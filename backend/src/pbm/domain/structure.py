"""構造設計(Step 8 / TASKS T-301)のドメインモデル。

**荷重倍数・許容応力・要求安全率・材料物性に既定値は設けない。**
これらは人間(チーム)が確定する事項である(PROJECT_BRIEF §2, §10)。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from pbm.domain.quantities import Quantity, ensure_dimension
from pbm.domain.results import AssumptionRecord, CalcWarning, FormulaRecord


class LiftDistribution(StrEnum):
    elliptic = "elliptic"  # 楕円分布(誘導抗力最小の理想分布)
    uniform = "uniform"    # 一様分布(保守側: 翼端荷重が大きい)


class SparAnalysisRequest(BaseModel):
    """主桁の簡易梁解析の入力。

    モデル: 半翼を翼根固定の片持ち梁とし、揚力分布による曲げを評価する。
    断面は円管(外径D・肉厚t、翼幅方向一定)。
    load_factor / allowable_stress / required_safety_factor は既定値なし(人間が確定)。
    """

    half_span: Quantity
    load_factor: float = Field(gt=0, le=10.0)          # 荷重倍数 n(既定値なし)
    total_mass: Quantity                                # 全備質量(要求仕様から転記可)
    lift_distribution: LiftDistribution = LiftDistribution.elliptic
    spar_outer_diameter: Quantity
    spar_wall_thickness: Quantity
    elastic_modulus: Quantity                           # 材料ヤング率 E(既定値なし)
    allowable_stress: Quantity                          # 許容応力(既定値なし)
    required_safety_factor: float = Field(gt=0, le=20.0)  # 要求安全率(既定値なし)
    stations: int = Field(default=101, ge=11, le=1001)  # 数値積分の分割数+1

    @model_validator(mode="after")
    def _validate(self) -> SparAnalysisRequest:
        checks: list[tuple[str, str, float, float]] = [
            ("half_span", "[length]", 1.5, 22.5),
            ("total_mass", "[mass]", 35.0, 300.0),
            ("spar_outer_diameter", "[length]", 0.01, 0.5),
            ("spar_wall_thickness", "[length]", 0.0002, 0.1),
            ("elastic_modulus", "[pressure]", 1e9, 1e12),
            ("allowable_stress", "[pressure]", 1e6, 5e9),
        ]
        for name, dim, lo, hi in checks:
            q: Quantity = getattr(self, name)
            ensure_dimension(q, dim, field_name=name)
            si = q.magnitude_si
            if not (lo <= si <= hi):
                raise ValueError(
                    f"{name}: SI値 {si:g} は許容範囲 {lo:g}–{hi:g} を外れています(入力: {q})"
                )
        d = self.spar_outer_diameter.magnitude_si
        t = self.spar_wall_thickness.magnitude_si
        if 2.0 * t >= d:
            raise ValueError(
                f"spar_wall_thickness: 肉厚×2 ({2*t:g} m) が外径 ({d:g} m) 以上です"
                "(円管が成立しない)"
            )
        return self


class SparStation(BaseModel):
    """翼幅方向1ステーションの断面力・応力・たわみ。"""

    y: Quantity                 # 翼根からの距離
    shear: Quantity             # せん断力 V
    bending_moment: Quantity    # 曲げモーメント M
    bending_stress: Quantity    # 曲げ応力 σ
    deflection: Quantity        # たわみ δ


class SparAnalysisOutput(BaseModel):
    quantities: dict[str, Quantity]
    stations: list[SparStation]
    formulas: list[FormulaRecord] = Field(default_factory=list)
    assumptions: list[AssumptionRecord] = Field(default_factory=list)
    warnings: list[CalcWarning] = Field(default_factory=list)
