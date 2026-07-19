"""静安定余裕・尾翼容積の計算(Step 7 / T-303)。純粋関数。

出典: Nelson "Flight Stability and Automatic Control" の標準式:
  尾翼容積      V_H = S_t·l_t / (S·c̄)
  ダウンウォッシュ dε/dα ≈ 2·a_w / (π·AR)(楕円分布近似)
  中立点        x_np = x_ac + c̄·η_t·V_H·(a_t/a_w)·(1 − dε/dα)
  静安定余裕    SM = (x_np − x_cg) / c̄(正=安定)

注意: 胴体・プロペラのモーメント寄与は含まない(A-131)。SMを実際より
大きめに評価する傾向があるため、詳細解析(XFLR5安定性解析等)で検証すること。
"""

from __future__ import annotations

import math

from pbm.calculation.lifting_line import finite_wing_lift_slope
from pbm.domain.errors import CalculationError
from pbm.domain.quantities import Quantity
from pbm.domain.results import AssumptionRecord, CalcWarning, FormulaRecord, Severity
from pbm.domain.stability import StabilityOutput, StabilityRequest

_SOURCE = "静安定の標準式(Nelson, Flight Stability and Automatic Control)"


def compute_static_stability(
    request: StabilityRequest,
    *,
    wing_area_si: float,
    wing_mean_chord_si: float,
    wing_aspect_ratio: float,
    wing_oswald_efficiency: float,
    cg_x_si: float,
) -> StabilityOutput:
    """尾翼容積・中立点・静安定余裕を計算する。

    引数のwing_*は平面形(Step 4)、cg_xは質量台帳(Step 9)から供給される(SI値)。
    """
    s_t = request.horizontal_tail_area.magnitude_si
    l_t = request.tail_arm.magnitude_si
    x_ac = request.wing_ac_position.magnitude_si
    eta_t = request.tail_efficiency

    a_w = finite_wing_lift_slope(wing_aspect_ratio, wing_oswald_efficiency)
    a_t = finite_wing_lift_slope(request.tail_aspect_ratio, request.tail_oswald_efficiency)
    tail_volume = s_t * l_t / (wing_area_si * wing_mean_chord_si)
    downwash_derivative = 2.0 * a_w / (math.pi * wing_aspect_ratio)
    np_shift = eta_t * tail_volume * (a_t / a_w) * (1.0 - downwash_derivative)
    x_np = x_ac + wing_mean_chord_si * np_shift
    static_margin = (x_np - cg_x_si) / wing_mean_chord_si

    def _fmt(value: float, unit: str = "") -> str:
        return f"{format(value, '.6g')} {unit}".strip()

    quantities = {
        "tail_volume_horizontal": Quantity(value=tail_volume, unit="dimensionless"),
        "wing_lift_slope": Quantity(value=a_w, unit="1/radian"),
        "tail_lift_slope": Quantity(value=a_t, unit="1/radian"),
        "downwash_derivative": Quantity(value=downwash_derivative, unit="dimensionless"),
        "neutral_point_x": Quantity(value=x_np, unit="m"),
        "cg_x": Quantity(value=cg_x_si, unit="m"),
        "static_margin": Quantity(value=static_margin, unit="dimensionless"),
    }
    for name, q in quantities.items():
        if not math.isfinite(q.value):
            raise CalculationError(f"計算結果が非有限値です: {name} = {q.value}")

    formulas = [
        FormulaRecord(
            symbol="V_H", name="水平尾翼容積", expression="V_H = S_t·l_t / (S·c̄)",
            substitutions={
                "S_t": _fmt(s_t, "m²"), "l_t": _fmt(l_t, "m"),
                "S": _fmt(wing_area_si, "m²"), "c̄": _fmt(wing_mean_chord_si, "m"),
            },
            result=quantities["tail_volume_horizontal"], source=_SOURCE,
        ),
        FormulaRecord(
            symbol="dε/dα", name="ダウンウォッシュ勾配", expression="dε/dα = 2·a_w / (π·AR)",
            substitutions={"a_w": _fmt(a_w, "/rad"), "AR": _fmt(wing_aspect_ratio)},
            result=quantities["downwash_derivative"],
            source=_SOURCE + "(楕円分布近似 A-131)",
        ),
        FormulaRecord(
            symbol="x_np", name="中立点",
            expression="x_np = x_ac + c̄·η_t·V_H·(a_t/a_w)·(1 − dε/dα)",
            substitutions={
                "x_ac": _fmt(x_ac, "m"), "η_t": _fmt(eta_t),
                "V_H": _fmt(tail_volume), "a_t/a_w": _fmt(a_t / a_w),
                "1−dε/dα": _fmt(1.0 - downwash_derivative),
            },
            result=quantities["neutral_point_x"], source=_SOURCE,
        ),
        FormulaRecord(
            symbol="SM", name="静安定余裕", expression="SM = (x_np − x_cg) / c̄",
            substitutions={
                "x_np": _fmt(x_np, "m"), "x_cg": _fmt(cg_x_si, "m"),
                "c̄": _fmt(wing_mean_chord_si, "m"),
            },
            result=quantities["static_margin"], source=_SOURCE,
        ),
    ]

    warnings: list[CalcWarning] = []
    if static_margin < 0:
        warnings.append(CalcWarning(
            code="STATICALLY_UNSTABLE", severity=Severity.violation,
            message=(
                f"静安定余裕 SM = {static_margin:.3f} が負です(静的不安定)。"
                "重心の前進または尾翼容積の増加が必要です"
            ),
        ))
    elif static_margin < 0.05:
        warnings.append(CalcWarning(
            code="STATIC_MARGIN_LOW", severity=Severity.warning,
            message=f"SM = {static_margin:.3f} < 0.05(A-133推奨下限)。安定余裕が不足気味です",
        ))
    elif static_margin > 0.20:
        warnings.append(CalcWarning(
            code="STATIC_MARGIN_HIGH", severity=Severity.warning,
            message=(
                f"SM = {static_margin:.3f} > 0.20(A-133推奨上限)。"
                "過安定でトリム抗力・操縦性の悪化に注意"
            ),
        ))
    if not (0.3 <= tail_volume <= 1.0):
        warnings.append(CalcWarning(
            code="TAIL_VOLUME_ATYPICAL", severity=Severity.info,
            message=f"V_H = {tail_volume:.3f} は一般的範囲0.3–1.0の外です(A-134)",
        ))

    assumptions = [
        AssumptionRecord(
            id="A-131", name="静安定モデルの簡略化",
            value="胴体・プロペラのモーメント寄与を無視、dε/dαは楕円分布近似",
            rationale="MVPの近似。SMを過大評価する傾向。XFLR5等の詳細解析で検証すること",
        ),
        AssumptionRecord(
            id="A-132", name="尾翼効率 η_t", value=f"{eta_t}",
            rationale="後流動圧比の一般値0.85–0.95の中庸(入力で上書き可)",
        ),
        AssumptionRecord(
            id="A-133", name="SM推奨範囲", value="0.05–0.20",
            rationale="一般航空機の慣行値。HPAでの適値はチームの操縦性評価で確定すること",
        ),
    ]

    return StabilityOutput(
        quantities=quantities, formulas=formulas, assumptions=assumptions, warnings=warnings
    )
