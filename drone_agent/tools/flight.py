"""飞行动作工具实现。"""

from __future__ import annotations

import math
import time
from typing import Any

from drone_agent.config.schema import RuntimeProfile


WAIT_FOR_POSITION_TIMEOUT_S = 3.0
LAND_TIMEOUT_S = 45.0
MIN_IN_AIR_ALTITUDE_M = -0.3
MAX_ALTITUDE_NED_M = -10.0
def switch_to_hover_on_timeout(controller: Any) -> None:
    """在动作超时后切换到 PX4 悬停模式。"""
    controller.stop_position_hold()
    controller.send_hover_command()
    auto_loiter_state = getattr(
        controller.vehicle_status.__class__,
        "NAVIGATION_STATE_AUTO_LOITER",
        None,
    )
    if auto_loiter_state is None:
        controller.get_logger().warn(
            "NAVIGATION_STATE_AUTO_LOITER is unavailable; hover mode was not confirmed"
        )
        return
    if not controller.wait_for_nav_state(auto_loiter_state, timeout_s=2.0):
        controller.get_logger().warn("AUTO_LOITER mode was not confirmed")


def _wait_for_valid_position(controller: Any) -> bool:
    """等待本地位置状态变为有效。"""
    wait_deadline = time.time() + WAIT_FOR_POSITION_TIMEOUT_S
    while time.time() < wait_deadline:
        if controller.uav_position_is_valid():
            return True
        time.sleep(controller.timer_period)
    return controller.uav_position_is_valid()


def takeoff(controller: Any, height: float, profile: RuntimeProfile) -> dict:
    """控制无人机原地起飞到目标高度。"""
    if not isinstance(height, (int, float)):
        return {
            "success": False,
            "error": "INVALID_HEIGHT_TYPE",
            "message": "height must be a number",
        }

    height = float(height)
    if height <= 0.0:
        return {
            "success": False,
            "error": "INVALID_HEIGHT_VALUE",
            "message": "height must be greater than 0",
        }

    if height > profile.safety.max_takeoff_height_m:
        return {
            "success": False,
            "error": "HEIGHT_TOO_LARGE",
            "message": "height exceeds safety limit",
        }

    if not _wait_for_valid_position(controller):
        return {
            "success": False,
            "error": "POSITION_INVALID",
            "message": "local position is not valid",
        }

    if controller.uav_is_in_air():
        return {
            "success": False,
            "error": "ALREADY_IN_AIR",
            "message": "uav is already in air",
        }

    current_position = controller.vehicle_local_position
    target_position = [
        current_position.x,
        current_position.y,
        current_position.z - height,
    ]
    controller.start_position_hold(target_position)
    controller.get_logger().info(f"takeoff(height={height}) accepted, target={target_position}")

    timeout = time.time() + profile.safety.action_timeout_s
    while time.time() < timeout:
        if controller.is_at_target(target_position):
            time.sleep(0.5)
            return {
                "success": True,
                "message": f"takeoff complete, reached {height:.1f}m",
                "target_height": height,
                "reference_xy_ned": [current_position.x, current_position.y],
                "reference_z_ned": current_position.z,
                "target_position_ned": target_position,
                "final_position_ned": controller.current_position_ned(),
            }
        time.sleep(controller.timer_period)

    if profile.safety.hover_on_timeout:
        switch_to_hover_on_timeout(controller)
    return {
        "success": False,
        "error": "TAKEOFF_TIMEOUT",
        "message": "takeoff did not reach target height within timeout. Auto switched to hover mode.",
        "target_position_ned": target_position,
        "final_position_ned": controller.current_position_ned(),
    }


def land(controller: Any, profile: RuntimeProfile) -> dict:
    """控制无人机执行降落。"""
    if not _wait_for_valid_position(controller):
        return {
            "success": False,
            "error": "POSITION_INVALID",
            "message": "local position is not valid",
        }

    if not controller.uav_is_in_air():
        return {
            "success": False,
            "error": "ALREADY_ON_GROUND",
            "message": "uav is already on the ground",
        }

    controller.stop_position_hold()
    controller.send_land_command()

    timeout = time.time() + max(profile.safety.action_timeout_s, LAND_TIMEOUT_S)
    while time.time() < timeout:
        if not controller.uav_is_in_air():
            return {
                "success": True,
                "message": "landing complete, uav is on the ground",
                "final_position_ned": controller.current_position_ned(),
            }
        time.sleep(controller.timer_period)

    if profile.safety.hover_on_timeout:
        switch_to_hover_on_timeout(controller)
    return {
        "success": False,
        "error": "LAND_TIMEOUT",
        "message": "landing did not complete within timeout. Auto switched to hover mode.",
        "final_position_ned": controller.current_position_ned(),
    }


def disarm(controller: Any) -> dict:
    """发送电机上锁命令。"""
    controller.stop_position_hold()
    controller.send_disarm_command()
    time.sleep(0.5)
    return {
        "success": True,
        "message": "uav disarm command sent",
    }


