"""質量・重心管理(Step 9 / TASKS T-302)のドメインモデル。

機体座標系(A-135): 原点=機首先端、x=後方が正、y=右翼方向が正、z=上方が正。
部品は点質量として扱う(A-136。分布質量・自身の慣性モーメントは含まない)。
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from pbm.domain.quantities import Quantity, ensure_dimension


class MassCategory(StrEnum):
    wing_structure = "wing_structure"          # 主翼構造
    fuselage_structure = "fuselage_structure"  # 胴体・フレーム
    tail_structure = "tail_structure"          # 尾翼
    propulsion = "propulsion"                  # プロペラ・駆動系
    cockpit = "cockpit"                        # コックピット・フェアリング
    control = "control"                        # 操縦系統
    pilot = "pilot"                            # パイロット(機体質量目標には含まない)
    contest_equipment = "contest_equipment"    # 大会搭載機材(オンボードカメラ等。A-116)
    other = "other"


class MassSource(StrEnum):
    estimated = "estimated"  # 推定値
    measured = "measured"    # 実測値


class MassItemInput(BaseModel):
    """部品1点の質量情報。"""

    name: str = Field(min_length=1, max_length=200)
    category: MassCategory = MassCategory.other
    mass: Quantity
    position_x: Quantity = Quantity(value=0.0, unit="m")
    position_y: Quantity = Quantity(value=0.0, unit="m")
    position_z: Quantity = Quantity(value=0.0, unit="m")
    material: str = Field(default="", max_length=200)
    source: MassSource = MassSource.estimated
    uncertainty: Quantity | None = None  # 質量の不確かさ(±)
    owner: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def _validate(self) -> MassItemInput:
        ensure_dimension(self.mass, "[mass]", field_name="mass")
        mass_si = self.mass.magnitude_si
        if not (0.0005 <= mass_si <= 200.0):
            raise ValueError(
                f"mass: SI値 {mass_si:g} kg は許容範囲 0.0005–200 kg を外れています"
                f"(入力: {self.mass})"
            )
        for axis in ("position_x", "position_y", "position_z"):
            q: Quantity = getattr(self, axis)
            ensure_dimension(q, "[length]", field_name=axis)
            if abs(q.magnitude_si) > 40.0:
                raise ValueError(f"{axis}: |SI値| {q.magnitude_si:g} m が40 mを超えています")
        if self.uncertainty is not None:
            ensure_dimension(self.uncertainty, "[mass]", field_name="uncertainty")
            if self.uncertainty.magnitude_si < 0:
                raise ValueError(f"uncertainty: 0以上が必要です(入力: {self.uncertainty})")
        return self


class MassItem(MassItemInput):
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime
