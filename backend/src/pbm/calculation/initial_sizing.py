"""初期サイジング計算エンジン(Step 3 / CALCULATION_SPEC.md)。

- 純粋関数。DB・HTTP・ファイルI/Oを行わない(NFR-002)
- 入力は検証済み RequirementSpecInput(次元・範囲は domain 層で保証済み)
- 全式は定常・等速・水平飛行の標準関係式
  出典: Anderson "Introduction to Flight" / McCormick "Aerodynamics, Aeronautics,
  and Flight Mechanics"。式番号は CALCULATION_SPEC.md §1 に対応
- 各結果に式(FormulaRecord)・仮定(AssumptionRecord)・警告(CalcWarning)を付与する
"""

from __future__ import annotations

import math

from pbm.domain.errors import CalculationError
from pbm.domain.quantities import Quantity
from pbm.domain.requirements import RequirementSpecInput
from pbm.domain.results import (
    AssumptionRecord,
    CalcWarning,
    FormulaRecord,
    Severity,
    SizingOutput,
)

# 物理定数(ASSUMPTIONS A-001, A-003)
STANDARD_GRAVITY_M_S2 = 9.80665      # ISO 80000-3 定義値
AIR_VISCOSITY_PA_S = 1.789e-5        # ISA海面 15°C(ICAO Doc 7488)

_TEXTBOOK = "定常水平飛行の標準式(Anderson, Introduction to Flight)"


def _fmt(value: float, unit: str = "") -> str:
    s = format(value, ".6g")
    return f"{s} {unit}".strip()


