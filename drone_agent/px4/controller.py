"""封装 PX4 DDS 发布、订阅与状态缓存。"""

from __future__ import annotations

import math
import time

from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image

from px4_msgs.msg import (
    BatteryStatus,
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
    VehicleStatus,
)

from drone_agent.px4.frame import body_to_ned, normalize_angle
from drone_agent.px4.topics import (
    BATTERY_STATUS_TOPIC,
    OFFBOARD_CONTROL_MODE_TOPIC,
    TRAJECTORY_SETPOINT_TOPIC,
    VEHICLE_COMMAND_TOPIC,
    VEHICLE_LOCAL_POSITION_TOPIC,
    VEHICLE_STATUS_TOPIC,
)


DEFAULT_POSITION_TOLERANCE_M = 0.3
DEFAULT_YAW_TOLERANCE_RAD = math.radians(5.0)
DEFAULT_TIMER_PERIOD_S = 0.1


class Px4Controller(Node):
    """负责 PX4 DDS 发布、订阅和状态缓存的底层控制器。"""

    def __init__(
        self,
        node_name: str,
        camera_scene_topic: str | None = None,
    ) -> None:
        """初始化 PX4 通信、状态订阅和定时器。"""
        super().__init__(node_name)

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        self.offboard_control_mode_publisher = self.create_publisher(
            OffboardControlMode,
            OFFBOARD_CONTROL_MODE_TOPIC,
            qos_profile,
        )
        self.trajectory_setpoint_publisher = self.create_publisher(
            TrajectorySetpoint,
            TRAJECTORY_SETPOINT_TOPIC,
            qos_profile,
        )
        self.vehicle_command_publisher = self.create_publisher(
            VehicleCommand,
            VEHICLE_COMMAND_TOPIC,
            qos_profile,
        )

        self.create_subscription(
            VehicleLocalPosition,
            VEHICLE_LOCAL_POSITION_TOPIC,
            self.vehicle_local_position_callback,
            qos_profile,
        )
        self.create_subscription(
            VehicleStatus,
            VEHICLE_STATUS_TOPIC,
            self.vehicle_status_callback,
            qos_profile,
        )
        self.create_subscription(
            BatteryStatus,
            BATTERY_STATUS_TOPIC,
            self.battery_status_callback,
            qos_profile,
        )
        if camera_scene_topic:
            self.create_subscription(
                Image,
                camera_scene_topic,
                self.rgb_image_callback,
                10,
            )

        self.vehicle_local_position = VehicleLocalPosition()
        self.vehicle_status = VehicleStatus()
        self.battery_status = BatteryStatus()
        self.bridge = CvBridge()
        self.latest_rgb_frame = None
        self.position_tolerance = DEFAULT_POSITION_TOLERANCE_M
        self.yaw_tolerance = DEFAULT_YAW_TOLERANCE_RAD
        self.timer_period = DEFAULT_TIMER_PERIOD_S

        self.target_position = None
        self.target_yaw = None
        self.target_yawspeed = None
        self.setpoint_counter = 0
        self.offboard_command_sent = False
        self.arm_command_sent = False

        self.timer = self.create_timer(self.timer_period, self.timer_callback)

    #订阅回调函数
    def vehicle_local_position_callback(self, msg: VehicleLocalPosition) -> None:
        """更新本地位置缓存。"""
        self.vehicle_local_position = msg

    def vehicle_status_callback(self, msg: VehicleStatus) -> None:
        """更新飞控状态缓存。"""
        self.vehicle_status = msg

    def battery_status_callback(self, msg: BatteryStatus) -> None:
        """更新电池状态缓存。"""
        self.battery_status = msg

    def rgb_image_callback(self, msg: Image) -> None:
        """把 ROS 图像消息转换并缓存为 OpenCV 图像。"""
        try:
            self.latest_rgb_frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as exc:
            self.get_logger().error(f"Failed to convert RGB image: {exc}")

    #发布消息函数
    def timestamp_us(self) -> int:
        """返回当前 ROS 时钟的微秒时间戳。"""
        return int(self.get_clock().now().nanoseconds / 1000)

    def publish_offboard_heartbeat(self) -> None:
        """发布 offboard 控制心跳。"""
        msg = OffboardControlMode()
        msg.position = True
        msg.velocity = False
        msg.acceleration = False
        msg.attitude = False
        msg.body_rate = False
        msg.timestamp = self.timestamp_us()
        self.offboard_control_mode_publisher.publish(msg)

    def publish_position_setpoint(
        self,
        position: list[float],
        yaw: float | None = None,
        yawspeed: float | None = None,
    ) -> None:
        """发布位置控制 setpoint。"""
        msg = TrajectorySetpoint()
        msg.position = position
        msg.yaw = float("nan") if yaw is None else yaw
        msg.yawspeed = float("nan") if yawspeed is None else yawspeed
        msg.timestamp = self.timestamp_us()
        self.trajectory_setpoint_publisher.publish(msg)

    def publish_vehicle_command(self, command: int, **params: float) -> None:
        """发布 PX4 vehicle command。"""
        msg = VehicleCommand()
        msg.command = command
        msg.param1 = params.get("param1", 0.0)
        msg.param2 = params.get("param2", 0.0)
        msg.param3 = params.get("param3", 0.0)
        msg.param4 = params.get("param4", 0.0)
        msg.param5 = params.get("param5", 0.0)
        msg.param6 = params.get("param6", 0.0)
        msg.param7 = params.get("param7", 0.0)
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = self.timestamp_us()
        self.vehicle_command_publisher.publish(msg)

    #机体转NED
    def body_to_ned(
        self,
        forward: float,
        right: float,
        down: float,
        heading: float,
    ) -> tuple[float, float, float]:
        """代理坐标转换工具，方便上层直接调用。"""
        return body_to_ned(forward, right, down, heading)

    def normalize_angle(self, angle: float) -> float:
        """代理角度归一化工具。"""
        return normalize_angle(angle)

    #控制基础实现
    def send_offboard_mode_command(self) -> None:
        """请求切换到 PX4 offboard 模式。"""
        self.publish_vehicle_command(
            VehicleCommand.VEHICLE_CMD_DO_SET_MODE,
            param1=1.0,
            param2=6.0,
        )
        self.get_logger().info("Switching to offboard mode")

    def send_arm_command(self) -> None:
        """发送解锁命令。"""
        self.publish_vehicle_command(
            VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
            param1=1.0,
        )
        self.get_logger().info("Arm command sent")

    def send_disarm_command(self) -> None:
        """发送上锁命令。"""
        self.publish_vehicle_command(
            VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
            param1=0.0,
        )
        self.get_logger().info("Disarm command sent")

    def send_land_command(self) -> None:
        """发送降落命令。"""
        self.publish_vehicle_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)
        self.get_logger().info("Switching to land mode")

    def send_hover_command(self) -> None:
        """发送悬停模式切换命令。"""
        self.publish_vehicle_command(
            VehicleCommand.VEHICLE_CMD_DO_SET_MODE,
            param1=1.0,
            param2=4.0,
            param3=3.0,
        )
        self.get_logger().info("Switching to AUTO_LOITER hover mode")

    def send_return_home_command(self) -> None:
        """发送返航模式切换命令。"""
        self.publish_vehicle_command(VehicleCommand.VEHICLE_CMD_NAV_RETURN_TO_LAUNCH)
        self.get_logger().info("Switching to return-to-launch mode")

    def uav_is_in_air(self) -> bool:
        """根据本地高度判断无人机是否已经离地。"""
        return (
            math.isfinite(self.vehicle_local_position.z)
            and self.vehicle_local_position.z < -0.3
        )

    def uav_position_is_valid(self) -> bool:
        """判断本地位置数据是否有效。"""
        pos = self.vehicle_local_position
        if not math.isfinite(pos.x) or not math.isfinite(pos.y) or not math.isfinite(pos.z):
            return False
        if hasattr(pos, "xy_valid") and not pos.xy_valid:
            return False
        if hasattr(pos, "z_valid") and not pos.z_valid:
            return False
        return True

    def is_at_target(self, position: list[float]) -> bool:
        """判断当前位置是否到达目标位置。"""
        dx = self.vehicle_local_position.x - position[0]
        dy = self.vehicle_local_position.y - position[1]
        dz = self.vehicle_local_position.z - position[2]
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        return distance <= self.position_tolerance

    def is_at_yaw_target(self, yaw: float) -> bool:
        """判断当前朝向是否到达目标朝向。"""
        current_heading = getattr(self.vehicle_local_position, "heading", float("nan"))
        if not math.isfinite(current_heading):
            return False
        yaw_error = self.normalize_angle(current_heading - yaw)
        return abs(yaw_error) <= self.yaw_tolerance

    def wait_for_nav_state(self, expected_nav_state: int, timeout_s: float) -> bool:
        """等待飞控切换到指定导航状态。"""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.vehicle_status.nav_state == expected_nav_state:
                return True
            time.sleep(self.timer_period)
        return self.vehicle_status.nav_state == expected_nav_state

    def start_position_hold(
        self,
        position: list[float],
        yaw: float | None = None,
        yawspeed: float | None = None,
    ) -> None:
        """开始持续发布位置保持 setpoint。"""
        self.target_position = position
        self.target_yaw = yaw
        self.target_yawspeed = yawspeed
        self.setpoint_counter = 0
        self.offboard_command_sent = False
        self.arm_command_sent = False

    def stop_position_hold(self) -> None:
        """停止持续发布位置保持 setpoint。"""
        self.target_position = None
        self.target_yaw = None
        self.target_yawspeed = None

    def current_position_ned(self) -> list[float]:
        """返回当前本地 NED 位置。"""
        return [
            self.vehicle_local_position.x,
            self.vehicle_local_position.y,
            self.vehicle_local_position.z,
        ]

    def timer_callback(self) -> None:
        """定时发布心跳和 setpoint，并在开始阶段切换 offboard/arm。"""
        if self.target_position is None:
            return

        self.publish_offboard_heartbeat()
        self.publish_position_setpoint(
            self.target_position,
            self.target_yaw,
            self.target_yawspeed,
        )

        if self.setpoint_counter == 10 and not self.offboard_command_sent:
            self.send_offboard_mode_command()
            self.offboard_command_sent = True

        if self.setpoint_counter == 11 and not self.arm_command_sent:
            self.send_arm_command()
            self.arm_command_sent = True

        if self.setpoint_counter < 12:
            self.setpoint_counter += 1
