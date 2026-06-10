"""PX4 坐标系转换工具。"""

from __future__ import annotations

import math


def body_to_ned(
    forward: float,
    right: float,
    down: float,
    heading: float,
) -> tuple[float, float, float]:
    """把机体系 FRD 位移转换为世界系 NED 位移。"""
    x_ned = forward * math.cos(heading) - right * math.sin(heading)
    y_ned = forward * math.sin(heading) + right * math.cos(heading)
    return x_ned, y_ned, down


def normalize_angle(angle: float) -> float:
    """把角度归一化到 [-pi, pi]。"""
    return math.atan2(math.sin(angle), math.cos(angle))
