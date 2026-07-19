"""APIルート(API_SPEC.md)。計算式・状態遷移規則はここに書かない(ARCHITECTURE §2)。"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

import pbm
from pbm.adapters.base import SolverExecution
from pbm.api.schemas import (
    AeroAnalysisRunOut,
    HealthOut,
    RequirementSpecOut,
    SizingRunSummary,
    TransitionRequest,
    WingPlanformOut,
)
from pbm.domain.aero_analysis import AeroAnalysisOutput, AeroAnalysisRequest
from pbm.domain.entities import Project, ProjectCreate
from pbm.domain.errors import MissingRequirementError, NotFoundError
from pbm.domain.planform import WingPlanformInput
from pbm.domain.requirements import RequirementSpecInput
from pbm.domain.results import SizingRunResult
from pbm.domain.states import DesignState
from pbm.persistence import repository
from pbm.reports.html_report import render_sizing_report
from pbm.workflow.aero_service import build_aero_request, execute_aero_analysis
from pbm.workflow.sizing_service import execute_sizing
from pbm.workflow.states import ensure_approved_for_manufacturing, validate_transition

logger = logging.getLogger("pbm.api")

router = APIRouter(prefix="/api")


def get_session(request: Request) -> Iterator[Session]:
    factory = request.app.state.session_factory
    with factory() as session:
        yield session


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", version=pbm.__version__)


# --- プロジェクト ---


@router.post("/projects", response_model=Project, status_code=201)
def create_project(data: ProjectCreate, session: Session = Depends(get_session)) -> Project:
    return repository.create_project(session, data)


@router.get("/projects", response_model=list[Project])
def list_projects(session: Session = Depends(get_session)) -> list[Project]:
    return repository.list_projects(session)


@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: str, session: Session = Depends(get_session)) -> Project:
    return repository.get_project(session, project_id)


# --- 要求仕様 ---


def _requirement_out(row) -> RequirementSpecOut:  # noqa: ANN001
    return RequirementSpecOut(
        id=row.id,
        project_id=row.project_id,
        revision=row.revision,
        created_at=datetime.fromisoformat(row.created_at),
        spec=RequirementSpecInput.model_validate(row.payload),
    )


@router.put("/projects/{project_id}/requirements", response_model=RequirementSpecOut)
def put_requirements(
    project_id: str, spec: RequirementSpecInput, session: Session = Depends(get_session)
) -> RequirementSpecOut:
    repository.save_requirements(session, project_id, spec)
    row = repository.latest_requirements_row(session, project_id)
    assert row is not None  # 直前に保存済み
    return _requirement_out(row)


@router.get("/projects/{project_id}/requirements", response_model=RequirementSpecOut)
def get_requirements(
    project_id: str, session: Session = Depends(get_session)
) -> RequirementSpecOut:
    repository.get_project(session, project_id)
    row = repository.latest_requirements_row(session, project_id)
    if row is None:
        # 未入力は「リソース不存在」として404(API_SPEC.md)
        raise NotFoundError(f"要求仕様が未入力です: project={project_id}")
    return _requirement_out(row)


@router.get(
    "/projects/{project_id}/requirements/history", response_model=list[RequirementSpecOut]
)
def requirements_history(
    project_id: str, session: Session = Depends(get_session)
) -> list[RequirementSpecOut]:
    repository.get_project(session, project_id)
    return [_requirement_out(r) for r in repository.requirements_history(session, project_id)]


# --- 初期サイジング ---


@router.post("/projects/{project_id}/sizing-runs", response_model=SizingRunResult, status_code=201)
def run_sizing(project_id: str, session: Session = Depends(get_session)) -> SizingRunResult:
    project = repository.get_project(session, project_id)
    row = repository.latest_requirements_row(session, project_id)
    if row is None:
        raise MissingRequirementError(
            f"要求仕様が未入力のためサイジングを実行できません: project={project_id}"
        )
    spec = RequirementSpecInput.model_validate(row.payload)
    outputs, execution = execute_sizing(spec)
    result = repository.save_sizing_run(
        session,
        project_id=project_id,
        requirement_spec_id=row.id,
        requirement_revision=row.revision,
        spec=spec,
        outputs=outputs,
        execution=execution,
    )
    if project.status is DesignState.draft:
        validate_transition(DesignState.draft, DesignState.calculated)
        repository.set_project_status(session, project_id, DesignState.calculated)
    return result


@router.get("/projects/{project_id}/sizing-runs", response_model=list[SizingRunSummary])
def list_sizing_runs(
    project_id: str, session: Session = Depends(get_session)
) -> list[SizingRunSummary]:
    runs = repository.list_sizing_runs(session, project_id)
    return [
        SizingRunSummary(
            id=r.id,
            requirement_revision=r.requirement_revision,
            input_hash=r.input_hash,
            execution_mode=r.execution.execution_mode,
            result_status=r.execution.result_status,
            created_at=r.created_at,
            wing_area=r.outputs.quantities["wing_area"],
            required_pilot_power=r.outputs.quantities["required_pilot_power"],
            power_margin=r.outputs.quantities["power_margin"],
            warning_count=len(r.outputs.warnings),
        )
        for r in runs
    ]


@router.get("/sizing-runs/{run_id}", response_model=SizingRunResult)
def get_sizing_run(run_id: str, session: Session = Depends(get_session)) -> SizingRunResult:
    return repository.get_sizing_run(session, run_id)


@router.get("/sizing-runs/{run_id}/report", response_class=HTMLResponse)
def sizing_report(run_id: str, session: Session = Depends(get_session)) -> HTMLResponse:
    run = repository.get_sizing_run(session, run_id)
    project = repository.get_project(session, run.project_id)
    html = render_sizing_report(project, run)
    return HTMLResponse(content=html)


# --- 主翼平面形(Step 4)・空力解析(Step 5) ---


def _planform_out(row) -> WingPlanformOut:  # noqa: ANN001
    planform = WingPlanformInput.model_validate(row.payload)
    return WingPlanformOut(
        id=row.id,
        project_id=row.project_id,
        revision=row.revision,
        created_at=datetime.fromisoformat(row.created_at),
        planform=planform,
        derived=planform.derived_quantities(),
    )


@router.put("/projects/{project_id}/planform", response_model=WingPlanformOut)
def put_planform(
    project_id: str, planform: WingPlanformInput, session: Session = Depends(get_session)
) -> WingPlanformOut:
    repository.save_planform(session, project_id, planform)
    row = repository.latest_planform_row(session, project_id)
    assert row is not None  # 直前に保存済み
    return _planform_out(row)


@router.get("/projects/{project_id}/planform", response_model=WingPlanformOut)
def get_planform(project_id: str, session: Session = Depends(get_session)) -> WingPlanformOut:
    repository.get_project(session, project_id)
    row = repository.latest_planform_row(session, project_id)
    if row is None:
        raise NotFoundError(f"主翼平面形が未入力です: project={project_id}")
    return _planform_out(row)


def _analysis_run_out(row) -> AeroAnalysisRunOut:  # noqa: ANN001
    return AeroAnalysisRunOut(
        id=row.id,
        project_id=row.project_id,
        solver_name=row.solver_name,
        planform_revision=row.planform_revision,
        requirement_revision=row.requirement_revision,
        input_hash=row.input_hash,
        request=AeroAnalysisRequest.model_validate(row.request),
        outputs=AeroAnalysisOutput.model_validate(row.outputs),
        execution=SolverExecution.model_validate(row.execution),
        created_at=datetime.fromisoformat(row.created_at),
    )


@router.post(
    "/projects/{project_id}/aero-analyses", response_model=AeroAnalysisRunOut, status_code=201
)
def run_aero_analysis(
    project_id: str, session: Session = Depends(get_session)
) -> AeroAnalysisRunOut:
    """最新の平面形+要求仕様でモック空力解析を実行する(Step 5)。

    現時点ではexecution_mode=mock固定(XFLR5 real連携はT-202b)。
    モックである旨は結果のexecution.execution_modeで機械的に判別できる(CON-003)。
    """
    project = repository.get_project(session, project_id)
    planform_row = repository.latest_planform_row(session, project_id)
    if planform_row is None:
        raise MissingRequirementError(
            f"主翼平面形が未入力のため空力解析を実行できません: project={project_id}"
        )
    req_row = repository.latest_requirements_row(session, project_id)
    if req_row is None:
        raise MissingRequirementError(
            f"要求仕様が未入力のため空力解析を実行できません(係数e/CD0/CL_maxが必要): "
            f"project={project_id}"
        )
    planform = WingPlanformInput.model_validate(planform_row.payload)
    spec = RequirementSpecInput.model_validate(req_row.payload)
    request = build_aero_request(planform, spec)
    outputs, execution = execute_aero_analysis(request)
    row = repository.save_analysis_run(
        session,
        project_id=project_id,
        solver_name=execution.solver_name,
        planform_revision=planform_row.revision,
        requirement_revision=req_row.revision,
        request=request.model_dump(mode="json"),
        outputs=outputs.model_dump(mode="json"),
        execution=execution,
    )
    if project.status is DesignState.calculated:
        validate_transition(DesignState.calculated, DesignState.analyzed)
        repository.set_project_status(session, project_id, DesignState.analyzed)
    return _analysis_run_out(row)


@router.get("/projects/{project_id}/aero-analyses", response_model=list[AeroAnalysisRunOut])
def list_aero_analyses(
    project_id: str, session: Session = Depends(get_session)
) -> list[AeroAnalysisRunOut]:
    return [_analysis_run_out(r) for r in repository.list_analysis_runs(session, project_id)]


@router.get("/aero-analyses/{run_id}", response_model=AeroAnalysisRunOut)
def get_aero_analysis(run_id: str, session: Session = Depends(get_session)) -> AeroAnalysisRunOut:
    return _analysis_run_out(repository.get_analysis_run(session, run_id))


# --- 状態遷移・製造ガード ---


@router.post("/projects/{project_id}/transition", response_model=Project)
def transition(
    project_id: str, req: TransitionRequest, session: Session = Depends(get_session)
) -> Project:
    project = repository.get_project(session, project_id)
    validate_transition(project.status, req.to, actor=req.actor)
    logger.info(
        "state transition project=%s %s -> %s actor=%s comment=%s",
        project_id, project.status, req.to, req.actor, req.comment,
    )
    return repository.set_project_status(session, project_id, req.to)


@router.post("/projects/{project_id}/manufacturing-export")
def manufacturing_export(project_id: str, session: Session = Depends(get_session)) -> Response:
    """製造用データ生成(FR-004ガード)。生成本体はPhase 5(TASKS T-501)。"""
    project = repository.get_project(session, project_id)
    ensure_approved_for_manufacturing(project.status)  # 未承認 → 409
    return Response(
        content='{"detail":"製造用データ生成はPhase 5で実装予定です(承認ガードは通過)"}',
        media_type="application/json",
        status_code=501,
    )
