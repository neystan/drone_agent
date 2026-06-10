"""通过源码文本检查 PX4 controller 的关键结构。"""

from pathlib import Path


CONTROLLER = Path(__file__).parents[2] / "drone_agent" / "px4" / "controller.py"


def source() -> str:
    """读取 controller 源码文本。"""
    return CONTROLLER.read_text(encoding="utf-8")


def test_controller_is_direct_ros2_node_subclass():
    text = source()

    assert "from rclpy.node import Node" in text
    assert "class Px4Controller(Node):" in text
    assert "RosDependencies" not in text
    assert "build_px4_controller_class" not in text


def test_controller_exposes_methods_needed_by_future_tools():
    text = source()

    for method in [
        "publish_offboard_heartbeat",
        "publish_position_setpoint",
        "publish_vehicle_command",
        "send_offboard_mode_command",
        "send_arm_command",
        "send_disarm_command",
        "send_land_command",
        "send_hover_command",
        "send_return_home_command",
        "uav_is_in_air",
        "uav_position_is_valid",
        "is_at_target",
        "is_at_yaw_target",
        "wait_for_nav_state",
        "start_position_hold",
        "stop_position_hold",
        "timer_callback",
        "current_position_ned",
    ]:
        assert f"def {method}" in text


def test_controller_uses_central_topics_and_px4_qos():
    text = source()

    for name in [
        "OFFBOARD_CONTROL_MODE_TOPIC",
        "TRAJECTORY_SETPOINT_TOPIC",
        "VEHICLE_COMMAND_TOPIC",
        "VEHICLE_LOCAL_POSITION_TOPIC",
        "VEHICLE_STATUS_TOPIC",
        "BATTERY_STATUS_TOPIC",
    ]:
        assert name in text

    assert "ReliabilityPolicy.BEST_EFFORT" in text
    assert "DurabilityPolicy.TRANSIENT_LOCAL" in text
    assert "HistoryPolicy.KEEP_LAST" in text
    assert "depth=1" in text