def run_initial_sizing(spec: RequirementSpecInput) -> SizingOutput:
    """検証済み要求仕様から初期サイジングを計算する(CALCULATION_SPEC §1 式1〜16)。"""
    # --- SI値の取り出し(以後の計算はすべてSI基本単位) ---
    pilot_mass = spec.pilot_mass.magnitude_si                      # kg
    airframe_mass = spec.airframe_mass_target.magnitude_si         # kg
    power_available = spec.pilot_power_sustained.magnitude_si      # W
    cruise_speed = spec.target_cruise_speed.magnitude_si           # m/s
    wingspan = spec.wingspan_limit.magnitude_si                    # m(A-101: 翼幅制限=設計翼幅)
    air_density = spec.air_density.magnitude_si                    # kg/m^3
    cl = spec.cl_cruise
    cl_max = spec.cl_max
    cd0 = spec.cd0
    oswald = spec.oswald_efficiency
    eta_prop = spec.propeller_efficiency
    eta_drive = spec.drivetrain_efficiency

    formulas: list[FormulaRecord] = []

    def record(
        symbol: str,
        name: str,
        expression: str,
        substitutions: dict[str, str],
        value: float,
        unit: str,
        source: str = _TEXTBOOK,
    ) -> float:
        formulas.append(
            FormulaRecord(
                symbol=symbol,
                name=name,
                expression=expression,
                substitutions=substitutions,
                result=Quantity(value=value, unit=unit),
                source=source,
            )
        )
        return value

    # 式1: 全備質量
    total_mass = record(
        "m_total", "全備質量", "m_total = m_pilot + m_airframe",
        {"m_pilot": _fmt(pilot_mass, "kg"), "m_airframe": _fmt(airframe_mass, "kg")},
        pilot_mass + airframe_mass, "kg", source="質量の加算(定義)",
    )
    # 式2: 必要揚力(定常水平飛行 L = W)
    weight = record(
        "W", "全備重量(必要揚力)", "W = m_total · g",
        {"m_total": _fmt(total_mass, "kg"), "g": _fmt(STANDARD_GRAVITY_M_S2, "m/s²")},
        total_mass * STANDARD_GRAVITY_M_S2, "N",
        source="L = W(定常水平飛行の釣合い)。g: ISO 80000-3(A-001)",
    )
    # 式3: 動圧
    dynamic_pressure = record(
        "q", "動圧", "q = ½ · ρ · V²",
        {"ρ": _fmt(air_density, "kg/m³"), "V": _fmt(cruise_speed, "m/s")},
        0.5 * air_density * cruise_speed**2, "Pa",
    )
    # 式4: 必要翼面積
    wing_area = record(
        "S", "必要翼面積", "S = W / (q · CL_cruise)",
        {"W": _fmt(weight, "N"), "q": _fmt(dynamic_pressure, "Pa"), "CL_cruise": _fmt(cl)},
        weight / (dynamic_pressure * cl), "m^2",
    )
    # 式5: 翼面荷重
    wing_loading = record(
        "W/S", "翼面荷重", "W/S = W / S",
        {"W": _fmt(weight, "N"), "S": _fmt(wing_area, "m²")},
        weight / wing_area, "N/m^2",
    )
    # 式6: アスペクト比
    aspect_ratio = record(
        "AR", "アスペクト比", "AR = b² / S",
        {"b": _fmt(wingspan, "m"), "S": _fmt(wing_area, "m²")},
        wingspan**2 / wing_area, "dimensionless",
    )
    # 式7: 平均翼弦(矩形近似 A-108)
    mean_chord = record(
        "c̄", "平均翼弦", "c̄ = S / b",
        {"S": _fmt(wing_area, "m²"), "b": _fmt(wingspan, "m")},
        wing_area / wingspan, "m", source="矩形近似(A-108)",
    )
    # 式8: 失速速度
    stall_speed = record(
        "V_stall", "失速速度", "V_stall = √(2W / (ρ · S · CL_max))",
        {
            "W": _fmt(weight, "N"), "ρ": _fmt(air_density, "kg/m³"),
            "S": _fmt(wing_area, "m²"), "CL_max": _fmt(cl_max),
        },
        math.sqrt(2.0 * weight / (air_density * wing_area * cl_max)), "m/s",
    )
    # 式9: 誘導抗力係数
    induced_drag_coeff = record(
        "CDi", "誘導抗力係数", "CDi = CL² / (π · AR · e)",
        {"CL": _fmt(cl), "AR": _fmt(aspect_ratio), "e": _fmt(oswald)},
        cl**2 / (math.pi * aspect_ratio * oswald), "dimensionless",
        source="揚力線理論 + オズワルド効率(A-105)",
    )
    # 式10: 全機抗力係数
    total_drag_coeff = record(
        "CD", "全機抗力係数", "CD = CD0 + CDi",
        {"CD0": _fmt(cd0), "CDi": _fmt(induced_drag_coeff)},
        cd0 + induced_drag_coeff, "dimensionless",
        source="抗力の分解(CD0: A-104)",
    )
    # 式11: 全抗力 = 必要推力
    total_drag = record(
        "D", "全抗力(必要推力)", "D = q · S · CD",
        {
            "q": _fmt(dynamic_pressure, "Pa"),
            "S": _fmt(wing_area, "m²"),
            "CD": _fmt(total_drag_coeff),
        },
        dynamic_pressure * wing_area * total_drag_coeff, "N",
        source="T = D(定常飛行の釣合い)",
    )
    # 式12: 揚抗比
    lift_to_drag = record(
        "L/D", "揚抗比", "L/D = CL / CD",
        {"CL": _fmt(cl), "CD": _fmt(total_drag_coeff)},
        cl / total_drag_coeff, "dimensionless",
    )
    # 式13: 空力所要動力
    aero_power = record(
        "P_aero", "空力所要動力", "P_aero = D · V",
        {"D": _fmt(total_drag, "N"), "V": _fmt(cruise_speed, "m/s")},
        total_drag * cruise_speed, "W",
    )
    # 式14: パイロット必要出力
    required_pilot_power = record(
        "P_req", "パイロット必要出力", "P_req = P_aero / (η_prop · η_drive)",
        {"P_aero": _fmt(aero_power, "W"), "η_prop": _fmt(eta_prop), "η_drive": _fmt(eta_drive)},
        aero_power / (eta_prop * eta_drive), "W",
        source="推進効率の連鎖(η: A-106, A-107)",
    )
    # 式15: 出力収支
    power_margin = record(
        "ΔP", "出力収支", "ΔP = P_avail − P_req",
        {"P_avail": _fmt(power_available, "W"), "P_req": _fmt(required_pilot_power, "W")},
        power_available - required_pilot_power, "W",
        source="出力収支(定義)",
    )
    # 式16: レイノルズ数(平均翼弦基準)
    reynolds = record(
        "Re", "レイノルズ数(平均翼弦基準)", "Re = ρ · V · c̄ / μ",
        {
            "ρ": _fmt(air_density, "kg/m³"), "V": _fmt(cruise_speed, "m/s"),
            "c̄": _fmt(mean_chord, "m"), "μ": _fmt(AIR_VISCOSITY_PA_S, "Pa·s"),
        },
        air_density * cruise_speed * mean_chord / AIR_VISCOSITY_PA_S, "dimensionless",
        source="定義式。μ: ISA海面(A-003)",
    )

    quantities: dict[str, Quantity] = {
        "total_mass": Quantity(value=total_mass, unit="kg"),
        "required_lift": Quantity(value=weight, unit="N"),
        "dynamic_pressure": Quantity(value=dynamic_pressure, unit="Pa"),
        "wing_area": Quantity(value=wing_area, unit="m^2"),
        "wing_loading": Quantity(value=wing_loading, unit="N/m^2"),
        "aspect_ratio": Quantity(value=aspect_ratio, unit="dimensionless"),
        "mean_chord": Quantity(value=mean_chord, unit="m"),
        "stall_speed": Quantity(value=stall_speed, unit="m/s"),
        "induced_drag_coefficient": Quantity(value=induced_drag_coeff, unit="dimensionless"),
        "parasite_drag_coefficient": Quantity(value=cd0, unit="dimensionless"),
        "drag_coefficient_total": Quantity(value=total_drag_coeff, unit="dimensionless"),
        "required_thrust": Quantity(value=total_drag, unit="N"),
        "lift_to_drag": Quantity(value=lift_to_drag, unit="dimensionless"),
        "aero_power": Quantity(value=aero_power, unit="W"),
        "required_pilot_power": Quantity(value=required_pilot_power, unit="W"),
        "power_margin": Quantity(value=power_margin, unit="W"),
        "reynolds_number": Quantity(value=reynolds, unit="dimensionless"),
        "speed_to_stall_ratio": Quantity(value=cruise_speed / stall_speed, unit="dimensionless"),
    }

    # NaN/infの黙殺禁止(NFR-005)。発生すれば計算エンジンのバグ
    for name, q in quantities.items():
        if not math.isfinite(q.value):
            raise CalculationError(f"計算結果が非有限値です: {name} = {q.value}")

    warnings = _collect_warnings(
        power_margin=power_margin,
        power_available=power_available,
        speed_ratio=cruise_speed / stall_speed,
        aspect_ratio=aspect_ratio,
        reynolds=reynolds,
        wing_loading=wing_loading,
        cl=cl,
    )
    assumptions = _collect_assumptions(spec)

    return SizingOutput(
        quantities=quantities, formulas=formulas, assumptions=assumptions, warnings=warnings
    )


