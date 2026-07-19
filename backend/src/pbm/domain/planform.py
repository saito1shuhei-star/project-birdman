"""主翼平面形状のパラメトリックモデル(Step 4 / TASKS T-204)。

- 左右対称翼を前提とし、セクションは片翼(y ≥ 0、翼根 y=0 から翼端へ)で定義する
- 翼面積はセクション間の翼弦線形補間による台形積分(×2 で全翼)
- 上反角・後退角・桁位置はPhase 2後半で追加予定(現状は上面視の平面形のみ)
- プラットホーム手すりの翼端クリアランス確認(A-115)は上反角導入後に実装する
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from pbm.domain.quantities import Quantity, ensure_dimension


class WingSection(BaseModel):
    """翼幅方向1ステーションの定義。"""

    spanwise_position: Quantity          # 翼根(機体中心線)からの距離 y [length]
    chord: Quantity                      # 翼弦長 [length]
    twist_deg: float = Field(default=0.0, ge=-10.0, le=10.0)  # ねじり角(幾何、正=前縁上げ)
    airfoil: str = Field(default="unspecified", max_length=100)

    @model_validator(mode="after")
    def _validate(self) -> WingSection:
        ensure_dimension(self.spanwise_position, "[length]", field_name="spanwise_position")
        ensure_dimension(self.chord, "[length]", field_name="chord")
        if self.spanwise_position.magnitude_si < 0:
            raise ValueError(f"spanwise_position: 0以上が必要です(入力: {self.spanwise_position})")
        chord_si = self.chord.magnitude_si
        if not (0.05 <= chord_si <= 3.0):
            raise ValueError(
                f"chord: SI値 {chord_si:g} m は許容範囲 0.05–3.0 m を外れています"
                f"(入力: {self.chord})"
            )
        return self


class WingPlanformInput(BaseModel):
    """主翼平面形の入力。セクションは y 昇順・先頭は翼根(y=0)であること。"""

    sections: list[WingSection] = Field(min_length=2, max_length=50)

    @model_validator(mode="after")
    def _validate_sections(self) -> WingPlanformInput:
        ys = [s.spanwise_position.magnitude_si for s in self.sections]
        if abs(ys[0]) > 1e-9:
            raise ValueError(f"先頭セクションは翼根(y=0)である必要があります(先頭 y={ys[0]:g} m)")
        for i in range(1, len(ys)):
            if ys[i] <= ys[i - 1]:
                raise ValueError(
                    f"セクションはy昇順である必要があります(index {i}: "
                    f"{ys[i]:g} m ≤ {ys[i-1]:g} m)"
                )
        half_span = ys[-1]
        if not (1.5 <= half_span <= 22.5):  # 全翼幅 3–45 m(CALCULATION_SPEC §2と整合)
            raise ValueError(
                f"半翼幅 {half_span:g} m は許容範囲 1.5–22.5 m(全翼幅3–45 m)を外れています"
            )
        return self

    # --- 導出量(すべてSI。式はDOMAIN_MODEL.md / 台形積分) ---

    @property
    def half_span_si(self) -> float:
        return self.sections[-1].spanwise_position.magnitude_si

    @property
    def span_si(self) -> float:
        """全翼幅 b = 2·y_tip(左右対称)。"""
        return 2.0 * self.half_span_si

    @property
    def area_si(self) -> float:
        """翼面積 S = 2·∫c(y)dy(セクション間は線形補間 → 台形積分)。"""
        total = 0.0
        for i in range(1, len(self.sections)):
            y0 = self.sections[i - 1].spanwise_position.magnitude_si
            y1 = self.sections[i].spanwise_position.magnitude_si
            c0 = self.sections[i - 1].chord.magnitude_si
            c1 = self.sections[i].chord.magnitude_si
            total += (y1 - y0) * (c0 + c1) / 2.0
        return 2.0 * total

    @property
    def aspect_ratio(self) -> float:
        return self.span_si**2 / self.area_si

    @property
    def mean_chord_si(self) -> float:
        return self.area_si / self.span_si

    @property
    def taper_ratio(self) -> float:
        """テーパー比 λ = 翼端翼弦 / 翼根翼弦。"""
        return self.sections[-1].chord.magnitude_si / self.sections[0].chord.magnitude_si

    def derived_quantities(self) -> dict[str, Quantity]:
        """導出量を単位付きで返す(APIレスポンス・レポート用)。"""
        return {
            "span": Quantity(value=self.span_si, unit="m"),
            "area": Quantity(value=self.area_si, unit="m^2"),
            "aspect_ratio": Quantity(value=self.aspect_ratio, unit="dimensionless"),
            "mean_chord": Quantity(value=self.mean_chord_si, unit="m"),
            "taper_ratio": Quantity(value=self.taper_ratio, unit="dimensionless"),
        }
