"""要求仕様 RequirementSpec(Step 2 / Phase 1 サブセット)。

- 物理量はQuantity(値+単位)で受理し、次元と妥当範囲をここで検証する(FR-011, FR-012)
- 無次元係数はfloat + 範囲制約(REQUIREMENTS FR-011 の明示的例外)
- 既定値の根拠は ASSUMPTIONS.md(A-002, A-102〜A-107)
- 妥当範囲の根拠は CALCULATION_SPEC.md §2 / ASSUMPTIONS A-110
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from pbm.domain.quantities import Quantity, ensure_dimension

# フィールド → (期待次元, SI下限, SI上限)。上下限はSI基本単位系の値(CALCULATION_SPEC §2)
_QUANTITY_CONSTRAINTS: dict[str, tuple[str, float | None, float | None]] = {
    "pilot_mass": ("[mass]", 30.0, 150.0),
    "airframe_mass_target": ("[mass]", 5.0, 150.0),
    "pilot_power_sustained": ("[power]", 50.0, 1500.0),
    "pilot_power_max": ("[power]", 0.0, None),
    "target_cruise_speed": ("[length] / [time]", 3.0, 20.0),
    "target_distance": ("[length]", 0.0, None),
    "wingspan_limit": ("[length]", 3.0, 45.0),
    "air_density": ("[mass] / [length] ** 3", 0.9, 1.4),
}


class RequirementSpecInput(BaseModel):
    """API境界で受理する要求仕様。検証済みであることがこの型の意味。"""

    pilot_mass: Quantity
    airframe_mass_target: Quantity
    pilot_power_sustained: Quantity
    pilot_power_max: Quantity | None = None
    target_cruise_speed: Quantity
    target_distance: Quantity | None = None
    wingspan_limit: Quantity
    # 既定値: ISA海面標準(A-002)
    air_density: Quantity = Quantity(value=1.225, unit="kg/m^3")

    # 無次元係数。既定値の根拠は ASSUMPTIONS A-102〜A-107
    cl_cruise: float = Field(default=1.0, ge=0.1, le=2.5)
    cl_max: float = Field(default=1.4, ge=0.5, le=3.0)
    cd0: float = Field(default=0.020, ge=0.005, le=0.1)
    oswald_efficiency: float = Field(default=0.90, ge=0.5, le=1.0)
    propeller_efficiency: float = Field(default=0.80, ge=0.3, le=1.0)
    drivetrain_efficiency: float = Field(default=0.95, ge=0.3, le=1.0)

    @model_validator(mode="after")
    def _validate_quantities(self) -> RequirementSpecInput:
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
        if self.cl_max <= self.cl_cruise:
            raise ValueError(
                f"cl_max ({self.cl_max}) は cl_cruise ({self.cl_cruise}) より大きい必要があります"
            )
        return self

    def user_specified(self, field: str) -> bool:
        """フィールドがユーザー入力か(False=既定値を使用)。仮定記録に用いる。"""
        return field in self.model_fields_set
