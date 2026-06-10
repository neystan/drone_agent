import math
"""验证 PX4 状态解析工具。"""

from types import SimpleNamespace

from drone_agent.px4.status import enum_name_from_prefix, flight_mode_status_dict


class FakeVehicleStatusEnum:
    NAVIGATION_STATE_MANUAL = 0
    NAVIGATION_STATE_OFFBOARD = 14
    ARMING_STATE_DISARMED = 1
    ARMING_STATE_ARMED = 2


def test_enum_name_from_prefix_returns_matching_constant_name():
    assert (
        enum_name_from_prefix(
            FakeVehicleStatusEnum,
            "NAVIGATION_STATE_",
            14,
        )
        == "NAVIGATION_STATE_OFFBOARD"
    )


def test_enum_name_from_prefix_returns_unknown_with_value():
    assert (
        enum_name_from_prefix(
            FakeVehicleStatusEnum,
            "NAVIGATION_STATE_",
            999,
        )
        == "UNKNOWN_NAVIGATION_STATE_999"
    )


def test_flight_mode_status_dict_uses_controller_state_methods():
    controller = SimpleNamespace(
        vehicle_local_position=SimpleNamespace(heading=math.nan),
        vehicle_status=SimpleNamespace(nav_state=14, arming_state=2),
        uav_is_in_air=lambda: True,
        uav_position_is_valid=lambda: True,
    )

    result = flight_mode_status_dict(controller, FakeVehicleStatusEnum)

    assert result == {
        "success": True,
        "nav_state_name": "NAVIGATION_STATE_OFFBOARD",
        "arming_state_name": "ARMING_STATE_ARMED",
        "in_air": True,
        "position_valid": True,
        "heading_valid": False,
    }
