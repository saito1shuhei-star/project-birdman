"""XROTOR未接続時のモックプロペラ解析(Step 6 / T-203)。

**これは実際のXROTOR解析ではない。** 作動円板の運動量理論(Rankine-Froude)による
理想値の推定であり、ブレードの翼型抗力・回転流(スワール)・枚数・ハブの影響を含まない。
得られる効率は**理論上限**であり、実効効率は必ずこれより低い。
実設計判断にはXROTOR等による実解析(execution_mode=real)または台上試験を用いること。

理論(出典: McCormick "Aerodynamics, Aeronautics, and Flight Mechanics" /
Anderson "Introduction to Flight" のプロペラ運動量理論):
  円板面積      A = π·D²/4
  スリップストリーム速度 w = V + v_i(v_i: 円板位置の誘導速度)
  推力          T = 2·ρ·A·w·(w − V)
  所要動力      P = T·(V + v_i) = 2·ρ·A·w²·(w − V)
  → 入力Pからwを解く(wの3次方程式。Newton法)
  理想推進効率  η_ideal = T·V / P = V / (V + v_i)(Froude効率)
"""

from __future__ import annotations

import math

from pbm.domain.errors import CalculationError
from pbm.domain.prop_analysis import PropAnalysisOutput, PropAnalysisRequest
from pbm.domain.quantities import Quantity
from pbm.domain.results import AssumptionRecord, CalcWarning, FormulaRecord, Severity

_SOURCE = "作動円板の運動量理論(McCormick / Anderson)。モック近似"

_NEWTON_MAX_ITER = 100
_NEWTON_REL_TOL = 1e-13


def _solve_slipstream_velocity(two_rho_area: float, speed: float, power: float) -> float:
    """2ρA·w²·(w−V) = P を w について解く(w > V の実根、Newton法)。"""
    w = speed * 1.05 + 0.1  # 初期値: 巡航速度よりわずかに大きい値
    for _ in range(_NEWTON_MAX_ITER):
        f = two_rho_area * (w**3 - speed * w**2) - power
        df = two_rho_area * (3.0 * w**2 - 2.0 * speed * w)
        if df <= 0:  # w > V > 0 では起こらないはず(数値的安全弁)
            raise CalculationError("プロペラ運動量理論の解の探索に失敗しました(df<=0)")
        w_next = w - f / df
        if w_next <= speed:
            w_next = (w + speed) / 2.0  # 物理解 w > V の範囲へ戻す
        if abs(w_next - w) <= _NEWTON_REL_TOL * w:
            return w_next
        w = w_next
    raise CalculationError("プロペラ運動量理論の解が収束しませんでした")


def run_mock_momentum_analysis(request: PropAnalysisRequest) -> PropAnalysisOutput:
    """運動量理論による理想プロペラ性能の推定(モック。実XROTOR解析ではない)。"""
    speed = request.flight_speed.magnitude_si          # m/s
    power = request.input_power.magnitude_si           # W
    diameter = request.diameter.magnitude_si           # m
    rho = request.air_density.magnitude_si             # kg/m^3

    disk_area = math.pi * diameter**2 / 4.0
    two_rho_area = 2.0 * rho * disk_area
    slipstream = _solve_slipstream_velocity(two_rho_area, speed, power)
    induced_velocity = slipstream - speed
    thrust = two_rho_area * slipstream * induced_velocity
    ideal_efficiency = thrust * speed / power
    disk_loading = thrust / disk_area

    def _fmt(value: float, unit: str = "") -> str:
        return f"{format(value, '.6g')} {unit}".strip()

    formulas = [
        FormulaRecord(
            symbol="A", name="円板面積", expression="A = π · D² / 4",
            substitutions={"D": _fmt(diameter, "m")},
            result=Quantity(value=disk_area, unit="m^2"), source=_SOURCE,
        ),
        FormulaRecord(
            symbol="w", name="スリップストリーム速度",
            expression="2·ρ·A·w²·(w − V) = P を w について解く",
            substitutions={
                "ρ": _fmt(rho, "kg/m³"), "A": _fmt(disk_area, "m²"),
                "V": _fmt(speed, "m/s"), "P": _fmt(power, "W"),
            },
            result=Quantity(value=slipstream, unit="m/s"), source=_SOURCE,
        ),
        FormulaRecord(
            symbol="T", name="推力(理想)", expression="T = 2·ρ·A·w·(w − V)",
            substitutions={
                "ρ": _fmt(rho, "kg/m³"), "A": _fmt(disk_area, "m²"),
                "w": _fmt(slipstream, "m/s"), "V": _fmt(speed, "m/s"),
            },
            result=Quantity(value=thrust, unit="N"), source=_SOURCE,
        ),
        FormulaRecord(
            symbol="η_ideal", name="理想推進効率(Froude効率)",
            expression="η_ideal = T·V / P = V / (V + v_i)",
            substitutions={
                "T": _fmt(thrust, "N"), "V": _fmt(speed, "m/s"), "P": _fmt(power, "W"),
            },
            result=Quantity(value=ideal_efficiency, unit="dimensionless"), source=_SOURCE,
        ),
    ]

    quantities = {
        "disk_area": Quantity(value=disk_area, unit="m^2"),
        "slipstream_velocity": Quantity(value=slipstream, unit="m/s"),
        "induced_velocity": Quantity(value=induced_velocity, unit="m/s"),
        "thrust_ideal": Quantity(value=thrust, unit="N"),
        "ideal_efficiency": Quantity(value=ideal_efficiency, unit="dimensionless"),
        "disk_loading": Quantity(value=disk_loading, unit="N/m^2"),
    }
    for name, q in quantities.items():
        if not math.isfinite(q.value):
            raise CalculationError(f"計算結果が非有限値です: {name} = {q.value}")

    warnings = [
        CalcWarning(
            code="MOCK_IDEAL_EFFICIENCY",
            severity=Severity.warning,
            message=(
                f"η_ideal = {ideal_efficiency:.3f} は運動量理論の理論上限です。"
                "実効効率はブレード翼型抗力・回転流損失により必ずこれより低くなります"
                "(HPA実績帯はA-106参照)。XROTOR実解析または台上試験で評価してください"
            ),
        ),
    ]
    if request.blade_count != 2 or request.hub_diameter or request.rotation_speed:
        warnings.append(CalcWarning(
            code="MOCK_GEOMETRY_UNUSED",
            severity=Severity.info,
            message=(
                "ブレード枚数・ハブ径・回転数はモック(運動量理論)では使用されません。"
                "実解析(XROTOR)への入力として記録のみされています"
            ),
        ))

    assumptions = [
        AssumptionRecord(
            id="A-120", name="作動円板近似",
            value="無限枚ブレード・スワールなし・一様流入",
            rationale="運動量理論の標準仮定。ブレード形状の影響はXROTOR実解析で評価すること",
        ),
    ]

    return PropAnalysisOutput(
        quantities=quantities, formulas=formulas, assumptions=assumptions, warnings=warnings
    )