def _collect_warnings(
    *,
    power_margin: float,
    power_available: float,
    speed_ratio: float,
    aspect_ratio: float,
    reynolds: float,
    wing_loading: float,
    cl: float,
) -> list[CalcWarning]:
    """推奨範囲・制約の判定(CALCULATION_SPEC §3)。"""
    warnings: list[CalcWarning] = []
    if power_margin < 0:
        warnings.append(CalcWarning(
            code="POWER_DEFICIT", severity=Severity.violation,
            message=(
                f"必要出力がパイロット持続出力を {-power_margin:.1f} W 超過しています。"
                "持続水平飛行は成立しません。質量低減・翼幅拡大・抵抗低減を検討してください"
            ),
        ))
    elif power_margin < 0.1 * power_available:
        warnings.append(CalcWarning(
            code="POWER_MARGIN_LOW", severity=Severity.warning,
            message=f"出力余裕が10%未満です(余裕 {power_margin:.1f} W)",
        ))
    if speed_ratio < 1.15:
        warnings.append(CalcWarning(
            code="STALL_MARGIN_LOW", severity=Severity.warning,
            message=(
                f"失速余裕が不足しています(V/V_stall = {speed_ratio:.3f} < 1.15、A-111)。"
                "巡航速度またはCL_maxの見直しを検討してください"
            ),
        ))
    if aspect_ratio > 40:
        warnings.append(CalcWarning(
            code="ASPECT_RATIO_HIGH", severity=Severity.warning,
            message=f"AR = {aspect_ratio:.1f} > 40。構造成立性・翼剛性に注意(HPA上限域)",
        ))
    elif aspect_ratio < 15:
        warnings.append(CalcWarning(
            code="ASPECT_RATIO_LOW", severity=Severity.info,
            message=f"AR = {aspect_ratio:.1f} < 15。HPAとしては低ARで誘導抗力が大きくなります",
        ))
    if reynolds < 2.0e5:
        warnings.append(CalcWarning(
            code="REYNOLDS_LOW", severity=Severity.warning,
            message=f"Re = {reynolds:.3g} < 2.0e5。低Re領域のため翼型データの適用範囲に注意",
        ))
    if wing_loading > 60:
        warnings.append(CalcWarning(
            code="WING_LOADING_HIGH", severity=Severity.warning,
            message=f"翼面荷重 {wing_loading:.1f} N/m² > 60 N/m²(A-112)。HPAとして高翼面荷重です",
        ))
    if cl > 1.3:
        warnings.append(CalcWarning(
            code="CL_CRUISE_HIGH", severity=Severity.info,
            message=f"巡航CL = {cl:.2f} は高めです。失速余裕・抵抗増に注意",
        ))
    return warnings


