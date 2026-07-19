"""XFLR5未接続時のモック空力ポーラ生成(Step 5 / T-202)。

**これは実際のXFLR5解析ではない。** 有限翼の揚力線理論(thin airfoil theory +
Prandtlの有限翼補正)による粗い近似であり、翼型固有の詳細特性(遷移、圧力分布、
実際の失速挙動、モーメント特性)は反映しない。実設計判断にはXFLR5等による実解析
(execution_mode=real)またはXROTOR等の実測値を用いること。

出典: Anderson, "Fundamentals of Aerodynamics" の有限翼揚力線傾斜補正式
  a = a0 / (1 + a0 / (π·AR·e))
CD = CD0 + CL²/(π·AR·e) は initial_sizing.py と同一の抗力極線モデル(誘導抗力)。
"""

from __future__ import annotations

import math

from pbm.calculation.lifting_line import (
    THIN_AIRFOIL_LIFT_SLOPE_PER_RAD,
    finite_wing_lift_slope,
)
from pbm.domain.aero_analysis import AeroAnalysisOutput, AeroAnalysisRequest, AeroPolarPoint
from pbm.domain.quantities import Quantity
from pbm.domain.results import AssumptionRecord, CalcWarning, FormulaRecord, Severity


def generate_mock_polar(request: AeroAnalysisRequest) -> AeroAnalysisOutput:
    """有限翼揚力線理論による近似ポーラを生成する(モック。実XFLR5解析ではない)。"""
    a0 = THIN_AIRFOIL_LIFT_SLOPE_PER_RAD
    lift_slope = finite_wing_lift_slope(request.aspect_ratio, request.oswald_efficiency)

    formulas = [
        FormulaRecord(
            symbol="a",
            name="有限翼揚力傾斜(モック近似)",
            expression="a = a0 / (1 + a0 / (π · AR · e))",
            substitutions={
                "a0": f"{a0:.6g} /rad",
                "AR": f"{request.aspect_ratio:.6g}",
                "e": f"{request.oswald_efficiency:.6g}",
            },
            result=Quantity(value=lift_slope, unit="1/radian"),
            source="有限翼揚力線理論(Anderson, Fundamentals of Aerodynamics)。モック近似",
        )
    ]

    alpha_span = request.alpha_max_deg - request.alpha_min_deg
    n_steps = max(1, round(alpha_span / request.alpha_step_deg))
    polar: list[AeroPolarPoint] = []
    for i in range(n_steps + 1):
        alpha_deg = request.alpha_min_deg + i * request.alpha_step_deg
        alpha_rad = math.radians(alpha_deg)
        cl_unstalled = lift_slope * alpha_rad  # 零揚力角=0の仮定(対称翼型近似)
        stalled = abs(cl_unstalled) > request.cl_max
        cl = math.copysign(request.cl_max, cl_unstalled) if stalled else cl_unstalled
        cd = request.parasite_drag_coefficient + (cl**2) / (
            math.pi * request.aspect_ratio * request.oswald_efficiency
        )
        polar.append(
            AeroPolarPoint(alpha_deg=alpha_deg, cl=cl, cd=cd, cm=0.0, stalled=stalled)
        )

    valid = [p for p in polar if p.cd > 1e-12]
    best = max(valid, key=lambda p: p.cl / p.cd, default=None)
    max_ld = (best.cl / best.cd) if best else 0.0
    cl_at_max_ld = best.cl if best else 0.0

    warnings: list[CalcWarning] = []
    if any(p.stalled for p in polar):
        warnings.append(
            CalcWarning(
                code="MOCK_POLAR_STALL_CLIPPED",
                severity=Severity.info,
                message="迎角範囲内でCL_maxを超えたためクリップした(モック近似の簡易失速処理)",
            )
        )

    assumptions = [
        AssumptionRecord(
            id="A-102",
            name="零揚力角",
            value="0 deg",
            rationale="翼型座標データ未使用のため対称翼型を仮定。実XFLR5解析で更新すること",
        ),
        AssumptionRecord(
            id="A-104",
            name="モーメント係数Cm",
            value="0.0(全迎角で一定)",
            rationale="翼型固有のモーメント特性を反映していない。実XFLR5解析で更新すること",
        ),
    ]

    return AeroAnalysisOutput(
        polar=polar,
        max_lift_to_drag=max_ld,
        cl_at_max_lift_to_drag=cl_at_max_ld,
        formulas=formulas,
        assumptions=assumptions,
        warnings=warnings,
    )
