"""質量特性の計算(Step 9 / T-302)。純粋関数。

- 総質量        m_total = Σmᵢ
- 重心          r_cg = Σmᵢrᵢ / Σmᵢ
- 慣性モーメント I = Σmᵢ·dᵢ²(重心まわり、点質量近似 A-136。部品自身の慣性は含まない)
  Ixx = Σm(Δy²+Δz²), Iyy = Σm(Δx²+Δz²), Izz = Σm(Δx²+Δy²)
- カテゴリ別内訳、機体質量目標(パイロット除く)との差
出典: 質点系の力学の定義式(標準力学教科書)。
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from pbm.domain.errors import CalculationError
from pbm.domain.mass_item import MassCategory, MassItemInput, MassSource
from pbm.domain.quantities import Quantity
from pbm.domain.results import AssumptionRecord, CalcWarning, FormulaRecord, Severity

_SOURCE = "質点系の定義式(点質量近似 A-136)"


class CategoryBreakdown(BaseModel):
    category: MassCategory
    mass: Quantity
    fraction: float  # 総質量に対する割合
    item_count: int


class MassPropertiesOutput(BaseModel):
    quantities: dict[str, Quantity]
    breakdown: list[CategoryBreakdown]
    formulas: list[FormulaRecord] = Field(default_factory=list)
    assumptions: list[AssumptionRecord] = Field(default_factory=list)
    warnings: list[CalcWarning] = Field(default_factory=list)
    estimated_item_count: int = 0
    measured_item_count: int = 0


def compute_mass_properties(
    items: list[MassItemInput],
    airframe_mass_target: Quantity | None = None,
) -> MassPropertiesOutput:
    """部品台帳から総質量・重心・慣性モーメント・内訳を計算する。

    airframe_mass_target(要求仕様)を渡すと、パイロットカテゴリを除いた
    機体質量と目標との差を算出し、超過時は警告を付与する。
    """
    if not items:
        raise CalculationError("質量部品が0件のため質量特性を計算できません")

    masses = [i.mass.magnitude_si for i in items]
    xs = [i.position_x.magnitude_si for i in items]
    ys = [i.position_y.magnitude_si for i in items]
    zs = [i.position_z.magnitude_si for i in items]

    total = sum(masses)
    cg_x = sum(m * x for m, x in zip(masses, xs, strict=True)) / total
    cg_y = sum(m * y for m, y in zip(masses, ys, strict=True)) / total
    cg_z = sum(m * z for m, z in zip(masses, zs, strict=True)) / total

    ixx = sum(
        m * ((y - cg_y) ** 2 + (z - cg_z) ** 2)
        for m, y, z in zip(masses, ys, zs, strict=True)
    )
    iyy = sum(
        m * ((x - cg_x) ** 2 + (z - cg_z) ** 2)
        for m, x, z in zip(masses, xs, zs, strict=True)
    )
    izz = sum(
        m * ((x - cg_x) ** 2 + (y - cg_y) ** 2)
        for m, x, y in zip(masses, xs, ys, strict=True)
    )

    airframe_mass = sum(
        m for m, i in zip(masses, items, strict=True) if i.category is not MassCategory.pilot
    )

    quantities: dict[str, Quantity] = {
        "total_mass": Quantity(value=total, unit="kg"),
        "airframe_mass": Quantity(value=airframe_mass, unit="kg"),
        "cg_x": Quantity(value=cg_x, unit="m"),
        "cg_y": Quantity(value=cg_y, unit="m"),
        "cg_z": Quantity(value=cg_z, unit="m"),
        "inertia_xx": Quantity(value=ixx, unit="kg*m^2"),
        "inertia_yy": Quantity(value=iyy, unit="kg*m^2"),
        "inertia_zz": Quantity(value=izz, unit="kg*m^2"),
    }

    formulas = [
        FormulaRecord(
            symbol="m_total", name="総質量", expression="m_total = Σmᵢ",
            substitutions={"部品数": f"{len(items)}"},
            result=quantities["total_mass"], source=_SOURCE,
        ),
        FormulaRecord(
            symbol="x_cg", name="重心x座標", expression="x_cg = Σ(mᵢ·xᵢ) / Σmᵢ",
            substitutions={"m_total": f"{total:.6g} kg"},
            result=quantities["cg_x"], source=_SOURCE + "。座標系はA-135(機首原点、x後方+)",
        ),
        FormulaRecord(
            symbol="Iyy", name="ピッチ慣性モーメント(重心まわり)",
            expression="Iyy = Σmᵢ·(Δxᵢ² + Δzᵢ²)",
            substitutions={"x_cg": f"{cg_x:.6g} m", "z_cg": f"{cg_z:.6g} m"},
            result=quantities["inertia_yy"], source=_SOURCE,
        ),
    ]

    warnings: list[CalcWarning] = []
    if airframe_mass_target is not None:
        target = airframe_mass_target.magnitude_si
        delta = airframe_mass - target
        quantities["airframe_mass_target"] = Quantity(value=target, unit="kg")
        quantities["airframe_mass_delta"] = Quantity(value=delta, unit="kg")
        if delta > 0:
            warnings.append(CalcWarning(
                code="MASS_OVER_TARGET", severity=Severity.violation,
                message=(
                    f"機体質量(パイロット除く) {airframe_mass:.2f} kg が"
                    f"目標 {target:.2f} kg を {delta:.2f} kg 超過しています"
                ),
            ))
        elif delta > -0.05 * target:
            warnings.append(CalcWarning(
                code="MASS_MARGIN_LOW", severity=Severity.warning,
                message=f"機体質量の目標余裕が5%未満です(残り {-delta:.2f} kg)",
            ))

    estimated = sum(1 for i in items if i.source is MassSource.estimated)
    measured = len(items) - estimated
    if estimated == len(items):
        warnings.append(CalcWarning(
            code="ALL_ESTIMATED", severity=Severity.info,
            message="全部品が推定値です。製作の進行に応じて実測値へ更新してください",
        ))
    if not any(i.category is MassCategory.pilot for i in items):
        warnings.append(CalcWarning(
            code="NO_PILOT_ITEM", severity=Severity.info,
            message="パイロットが登録されていません。全機重心の評価にはパイロットの登録が必要です",
        ))
    if not any(i.category is MassCategory.contest_equipment for i in items):
        warnings.append(CalcWarning(
            code="NO_CONTEST_EQUIPMENT", severity=Severity.info,
            message=(
                "大会搭載機材(オンボードカメラ等)が未登録です。"
                "搭載同意義務があるため質量を見込むこと(A-116)"
            ),
        ))

    breakdown: list[CategoryBreakdown] = []
    for cat in MassCategory:
        cat_items = [(m, i) for m, i in zip(masses, items, strict=True) if i.category is cat]
        if not cat_items:
            continue
        cat_mass = sum(m for m, _ in cat_items)
        breakdown.append(CategoryBreakdown(
            category=cat,
            mass=Quantity(value=cat_mass, unit="kg"),
            fraction=cat_mass / total,
            item_count=len(cat_items),
        ))
    breakdown.sort(key=lambda b: b.mass.value, reverse=True)

    for name, q in quantities.items():
        if not math.isfinite(q.value):
            raise CalculationError(f"計算結果が非有限値です: {name} = {q.value}")

    assumptions = [
        AssumptionRecord(
            id="A-135", name="機体座標系",
            value="原点=機首先端、x=後方+、y=右+、z=上+",
            rationale="部品座標・重心の共通基準。平面形・安定性計算と共通",
        ),
        AssumptionRecord(
            id="A-136", name="点質量近似",
            value="部品自身の慣性モーメント・分布は無視",
            rationale="台帳MVPの近似。大型部品(主翼等)は分割登録で精度を上げること",
        ),
    ]

    return MassPropertiesOutput(
        quantities=quantities,
        breakdown=breakdown,
        formulas=formulas,
        assumptions=assumptions,
        warnings=warnings,
        estimated_item_count=estimated,
        measured_item_count=measured,
    )