def timer(seconds: int) -> dict:
    """执行一个简单的计时等待工具。"""
    if not isinstance(seconds, int):
        return {
            "success": False,
            "error": "INVALID_SECONDS_TYPE",
            "message": "seconds must be an integer",
        }

    if seconds <= 0:
        return {
            "success": False,
            "error": "INVALID_SECONDS_VALUE",
            "message": "seconds must be greater than 0",
        }

    if seconds > 600:
        return {
            "success": False,
            "error": "SECONDS_TOO_LARGE",
            "message": "seconds exceeds safety limit",
        }

    deadline = time.monotonic() + seconds
    print(f"timer> 开始计时，目标时长 {seconds:.1f}s")
    while True:
        now = time.monotonic()
        remaining = deadline - now
        if remaining <= 0:
            break
        elapsed = seconds - remaining
        print(f"\rtimer> 已计时 {elapsed:.1f}s / {seconds:.1f}s", end="", flush=True)
        time.sleep(min(remaining, 0.1))
    print(f"\rtimer> 已计时 {seconds:.1f}s / {seconds:.1f}s")

    return {
        "success": True,
        "message": f"timer complete after {seconds} seconds",
        "waited_seconds": seconds,
    }


def hover(controller: Any) -> dict:
    """切换到 PX4 AUTO_LOITER 悬停模式。"""
    if not _wait_for_valid_position(controller):
        return {
            "success": False,
            "error": "POSITION_INVALID",
            "message": "local position is not valid",
        }

    if not controller.uav_is_in_air():
        return {
            "success": False,
            "error": "ALREADY_ON_GROUND",
            "message": "uav is on the ground and cannot enter hover mode",
        }

    controller.stop_position_hold()
    controller.send_hover_command()
    time.sleep(0.5)
    return {
        "success": True,
        "message": "hover mode engaged with AUTO_LOITER",
    }


def return_home(controller: Any) -> dict:
    """切换到 PX4 RTL 返航模式。"""
    if not _wait_for_valid_position(controller):
        return {
            "success": False,
            "error": "POSITION_INVALID",
            "message": "local position is not valid",
        }

    if not controller.uav_is_in_air():
        return {
            "success": False,
            "error": "ALREADY_ON_GROUND",
            "message": "uav is on the ground and cannot return home",
        }

    controller.stop_position_hold()
    controller.send_return_home_command()
    time.sleep(0.5)
    return {
        "success": True,
        "message": "return-to-home mode engaged with PX4 RTL",
    }


def rotate(controller: Any, direction: str, degrees: float, profile: RuntimeProfile) -> dict:
    """在保持当前位置的同时执行定角度旋转。"""
    if direction not in {"left", "right"}:
        return {
            "success": False,
            "error": "INVALID_DIRECTION",
            "message": "direction must be 'left' or 'right'",
        }

    if not isinstance(degrees, (int, float)):
        return {
            "success": False,
            "error": "INVALID_DEGREES_TYPE",
            "message": "degrees must be a number",
        }

    degrees = float(degrees)
    if degrees < 0.0:
        return {
            "success": False,
            "error": "INVALID_DEGREES_VALUE",
            "message": "degrees must be greater than or equal to 0",
        }

    if degrees > profile.safety.max_rotation_deg:
        return {
            "success": False,
            "error": "DEGREES_TOO_LARGE",
            "message": "degrees exceeds safety limit",
        }

    if not _wait_for_valid_position(controller):
        return {
            "success": False,
            "error": "POSITION_INVALID",
            "message": "local position is not valid",
        }

    if not controller.uav_is_in_air():
        return {
            "success": False,
            "error": "ALREADY_ON_GROUND",
            "message": "uav must take off before rotating",
        }

    current_heading = getattr(controller.vehicle_local_position, "heading", float("nan"))
    if not math.isfinite(current_heading):
        return {
            "success": False,
            "error": "HEADING_INVALID",
            "message": "local heading is not valid",
        }

    target_position = controller.current_position_ned()
    if degrees == 0.0:
        controller.start_position_hold(target_position, current_heading)
        return {
            "success": True,
            "message": "rotate complete after 0.0 degrees",
            "direction": direction,
            "target_yaw_rad": current_heading,
        }

    commanded_yawspeed = math.radians(45.0)
    if direction == "left":
        commanded_yawspeed = -commanded_yawspeed

    controller.start_position_hold(target_position, yawspeed=commanded_yawspeed)
    controller.get_logger().info(
        f"rotate(direction={direction}, degrees={degrees}) accepted, heading={current_heading}, yawspeed={commanded_yawspeed}"
    )

    accumulated_degrees = 0.0
    previous_heading = current_heading
    timeout = time.time() + max(profile.safety.action_timeout_s, degrees / 20.0)

    while time.time() < timeout:
        heading = getattr(controller.vehicle_local_position, "heading", float("nan"))
        if not math.isfinite(heading):
            controller.stop_position_hold()
            return {
                "success": False,
                "error": "HEADING_INVALID",
                "message": "local heading became invalid during rotate",
            }

        heading_delta = math.degrees(controller.normalize_angle(heading - previous_heading))
        previous_heading = heading

        if direction == "right" and heading_delta > 0.0:
            accumulated_degrees += heading_delta
        if direction == "left" and heading_delta < 0.0:
            accumulated_degrees += -heading_delta

        if accumulated_degrees >= degrees:
            final_heading = heading
            controller.start_position_hold(target_position, final_heading)
            settle_timeout = time.time() + 3.0
            while time.time() < settle_timeout:
                if controller.is_at_yaw_target(final_heading):
                    return {
                        "success": True,
                        "message": f"rotate complete after {direction} {degrees:.1f} degrees",
                        "direction": direction,
                        "target_yaw_rad": final_heading,
                        "final_position_ned": controller.current_position_ned(),
                    }
                time.sleep(controller.timer_period)
            return {
                "success": True,
                "message": f"rotate complete after {direction} {degrees:.1f} degrees",
                "direction": direction,
                "target_yaw_rad": final_heading,
                "final_position_ned": controller.current_position_ned(),
            }

        time.sleep(controller.timer_period)

    if profile.safety.hover_on_timeout:
        switch_to_hover_on_timeout(controller)
    return {
        "success": False,
        "error": "ROTATE_TIMEOUT",
        "message": "rotate did not reach target angle within timeout. Auto switched to hover mode.",
        "direction": direction,
        "target_yaw_rad": previous_heading,
        "final_position_ned": controller.current_position_ned(),
    }


