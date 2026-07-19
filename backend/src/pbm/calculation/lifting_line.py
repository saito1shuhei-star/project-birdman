"""有限翼の揚力傾斜(揚力線理論)。空力モック・静安定計算で共用する。

出典: Anderson "Fundamentals of Aerodynamics" の有限翼補正式
  a = a0 / (1 + a0 / (π·AR·e)),  a0 = 2π(薄翼理論)
"""

from __future__ import annotations

import math

THIN_AIRFOIL_LIFT_SLOPE_PER_RAD = 2.0 * math.pi  # a0(2D薄翼理論)


def finite_wing_lift_slope(aspect_ratio: float, oswald_efficiency: float) -> float:
    """有限翼の揚力傾斜 a [1/rad]。"""
    a0 = THIN_AIRFOIL_LIFT_SLOPE_PER_RAD
    return a0 / (1.0 + a0 / (math.pi * aspect_ratio * oswald_efficiency))
