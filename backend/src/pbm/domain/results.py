"""計算・解析結果のドメインモデル(DOMAIN_MODEL.md §2)。"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from pbm.adapters.base import SolverExecution
from pbm.domain.quantities import Quantity
from pbm.domain.requirements import RequirementSpecInput


class Severity(StrEnum):
    info = "info"
    warning = "warning"
    violation = "violation"


class CalcWarning(BaseModel):
    code: str
    severity: Severity
    message: str


class FormulaRecord(BaseModel):
    """使用した計算式の記録(FR-021)。"""

    symbol: str                       # 例 "S"
    name: str                         # 例 "必要翼面積"
    expression: str                   # 例 "S = W / (q · CL_cruise)"
    substitutions: dict[str, str]     # 記号 → 代入値(単位付き文字列)
    result: Quantity
    source: str                       # 出典 or ASSUMPTIONSのID


class AssumptionRecord(BaseModel):
    """使用した仮定の記録(FR-021)。idはASSUMPTIONS.mdのID。"""

    id: str
    name: str
    value: str
    rationale: str


class SizingOutput(BaseModel):
    quantities: dict[str, Quantity]
    formulas: list[FormulaRecord] = Field(default_factory=list)
    assumptions: list[AssumptionRecord] = Field(default_factory=list)
    warnings: list[CalcWarning] = Field(default_factory=list)


class SizingRunResult(BaseModel):
    """保存されるサイジング実行1回分(トレーサビリティ: ARCHITECTURE §5)。"""

    id: str
    project_id: str
    requirement_spec_id: str
    requirement_revision: int
    input_hash: str
    inputs_snapshot: RequirementSpecInput
    outputs: SizingOutput
    execution: SolverExecution
    created_at: datetime