def move(controller: Any, x: float, y: float, z: float, profile: RuntimeProfile) -> dict:
    """按机体系 FRD 偏移执行相对移动。"""
    for name, value in (("x", x), ("y", y), ("z", z)):
        if not isinstance(value, (int, float)):
            return {
                "success": False,
                "error": f"INVALID_{name.upper()}_TYPE",
                "message": f"{name} must be a number",
            }

    x = float(x)
    y = float(y)
    z = float(z)

    if abs(x) > profile.safety.max_relative_move_m:
        return {
            "success": False,
            "error": "X_OUT_OF_RANGE",
            "message": "x exceeds safety limit",
        }

    if abs(y) > profile.safety.max_relative_move_m:
        return {
            "success": False,
            "error": "Y_OUT_OF_RANGE",
            "message": "y exceeds safety limit",
        }

    if abs(z) > profile.safety.max_vertical_move_m:
        return {
            "success": False,
            "error": "Z_OUT_OF_RANGE",
            "message": "z exceeds safety limit",
        }

    if not _wait_for_valid_position(controller):
        return {
            "success": False,
            "error": "POSITION_INVALID",
            "message": "local position is not valid",
        }

    if not controller.uav_is_in_air():
        return {
            "success": False,
            "error": "ALREADY_ON_GROUND",
            "message": "uav must take off before moving to a target position",
        }

    heading = getattr(controller.vehicle_local_position, "heading", float("nan"))
    if not math.isfinite(heading):
        return {
            "success": False,
            "error": "HEADING_INVALID",
            "message": "local heading is not valid",
        }

    current_position = controller.vehicle_local_position
    dx_ned, dy_ned, dz_ned = controller.body_to_ned(x, y, z, heading)
    target_position = [
        current_position.x + dx_ned,
        current_position.y + dy_ned,
        current_position.z + dz_ned,
    ]

    if target_position[2] < MAX_ALTITUDE_NED_M or target_position[2] > MIN_IN_AIR_ALTITUDE_M:
        return {
            "success": False,
            "error": "TARGET_Z_OUT_OF_RANGE",
            "message": "target altitude is outside allowed local NED range",
            "target_position_ned": target_position,
        }

    controller.start_position_hold(target_position)
    controller.get_logger().info(
        f"move(body_x={x}, body_y={y}, body_z={z}) accepted, heading={heading}, target={target_position}"
    )

    timeout = time.time() + profile.safety.action_timeout_s
    while time.time() < timeout:
        if controller.is_at_target(target_position):
            time.sleep(0.5)
            return {
                "success": True,
                "message": f"move complete after body-frame offset ({x:.2f}, {y:.2f}, {z:.2f})",
                "body_offset_frd": [x, y, z],
                "target_position_ned": target_position,
                "final_position_ned": controller.current_position_ned(),
            }
        time.sleep(controller.timer_period)

    if profile.safety.hover_on_timeout:
        switch_to_hover_on_timeout(controller)
    return {
        "success": False,
        "error": "MOVE_TIMEOUT",
        "message": "move did not reach target position within timeout. Auto switched to hover mode.",
        "body_offset_frd": [x, y, z],
        "target_position_ned": target_position,
        "final_position_ned": controller.current_position_ned(),
    }
