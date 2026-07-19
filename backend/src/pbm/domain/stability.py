"""静安定・尾翼サイジング(Step 7 / TASKS T-303)のドメインモデル。

座標系はA-135(機首原点、x後方+)。翼のMAC・面積は平面形(Step 4)から、
重心は質量台帳(Step 9)から取得する。
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from pbm.domain.quantities import Quantity, ensure_dimension
from pbm.domain.results import AssumptionRecord, CalcWarning, FormulaRecord


class StabilityRequest(BaseModel):
    """静安定解析の入力(尾翼構成)。

    wing_ac_position: 主翼空力中心の機体x座標(通常はMAC 25%位置。機首原点)
    tail_arm: 主翼ACから水平尾翼ACまでの距離 l_t
    """

    horizontal_tail_area: Quantity
    tail_arm: Quantity
    wing_ac_position: Quantity
    tail_aspect_ratio: float = Field(gt=1.0, le=30.0)
    # 既定値の根拠: A-130(尾翼オズワルド効率)、A-132(尾翼効率η_t)
    tail_oswald_efficiency: float = Field(default=0.9, ge=0.5, le=1.0)
    tail_efficiency: float = Field(default=0.9, ge=0.5, le=1.0)

    @model_validator(mode="after")
    def _validate(self) -> StabilityRequest:
        ensure_dimension(self.horizontal_tail_area, "[length] ** 2", "horizontal_tail_area")
        ensure_dimension(self.tail_arm, "[length]", "tail_arm")
        ensure_dimension(self.wing_ac_position, "[length]", "wing_ac_position")
        st = self.horizontal_tail_area.magnitude_si
        if not (0.2 <= st <= 20.0):
            raise ValueError(f"horizontal_tail_area: SI値 {st:g} m² は範囲 0.2–20 m² 外です")
        lt = self.tail_arm.magnitude_si
        if not (0.5 <= lt <= 15.0):
            raise ValueError(f"tail_arm: SI値 {lt:g} m は範囲 0.5–15 m 外です")
        xac = self.wing_ac_position.magnitude_si
        if not (0.0 <= xac <= 20.0):
            raise ValueError(f"wing_ac_position: SI値 {xac:g} m は範囲 0–20 m 外です")
        return self


class StabilityOutput(BaseModel):
    quantities: dict[str, Quantity]
    formulas: list[FormulaRecord] = Field(default_factory=list)
    assumptions: list[AssumptionRecord] = Field(default_factory=list)
    warnings: list[CalcWarning] = Field(default_factory=list)
