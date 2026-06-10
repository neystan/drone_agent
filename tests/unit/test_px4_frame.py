"""验证 PX4 坐标系转换工具。"""

import math

import pytest

from drone_agent.px4.frame import body_to_ned, normalize_angle


def test_body_to_ned_with_zero_heading_keeps_forward_right_down():
    assert body_to_ned(1.0, 2.0, 3.0, 0.0) == pytest.approx((1.0, 2.0, 3.0))


def test_body_to_ned_with_ninety_degree_heading_rotates_body_axes():
    x_ned, y_ned, z_ned = body_to_ned(1.0, 0.0, -0.5, math.pi / 2.0)

    assert x_ned == pytest.approx(0.0, abs=1e-9)
    assert y_ned == pytest.approx(1.0)
    assert z_ned == pytest.approx(-0.5)


def test_body_to_ned_matches_takeoff_py_formula_for_right_offset():
    heading = math.radians(30.0)

    x_ned, y_ned, z_ned = body_to_ned(0.0, 2.0, 1.0, heading)

    assert x_ned == pytest.approx(-2.0 * math.sin(heading))
    assert y_ned == pytest.approx(2.0 * math.cos(heading))
    assert z_ned == pytest.approx(1.0)


def test_normalize_angle_wraps_to_minus_pi_pi():
    assert normalize_angle(3.0 * math.pi) == pytest.approx(math.pi)
    assert normalize_angle(-3.0 * math.pi) == pytest.approx(-math.pi)
    assert normalize_angle(0.25) == pytest.approx(0.25)