def _collect_assumptions(spec: RequirementSpecInput) -> list[AssumptionRecord]:
    """使用した仮定の記録。ユーザー入力値は「入力値」として区別する(FR-021)。"""

    def origin(field: str) -> str:
        return "ユーザー入力値" if spec.user_specified(field) else "既定値(仮定)"

    return [
        AssumptionRecord(
            id="A-001", name="標準重力加速度", value=f"{STANDARD_GRAVITY_M_S2} m/s²",
            rationale="ISO 80000-3 定義値",
        ),
        AssumptionRecord(
            id="A-003", name="空気粘性係数", value=f"{AIR_VISCOSITY_PA_S} Pa·s",
            rationale="ISA海面 15°C(ICAO Doc 7488)",
        ),
        AssumptionRecord(
            id="A-002", name="空気密度", value=str(spec.air_density),
            rationale=f"{origin('air_density')}。ISA海面標準。実環境(気温・標高)で要補正",
        ),
        AssumptionRecord(
            id="A-101", name="設計翼幅", value=str(spec.wingspan_limit),
            rationale="翼幅制限値を設計翼幅として使用(誘導抗力最小化の定石)。Phase 2で設計変数化",
        ),
        AssumptionRecord(
            id="A-102", name="巡航揚力係数 CL_cruise", value=f"{spec.cl_cruise}",
            rationale=f"{origin('cl_cruise')}。翼型解析(Phase 2)で更新すること",
        ),
        AssumptionRecord(
            id="A-103", name="最大揚力係数 CL_max", value=f"{spec.cl_max}",
            rationale=f"{origin('cl_max')}。要XFLR5検証",
        ),
        AssumptionRecord(
            id="A-104", name="有害抗力係数 CD0", value=f"{spec.cd0}",
            rationale=f"{origin('cd0')}。主翼面積基準の全機寄生抗力。抵抗見積りで更新すること",
        ),
        AssumptionRecord(
            id="A-105", name="オズワルド効率 e", value=f"{spec.oswald_efficiency}",
            rationale=f"{origin('oswald_efficiency')}。翼幅方向分布解析で更新すること",
        ),
        AssumptionRecord(
            id="A-106", name="プロペラ効率 η_prop", value=f"{spec.propeller_efficiency}",
            rationale=f"{origin('propeller_efficiency')}。XROTOR(Phase 2)で更新すること",
        ),
        AssumptionRecord(
            id="A-107", name="駆動系効率 η_drive", value=f"{spec.drivetrain_efficiency}",
            rationale=f"{origin('drivetrain_efficiency')}。実測で更新すること",
        ),
        AssumptionRecord(
            id="A-108", name="平均翼弦の矩形近似", value="c̄ = S / b",
            rationale="初期サイジングの標準近似。テーパー導入(Phase 2)で更新",
        ),
    ]
