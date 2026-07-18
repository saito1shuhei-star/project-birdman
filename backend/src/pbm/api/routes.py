"""APIルート(API_SPEC.md)。計算式・状態遷移規則はここに書かない(ARCHITECTURE §2)。"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

import pbm
from pbm.api.schemas import (
    HealthOut,
    RequirementSpecOut,
    SizingRunSummary,
    TransitionRequest,
)
from pbm.domain.entities import Project, ProjectCreate
from pbm.domain.errors import MissingRequirementError, NotFoundError
from pbm.domain.requirements import RequirementSpecInput
from pbm.domain.results import SizingRunResult
from pbm.domain.states import DesignState
from pbm.persistence import repository
from pbm.reports.html_report import render_sizing_report
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
