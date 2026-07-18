"""空力解析(Step 5)のドメインモデル。

Phase 2で本格実装するXFLR5連携の入出力形式。WingPlanform(翼平面形状、TASKS T-204)は
未実装のため、現時点ではRequirementSpecInput/SizingOutput相当の簡易パラメータのみを
入力とする。翼型固有の詳細形状(翼型座標、テーパー、ねじり分布等)はここでは扱わない。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from pbm.domain.results import AssumptionRecord, CalcWarning, FormulaRecord


class AeroAnalysisRequest(BaseModel):
    """空力解析リクエスト(簡易版。WingPlanform実装後に置き換え予定)。"""

    airfoil_name: str = Field(default="unspecified", max_length=100)
    aspect_ratio: float = Field(gt=0)
    oswald_efficiency: float = Field(gt=0, le=1.0)
    parasite_drag_coefficient: float = Field(ge=0)
    cl_max: float = Field(gt=0)
    alpha_min_deg: float = -4.0
    alpha_max_deg: float = 12.0
    alpha_step_deg: float = Field(default=1.0, gt=0)


class AeroPolarPoint(BaseModel):
    """迎角1点あたりの空力係数(揚力係数・抗力係数・モーメント係数は無次元)。"""

    alpha_deg: float
    cl: float
    cd: float
    cm: float
    stalled: bool = False


class AeroAnalysisOutput(BaseModel):
    """空力解析結果(Step 5取得対象: CL, CD, Cm, L/D, 迎角特性)。"""

    polar: list[AeroPolarPoint]
    max_lift_to_drag: float
    cl_at_max_lift_to_drag: float
    formulas: list[FormulaRecord] = Field(default_factory=list)
    assumptions: list[AssumptionRecord] = Field(default_factory=list)
    warnings: list[CalcWarning] = Field(default_factory=list)
