"""プロペラ解析(Step 6)のドメインモデル。

Phase 2で本格実装するXROTOR連携の入出力形式。モック(運動量理論)は
ブレード形状(枚数・コード分布・ねじり分布)を使用しないが、実解析(real)への
移行を見据えて主要形状パラメータを受理・記録する。
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from pbm.domain.quantities import Quantity, ensure_dimension
from pbm.domain.results import AssumptionRecord, CalcWarning, FormulaRecord

# フィールド → (期待次元, SI下限, SI上限)
_QUANTITY_CONSTRAINTS: dict[str, tuple[str, float | None, float | None]] = {
    "flight_speed": ("[length] / [time]", 3.0, 20.0),
    "input_power": ("[power]", 50.0, 1500.0),
    "diameter": ("[length]", 0.3, 6.0),
    "hub_diameter": ("[length]", 0.0, None),
    "air_density": ("[mass] / [length] ** 3", 0.9, 1.4),
    "rotation_speed": ("1 / [time]", 0.0, None),
}


class PropAnalysisRequest(BaseModel):
    """プロペラ解析リクエスト。

    モック(運動量理論)が使用するのは flight_speed / input_power / diameter /
    air_density のみ。blade_count・hub_diameter・rotation_speed は実解析(Phase 2)用に
    記録される(モックでは未使用である旨を警告に明示する)。
    """

    flight_speed: Quantity
    input_power: Quantity
    diameter: Quantity
    air_density: Quantity = Quantity(value=1.225, unit="kg/m^3")
    blade_count: int = Field(default=2, ge=1, le=6)
    hub_diameter: Quantity | None = None
    rotation_speed: Quantity | None = None  # 例 {"value": 120, "unit": "rpm"}

    @model_validator(mode="after")
    def _validate_quantities(self) -> PropAnalysisRequest:
        for name, (dim, lo, hi) in _QUANTITY_CONSTRAINTS.items():
            q: Quantity | None = getattr(self, name)
            if q is None:
                continue
            ensure_dimension(q, dim, field_name=name)
            si = q.magnitude_si
            if si <= 0:
                raise ValueError(f"{name}: 正の値が必要です(入力: {q})")
            if lo is not None and si < lo:
                raise ValueError(f"{name}: SI値 {si:g} は下限 {lo:g} を下回ります(入力: {q})")
            if hi is not None and si > hi:
                raise ValueError(f"{name}: SI値 {si:g} は上限 {hi:g} を超えます(入力: {q})")
        if self.hub_diameter is not None:
            if self.hub_diameter.magnitude_si >= self.diameter.magnitude_si:
                raise ValueError(
                    f"hub_diameter ({self.hub_diameter}) は diameter ({self.diameter}) "
                    "より小さい必要があります"
                )
        return self


class PropAnalysisOutput(BaseModel):
    """プロペラ解析結果(Step 6出力対象: 推力・必要動力・推進効率 ほか)。"""

    quantities: dict[str, Quantity]
    formulas: list[FormulaRecord] = Field(default_factory=list)
    assumptions: list[AssumptionRecord] = Field(default_factory=list)
    warnings: list[CalcWarning] = Field(default_factory=list)
