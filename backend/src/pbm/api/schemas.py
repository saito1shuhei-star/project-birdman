"""API入出力スキーマ(API_SPEC.md)。ドメインモデルを直接使えるものは再利用する。"""

from datetime import datetime

from pydantic import BaseModel, Field

from pbm.adapters.base import ExecutionMode, ResultStatus, SolverExecution
from pbm.domain.aero_analysis import AeroAnalysisOutput, AeroAnalysisRequest
from pbm.domain.optimization import DesignSweepOutput, DesignSweepRequest
from pbm.domain.planform import WingPlanformInput
from pbm.domain.quantities import Quantity
from pbm.domain.requirements import RequirementSpecInput
from pbm.domain.stability import StabilityOutput
from pbm.domain.states import DesignState
from pbm.domain.structure import SparAnalysisOutput, SparAnalysisRequest


class HealthOut(BaseModel):
    status: str
    version: str


class RequirementSpecOut(BaseModel):
    id: str
    project_id: str
    revision: int
    created_at: datetime
    spec: RequirementSpecInput


class SizingRunSummary(BaseModel):
    """一覧表示用の要約(全文は GET /api/sizing-runs/{id})。"""

    id: str
    requirement_revision: int
    input_hash: str
    execution_mode: ExecutionMode
    result_status: ResultStatus
    created_at: datetime
    wing_area: Quantity
    required_pilot_power: Quantity
    power_margin: Quantity
    warning_count: int


class TransitionRequest(BaseModel):
    to: DesignState
    actor: str | None = Field(default=None, max_length=200)
    comment: str | None = Field(default=None, max_length=2000)


class SweepRunOut(BaseModel):
    """設計スイープ実行(analysis_runs保存分。T-401)。"""

    id: str
    project_id: str
    requirement_revision: int | None
    input_hash: str
    request: "DesignSweepRequest"
    outputs: "DesignSweepOutput"
    execution: SolverExecution
    created_at: datetime


class ApprovalOut(BaseModel):
    """状態遷移の監査ログ1件(T-304)。actorがNoneの遷移は自動遷移。"""

    id: str
    project_id: str
    from_state: DesignState
    to_state: DesignState
    actor: str | None
    comment: str | None
    created_at: datetime


class TransitionsOut(BaseModel):
    """現在状態と許可される遷移先(DOMAIN_MODEL.md §3)。"""

    current: DesignState
    allowed: list[DesignState]
    actor_required: list[DesignState]  # 遷移に承認者名が必須の状態


class StabilityRunOut(BaseModel):
    """静安定解析実行(analysis_runs保存分)。requestは尾翼構成+文脈(翼幾何・重心)。"""

    id: str
    project_id: str
    planform_revision: int | None
    requirement_revision: int | None
    input_hash: str
    request: dict
    outputs: "StabilityOutput"
    execution: SolverExecution
    created_at: datetime


class SparRunOut(BaseModel):
    """主桁梁解析実行(analysis_runs保存分)。"""

    id: str
    project_id: str
    input_hash: str
    request: "SparAnalysisRequest"
    outputs: "SparAnalysisOutput"
    execution: SolverExecution
    created_at: datetime


class WingPlanformOut(BaseModel):
    id: str
    project_id: str
    revision: int
    created_at: datetime
    planform: WingPlanformInput
    derived: dict[str, Quantity]  # span / area / aspect_ratio / mean_chord / taper_ratio


class AeroAnalysisRunOut(BaseModel):
    id: str
    project_id: str
    solver_name: str
    planform_revision: int | None
    requirement_revision: int | None
    input_hash: str
    request: AeroAnalysisRequest
    outputs: AeroAnalysisOutput
    execution: SolverExecution
    created_at: datetime
