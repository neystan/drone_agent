"""封装 PX4 DDS 发布、订阅与状态缓存。"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image

from px4_msgs.msg import (
    BatteryStatus,
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleCommandAck,
    VehicleLocalPosition,
    VehicleStatus,
)

from drone_agent.px4.frame import body_to_ned, is_finite_number, normalize_angle
from drone_agent.px4.topics import (
    BATTERY_STATUS_TOPIC,
    OFFBOARD_CONTROL_MODE_TOPIC,
    TRAJECTORY_SETPOINT_TOPIC,
    VEHICLE_COMMAND_TOPIC,
    VEHICLE_COMMAND_ACK_TOPIC,
    VEHICLE_LOCAL_POSITION_TOPIC,
    VEHICLE_STATUS_TOPIC,
)


DEFAULT_POSITION_TOLERANCE_M = 0.3
DEFAULT_YAW_TOLERANCE_RAD = math.radians(5.0)
DEFAULT_TIMER_PERIOD_S = 0.1


@dataclass(frozen=True)
class CommandRequest:
    """记录一条命令发送前的 ACK 序号。"""

    command: int
    ack_sequence_before: int


PX4_COMMAND_RESULT_NAMES = {
    0: "ACCEPTED",
    1: "TEMPORARILY_REJECTED",
    2: "DENIED",
    3: "UNSUPPORTED",
    4: "FAILED",
    5: "IN_PROGRESS",
    6: "CANCELLED",
}


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
        self.create_subscription(
            VehicleCommandAck,
            VEHICLE_COMMAND_ACK_TOPIC,
            self.vehicle_command_ack_callback,
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
        self.vehicle_status_received = False
        self.battery_status_received = False
        self.vehicle_command_ack = None
        self.vehicle_command_ack_sequence = 0
        self.vehicle_command_ack_history: deque[tuple[int, Any]] = deque(maxlen=64)
        self._vehicle_command_ack_lock = threading.Lock()
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
        self.vehicle_status_received = True

    def battery_status_callback(self, msg: BatteryStatus) -> None:
        """更新电池状态缓存。"""
        self.battery_status = msg
        self.battery_status_received = True

    def vehicle_command_ack_callback(self, msg: VehicleCommandAck) -> None:
        """缓存 PX4 命令 ACK，并推进序号。"""
        with self._vehicle_command_ack_lock:
            self.vehicle_command_ack_sequence += 1
            self.vehicle_command_ack = msg
            self.vehicle_command_ack_history.append(
                (self.vehicle_command_ack_sequence, msg)
            )

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
        self._validate_setpoint(position, yaw, yawspeed)
        msg = TrajectorySetpoint()
        msg.position = position
        msg.yaw = float("nan") if yaw is None else yaw
        msg.yawspeed = float("nan") if yawspeed is None else yawspeed
        msg.timestamp = self.timestamp_us()
        self.trajectory_setpoint_publisher.publish(msg)

    def publish_vehicle_command(self, command: int, **params: float) -> CommandRequest:
        """发布 PX4 vehicle command 并返回 ACK 请求句柄。"""
        request = self._build_command_request(command)
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
        return request

    def _build_command_request(self, command: int) -> CommandRequest:
        """记录命令发送前的 ACK 序号。"""
        return CommandRequest(
            command=int(command),
            ack_sequence_before=int(getattr(self, "vehicle_command_ack_sequence", 0)),
        )

    def get_command_ack(self, request: CommandRequest) -> Any | None:
        """返回该请求之后、命令号匹配的最新 ACK。"""
        lock = getattr(self, "_vehicle_command_ack_lock", None)
        if lock is None:
            history = tuple(getattr(self, "vehicle_command_ack_history", ()))
            latest_sequence = int(getattr(self, "vehicle_command_ack_sequence", 0))
            ack = getattr(self, "vehicle_command_ack", None)
        else:
            with lock:
                history = tuple(getattr(self, "vehicle_command_ack_history", ()))
                latest_sequence = int(getattr(self, "vehicle_command_ack_sequence", 0))
                ack = getattr(self, "vehicle_command_ack", None)
        for sequence, ack in reversed(history):
            if sequence > request.ack_sequence_before and getattr(ack, "command", None) == request.command:
                return ack

        if (
            latest_sequence > request.ack_sequence_before
            and ack is not None
            and getattr(ack, "command", None) == request.command
        ):
            return ack
        return None

    def wait_for_command_ack(
        self,
        request: CommandRequest,
        timeout_s: float,
    ) -> Any | None:
        """等待该请求对应的 PX4 ACK。"""
        deadline = time.monotonic() + max(0.0, timeout_s)
        while time.monotonic() < deadline:
            ack = self.get_command_ack(request)
            if ack is not None:
                return ack
            time.sleep(self.timer_period)
        return self.get_command_ack(request)

    def is_command_ack_accepted(self, ack: Any) -> bool:
        """判断 PX4 ACK 是否为接受结果。"""
        return int(getattr(ack, "result", -1)) == 0

    def command_ack_result_name(self, ack: Any) -> str:
        """把 PX4 ACK 结果转换为稳定名称。"""
        result = int(getattr(ack, "result", -1))
        return PX4_COMMAND_RESULT_NAMES.get(result, f"UNKNOWN_{result}")

    def nav_state_constant(self, name: str, fallback: int) -> int:
        """读取 PX4 VehicleStatus 导航状态常量。"""
        return int(getattr(self.vehicle_status.__class__, name, fallback))

    def wait_for_arming_state(self, expected_arming_state: int, timeout_s: float) -> bool:
        """等待飞控切换到指定解锁状态。"""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.vehicle_status.arming_state == expected_arming_state:
                return True
            time.sleep(self.timer_period)
        return self.vehicle_status.arming_state == expected_arming_state

    @staticmethod
    def _validate_setpoint(
        position: list[float],
        yaw: float | None,
        yawspeed: float | None,
    ) -> None:
        """拒绝任何会把异常浮点数发送给 PX4 的 setpoint。"""
        if (
            not isinstance(position, (list, tuple))
            or len(position) != 3
            or any(not is_finite_number(value) for value in position)
        ):
            raise ValueError("position must contain exactly three finite numbers")
        if yaw is not None and not is_finite_number(yaw):
            raise ValueError("yaw must be finite when specified")
        if yawspeed is not None and not is_finite_number(yawspeed):
            raise ValueError("yawspeed must be finite when specified")

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
    def send_offboard_mode_command(self) -> CommandRequest:
        """请求切换到 PX4 offboard 模式。"""
        request = self.publish_vehicle_command(
            VehicleCommand.VEHICLE_CMD_DO_SET_MODE,
            param1=1.0,
            param2=6.0,
        )
        self.get_logger().info("Switching to offboard mode")
        return request

    def send_arm_command(self) -> CommandRequest:
        """发送解锁命令。"""
        request = self.publish_vehicle_command(
            VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
            param1=1.0,
        )
        self.get_logger().info("Arm command sent")
        return request

    def send_disarm_command(self) -> CommandRequest:
        """发送上锁命令。"""
        request = self.publish_vehicle_command(
            VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
            param1=0.0,
        )
        self.get_logger().info("Disarm command sent")
        return request

    def send_land_command(self) -> CommandRequest:
        """发送降落命令。"""
        request = self.publish_vehicle_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)
        self.get_logger().info("Switching to land mode")
        return request

    def send_hover_command(self) -> CommandRequest:
        """发送悬停模式切换命令。"""
        request = self.publish_vehicle_command(
            VehicleCommand.VEHICLE_CMD_DO_SET_MODE,
            param1=1.0,
            param2=4.0,
            param3=3.0,
        )
        self.get_logger().info("Switching to AUTO_LOITER hover mode")
        return request

    def send_return_home_command(self) -> CommandRequest:
        """发送返航模式切换命令。"""
        request = self.publish_vehicle_command(VehicleCommand.VEHICLE_CMD_NAV_RETURN_TO_LAUNCH)
        self.get_logger().info("Switching to return-to-launch mode")
        return request

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
        self._validate_setpoint(position, yaw, yawspeed)
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
