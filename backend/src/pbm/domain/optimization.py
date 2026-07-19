"""設計最適化(Step 11 / TASKS T-401 MVP)のドメインモデル。

設計変数・制約・評価関数を分離する(PROJECT_BRIEF §4 Step 11):
- 設計変数: 本MVPでは翼幅・巡航速度・巡航CLのグリッドスイープ
- 制約: 初期サイジングのviolation警告(出力超過等)=不可行として扱う
- 評価関数: 必要出力の最小化 × 揚抗比の最大化の2目的(パレート抽出)

**PBMは最適解を自動採用しない。** 候補一覧とパレートフラグを提示し、
採用判断は人間が行う(PROJECT_BRIEF §2「最適化結果の採用」)。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from pbm.domain.quantities import Quantity
from pbm.domain.results import AssumptionRecord, CalcWarning

_MAX_EVALUATIONS = 200  # グリッド評価数の上限(応答サイズ・計算時間の管理)

# 変数ごとの許容範囲(SI)。RequirementSpecInputの検証範囲と一致させる
_VARIABLE_BOUNDS: dict[str, tuple[float, float]] = {
    "wingspan": (3.0, 45.0),        # m
    "cruise_speed": (3.0, 20.0),    # m/s
    "cl_cruise": (0.1, 2.5),        # −
}


class SweepVariable(StrEnum):
    wingspan = "wingspan"            # 翼幅(wingspan_limitを置換)
    cruise_speed = "cruise_speed"    # 巡航速度(target_cruise_speedを置換)
    cl_cruise = "cl_cruise"          # 巡航揚力係数


class VariableRange(BaseModel):
    """設計変数1つの掃引範囲(値はSI: m / m/s / 無次元)。"""

    variable: SweepVariable
    minimum: float
    maximum: float
    steps: int = Field(ge=2, le=15)

    @model_validator(mode="after")
    def _validate(self) -> VariableRange:
        lo, hi = _VARIABLE_BOUNDS[self.variable.value]
        if not (lo <= self.minimum < self.maximum <= hi):
            raise ValueError(
                f"{self.variable}: 範囲 {self.minimum}–{self.maximum} が不正です"
                f"(要 {lo} ≤ min < max ≤ {hi}。単位はSI)"
            )
        return self

    def values(self) -> list[float]:
        step = (self.maximum - self.minimum) / (self.steps - 1)
        return [self.minimum + i * step for i in range(self.steps)]


class DesignSweepRequest(BaseModel):
    variables: list[VariableRange] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def _validate(self) -> DesignSweepRequest:
        names = [v.variable for v in self.variables]
        if len(set(names)) != len(names):
            raise ValueError("同じ設計変数を複数指定できません")
        total = 1
        for v in self.variables:
            total *= v.steps
        if total > _MAX_EVALUATIONS:
            raise ValueError(f"評価数 {total} が上限 {_MAX_EVALUATIONS} を超えています")
        return self


class SweepCandidate(BaseModel):
    """設計案1件の評価結果。"""

    values: dict[str, float]              # 変数名 → SI値
    feasible: bool                        # violation警告なし
    violation_codes: list[str] = Field(default_factory=list)
    pareto: bool = False                  # 可行案のパレートフロントに含まれるか
    required_pilot_power: Quantity
    lift_to_drag: Quantity
    wing_area: Quantity
    stall_speed: Quantity
    power_margin: Quantity


class DesignSweepOutput(BaseModel):
    candidates: list[SweepCandidate]
    evaluated: int
    feasible_count: int
    pareto_count: int
    assumptions: list[AssumptionRecord] = Field(default_factory=list)
    warnings: list[CalcWarning] = Field(default_factory=list)
