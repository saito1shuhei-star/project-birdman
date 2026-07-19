"""APIルート(API_SPEC.md)。計算式・状態遷移規則はここに書かない(ARCHITECTURE §2)。"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

import pbm
from pbm.adapters.base import ExecutionMode, ResultStatus, SolverExecution
from pbm.api.schemas import (
    AeroAnalysisRunOut,
    HealthOut,
    RequirementSpecOut,
    SizingRunSummary,
    SparRunOut,
    StabilityRunOut,
    TransitionRequest,
    WingPlanformOut,
)
from pbm.calculation.mass_properties import MassPropertiesOutput, compute_mass_properties
from pbm.calculation.spar_beam import run_spar_analysis
from pbm.calculation.static_stability import compute_static_stability
from pbm.domain.aero_analysis import AeroAnalysisOutput, AeroAnalysisRequest
from pbm.domain.entities import Project, ProjectCreate
from pbm.domain.errors import MissingRequirementError, NotFoundError
from pbm.domain.mass_item import MassItem, MassItemInput
from pbm.domain.planform import WingPlanformInput
from pbm.domain.requirements import RequirementSpecInput
from pbm.domain.results import SizingRunResult
from pbm.domain.stability import StabilityOutput, StabilityRequest
from pbm.domain.states import DesignState
from pbm.domain.structure import SparAnalysisOutput, SparAnalysisRequest
from pbm.persistence import repository
from pbm.reports.html_report import render_sizing_report
from pbm.workflow.aero_service import build_aero_request, execute_aero_analysis
from pbm.workflow.hashing import compute_input_hash
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
    runs = repository.list_analysis_runs(session, project_id, solver_name="XFLR5")
    return [_analysis_run_out(r) for r in runs]


@router.get("/aero-analyses/{run_id}", response_model=AeroAnalysisRunOut)
def get_aero_analysis(run_id: str, session: Session = Depends(get_session)) -> AeroAnalysisRunOut:
    row = repository.get_analysis_run(session, run_id)
    if row.solver_name != "XFLR5":
        raise NotFoundError(f"空力解析ではありません(solver={row.solver_name}): {run_id}")
    return _analysis_run_out(row)


# --- 質量・重心台帳(Step 9 / T-302) ---


@router.post("/projects/{project_id}/mass-items", response_model=MassItem, status_code=201)
def create_mass_item(
    project_id: str, item: MassItemInput, session: Session = Depends(get_session)
) -> MassItem:
    return repository.create_mass_item(session, project_id, item)


@router.get("/projects/{project_id}/mass-items", response_model=list[MassItem])
def list_mass_items(project_id: str, session: Session = Depends(get_session)) -> list[MassItem]:
    return repository.list_mass_items(session, project_id)


@router.put("/mass-items/{item_id}", response_model=MassItem)
def update_mass_item(
    item_id: str, item: MassItemInput, session: Session = Depends(get_session)
) -> MassItem:
    return repository.update_mass_item(session, item_id, item)


@router.delete("/mass-items/{item_id}", status_code=204)
def delete_mass_item(item_id: str, session: Session = Depends(get_session)) -> None:
    repository.delete_mass_item(session, item_id)


@router.get("/projects/{project_id}/mass-properties", response_model=MassPropertiesOutput)
def get_mass_properties(
    project_id: str, session: Session = Depends(get_session)
) -> MassPropertiesOutput:
    """台帳から総質量・重心・慣性モーメント・内訳を計算する(オンデマンド)。"""
    items = repository.list_mass_items(session, project_id)
    if not items:
        raise MissingRequirementError(
            f"質量部品が未登録のため質量特性を計算できません: project={project_id}"
        )
    req_row = repository.latest_requirements_row(session, project_id)
    target = None
    if req_row is not None:
        target = RequirementSpecInput.model_validate(req_row.payload).airframe_mass_target
    return compute_mass_properties(list(items), airframe_mass_target=target)


# --- 静安定(Step 7 / T-303) ---


def _stability_run_out(row) -> StabilityRunOut:  # noqa: ANN001
    return StabilityRunOut(
        id=row.id,
        project_id=row.project_id,
        planform_revision=row.planform_revision,
        requirement_revision=row.requirement_revision,
        input_hash=row.input_hash,
        request=row.request,
        outputs=StabilityOutput.model_validate(row.outputs),
        execution=SolverExecution.model_validate(row.execution),
        created_at=datetime.fromisoformat(row.created_at),
    )


@router.post(
    "/projects/{project_id}/stability-analyses",
    response_model=StabilityRunOut,
    status_code=201,
)
def run_stability_analysis(
    project_id: str, request: StabilityRequest, session: Session = Depends(get_session)
) -> StabilityRunOut:
    """静安定余裕を計算する。翼幾何は平面形、重心は質量台帳から取得する。"""
    repository.get_project(session, project_id)
    planform_row = repository.latest_planform_row(session, project_id)
    if planform_row is None:
        raise MissingRequirementError(
            f"主翼平面形が未入力のため静安定を計算できません: project={project_id}"
        )
    req_row = repository.latest_requirements_row(session, project_id)
    if req_row is None:
        raise MissingRequirementError(
            f"要求仕様が未入力のため静安定を計算できません(オズワルド効率が必要): "
            f"project={project_id}"
        )
    items = repository.list_mass_items(session, project_id)
    if not items:
        raise MissingRequirementError(
            f"質量部品が未登録のため重心を計算できません: project={project_id}"
        )

    planform = WingPlanformInput.model_validate(planform_row.payload)
    spec = RequirementSpecInput.model_validate(req_row.payload)
    mass_props = compute_mass_properties(
        list(items), airframe_mass_target=spec.airframe_mass_target
    )
    cg_x = mass_props.quantities["cg_x"].value

    # トレーサビリティのため、リクエスト本体に加えて導出済みの文脈も保存・ハッシュ対象にする
    context = {
        "tail": request.model_dump(mode="json"),
        "wing": {
            "area_m2": planform.area_si,
            "mean_chord_m": planform.mean_chord_si,
            "aspect_ratio": planform.aspect_ratio,
            "oswald_efficiency": spec.oswald_efficiency,
        },
        "cg_x_m": cg_x,
    }
    started_at = datetime.now(UTC)
    outputs = compute_static_stability(
        request,
        wing_area_si=planform.area_si,
        wing_mean_chord_si=planform.mean_chord_si,
        wing_aspect_ratio=planform.aspect_ratio,
        wing_oswald_efficiency=spec.oswald_efficiency,
        cg_x_si=cg_x,
    )
    finished_at = datetime.now(UTC)
    execution = SolverExecution(
        solver_name="pbm.static_stability",
        solver_version=pbm.__version__,
        execution_mode=ExecutionMode.analytical_estimate,
        input_hash=compute_input_hash(context),
        started_at=started_at,
        finished_at=finished_at,
        result_status=ResultStatus.ok,
    )
    row = repository.save_analysis_run(
        session,
        project_id=project_id,
        solver_name="pbm.static_stability",
        planform_revision=planform_row.revision,
        requirement_revision=req_row.revision,
        request=context,
        outputs=outputs.model_dump(mode="json"),
        execution=execution,
    )
    return _stability_run_out(row)


@router.get("/projects/{project_id}/stability-analyses", response_model=list[StabilityRunOut])
def list_stability_analyses(
    project_id: str, session: Session = Depends(get_session)
) -> list[StabilityRunOut]:
    runs = repository.list_analysis_runs(session, project_id, solver_name="pbm.static_stability")
    return [_stability_run_out(r) for r in runs]


# --- 構造: 主桁の簡易梁解析(Step 8 / T-301) ---


def _spar_run_out(row) -> SparRunOut:  # noqa: ANN001
    return SparRunOut(
        id=row.id,
        project_id=row.project_id,
        input_hash=row.input_hash,
        request=SparAnalysisRequest.model_validate(row.request),
        outputs=SparAnalysisOutput.model_validate(row.outputs),
        execution=SolverExecution.model_validate(row.execution),
        created_at=datetime.fromisoformat(row.created_at),
    )


@router.post(
    "/projects/{project_id}/spar-analyses", response_model=SparRunOut, status_code=201
)
def run_spar_analysis_endpoint(
    project_id: str, request: SparAnalysisRequest, session: Session = Depends(get_session)
) -> SparRunOut:
    """主桁の簡易梁解析。荷重倍数・許容応力・要求安全率は人間が入力する(既定値なし)。"""
    repository.get_project(session, project_id)
    started_at = datetime.now(UTC)
    outputs = run_spar_analysis(request)
    finished_at = datetime.now(UTC)
    execution = SolverExecution(
        solver_name="pbm.spar_beam",
        solver_version=pbm.__version__,
        execution_mode=ExecutionMode.analytical_estimate,
        input_hash=compute_input_hash(request),
        started_at=started_at,
        finished_at=finished_at,
        result_status=ResultStatus.ok,
    )
    row = repository.save_analysis_run(
        session,
        project_id=project_id,
        solver_name="pbm.spar_beam",
        planform_revision=None,
        requirement_revision=None,
        request=request.model_dump(mode="json"),
        outputs=outputs.model_dump(mode="json"),
        execution=execution,
    )
    return _spar_run_out(row)


@router.get("/projects/{project_id}/spar-analyses", response_model=list[SparRunOut])
def list_spar_analyses(
    project_id: str, session: Session = Depends(get_session)
) -> list[SparRunOut]:
    runs = repository.list_analysis_runs(session, project_id, solver_name="pbm.spar_beam")
    return [_spar_run_out(r) for r in runs]


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
