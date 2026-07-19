"""リポジトリ: ドメインモデル ⇔ テーブル行の変換と永続化操作。

履歴主義: サイジング実行・要求仕様・平面形・解析実行は上書きせず常に追記する(DATA_MODEL.md)。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pbm.adapters.base import SolverExecution
from pbm.domain.entities import Project, ProjectCreate
from pbm.domain.errors import NotFoundError
from pbm.domain.mass_item import MassItem, MassItemInput
from pbm.domain.planform import WingPlanformInput
from pbm.domain.requirements import RequirementSpecInput
from pbm.domain.results import SizingOutput, SizingRunResult
from pbm.domain.states import DesignState
from pbm.persistence.models import (
    AnalysisRunRow,
    ApprovalRow,
    MassItemRow,
    ProjectRow,
    RequirementSpecRow,
    SizingRunRow,
    WingPlanformRow,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _project_from_row(row: ProjectRow) -> Project:
    return Project(
        id=row.id,
        team_name=row.team_name,
        aircraft_name=row.aircraft_name,
        design_year=row.design_year,
        category=row.category,
        design_lead=row.design_lead,
        unit_system=row.unit_system,
        version=row.version,
        design_goal=row.design_goal,
        status=DesignState(row.status),
        created_at=datetime.fromisoformat(row.created_at),
        updated_at=datetime.fromisoformat(row.updated_at),
    )


# --- projects ---


def create_project(session: Session, data: ProjectCreate) -> Project:
    now = _now_iso()
    row = ProjectRow(
        id=str(uuid.uuid4()),
        team_name=data.team_name,
        aircraft_name=data.aircraft_name,
        design_year=data.design_year,
        category=data.category.value,
        design_lead=data.design_lead,
        unit_system=data.unit_system.value,
        version=data.version,
        design_goal=data.design_goal,
        status=DesignState.draft.value,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    return _project_from_row(row)


def list_projects(session: Session) -> list[Project]:
    rows = session.scalars(select(ProjectRow).order_by(ProjectRow.created_at.desc())).all()
    return [_project_from_row(r) for r in rows]


def get_project_row(session: Session, project_id: str) -> ProjectRow:
    row = session.get(ProjectRow, project_id)
    if row is None:
        raise NotFoundError(f"プロジェクトが存在しません: {project_id}")
    return row


def get_project(session: Session, project_id: str) -> Project:
    return _project_from_row(get_project_row(session, project_id))


def set_project_status(session: Session, project_id: str, status: DesignState) -> Project:
    row = get_project_row(session, project_id)
    row.status = status.value
    row.updated_at = _now_iso()
    session.commit()
    return _project_from_row(row)


# --- requirement specs ---


def save_requirements(
    session: Session, project_id: str, spec: RequirementSpecInput
) -> tuple[str, int]:
    """新しいリビジョンとして保存し、(id, revision) を返す。プロジェクトはdraftへ戻る。"""
    project = get_project_row(session, project_id)
    latest = latest_requirements_row(session, project_id)
    revision = (latest.revision + 1) if latest else 1
    row = RequirementSpecRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        revision=revision,
        payload=spec.model_dump(mode="json"),
        created_at=_now_iso(),
    )
    session.add(row)
    # 要求仕様の変更により既存計算は最新仕様と不一致になるため draft へ戻す(DOMAIN_MODEL §3)
    project.status = DesignState.draft.value
    project.updated_at = _now_iso()
    session.commit()
    return row.id, revision


def latest_requirements_row(session: Session, project_id: str) -> RequirementSpecRow | None:
    return session.scalars(
        select(RequirementSpecRow)
        .where(RequirementSpecRow.project_id == project_id)
        .order_by(RequirementSpecRow.revision.desc())
        .limit(1)
    ).first()


def requirements_history(session: Session, project_id: str) -> list[RequirementSpecRow]:
    return list(
        session.scalars(
            select(RequirementSpecRow)
            .where(RequirementSpecRow.project_id == project_id)
            .order_by(RequirementSpecRow.revision.desc())
        ).all()
    )


# --- sizing runs ---


def save_sizing_run(
    session: Session,
    *,
    project_id: str,
    requirement_spec_id: str,
    requirement_revision: int,
    spec: RequirementSpecInput,
    outputs: SizingOutput,
    execution: SolverExecution,
) -> SizingRunResult:
    row = SizingRunRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        requirement_spec_id=requirement_spec_id,
        requirement_revision=requirement_revision,
        input_hash=execution.input_hash,
        inputs_snapshot=spec.model_dump(mode="json"),
        outputs=outputs.model_dump(mode="json"),
        execution=execution.model_dump(mode="json"),
        result_status=execution.result_status.value,
        created_at=_now_iso(),
    )
    session.add(row)
    session.commit()
    return _sizing_run_from_row(row)


def _sizing_run_from_row(row: SizingRunRow) -> SizingRunResult:
    return SizingRunResult(
        id=row.id,
        project_id=row.project_id,
        requirement_spec_id=row.requirement_spec_id,
        requirement_revision=row.requirement_revision,
        input_hash=row.input_hash,
        inputs_snapshot=RequirementSpecInput.model_validate(row.inputs_snapshot),
        outputs=SizingOutput.model_validate(row.outputs),
        execution=SolverExecution.model_validate(row.execution),
        created_at=datetime.fromisoformat(row.created_at),
    )


def list_sizing_runs(session: Session, project_id: str) -> list[SizingRunResult]:
    get_project_row(session, project_id)
    rows = session.scalars(
        select(SizingRunRow)
        .where(SizingRunRow.project_id == project_id)
        .order_by(SizingRunRow.created_at.desc())
    ).all()
    return [_sizing_run_from_row(r) for r in rows]


def get_sizing_run(session: Session, run_id: str) -> SizingRunResult:
    row = session.get(SizingRunRow, run_id)
    if row is None:
        raise NotFoundError(f"サイジング実行が存在しません: {run_id}")
    return _sizing_run_from_row(row)


# --- wing planforms ---


def save_planform(
    session: Session, project_id: str, planform: WingPlanformInput
) -> tuple[str, int]:
    """新しいリビジョンとして保存し、(id, revision) を返す。"""
    get_project_row(session, project_id)
    latest = latest_planform_row(session, project_id)
    revision = (latest.revision + 1) if latest else 1
    row = WingPlanformRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        revision=revision,
        payload=planform.model_dump(mode="json"),
        created_at=_now_iso(),
    )
    session.add(row)
    session.commit()
    return row.id, revision


def latest_planform_row(session: Session, project_id: str) -> WingPlanformRow | None:
    return session.scalars(
        select(WingPlanformRow)
        .where(WingPlanformRow.project_id == project_id)
        .order_by(WingPlanformRow.revision.desc())
        .limit(1)
    ).first()


# --- analysis runs(XFLR5/XROTOR等) ---


def save_analysis_run(
    session: Session,
    *,
    project_id: str,
    solver_name: str,
    planform_revision: int | None,
    requirement_revision: int | None,
    request: dict,
    outputs: dict,
    execution: SolverExecution,
) -> AnalysisRunRow:
    row = AnalysisRunRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        solver_name=solver_name,
        planform_revision=planform_revision,
        requirement_revision=requirement_revision,
        input_hash=execution.input_hash,
        request=request,
        outputs=outputs,
        execution=execution.model_dump(mode="json"),
        result_status=execution.result_status.value,
        created_at=_now_iso(),
    )
    session.add(row)
    session.commit()
    return row


def list_analysis_runs(
    session: Session, project_id: str, solver_name: str | None = None
) -> list[AnalysisRunRow]:
    get_project_row(session, project_id)
    stmt = (
        select(AnalysisRunRow)
        .where(AnalysisRunRow.project_id == project_id)
        .order_by(AnalysisRunRow.created_at.desc())
    )
    if solver_name is not None:
        stmt = stmt.where(AnalysisRunRow.solver_name == solver_name)
    return list(session.scalars(stmt).all())


def get_analysis_run(session: Session, run_id: str) -> AnalysisRunRow:
    row = session.get(AnalysisRunRow, run_id)
    if row is None:
        raise NotFoundError(f"解析実行が存在しません: {run_id}")
    return row


# --- mass items(質量台帳。台帳的性質のため上書き更新を許可) ---


def _mass_item_from_row(row: MassItemRow) -> MassItem:
    return MassItem(
        **MassItemInput.model_validate(row.payload).model_dump(),
        id=row.id,
        project_id=row.project_id,
        created_at=datetime.fromisoformat(row.created_at),
        updated_at=datetime.fromisoformat(row.updated_at),
    )


def create_mass_item(session: Session, project_id: str, item: MassItemInput) -> MassItem:
    get_project_row(session, project_id)
    now = _now_iso()
    row = MassItemRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=item.name,
        category=item.category.value,
        payload=item.model_dump(mode="json"),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    return _mass_item_from_row(row)


def list_mass_items(session: Session, project_id: str) -> list[MassItem]:
    get_project_row(session, project_id)
    rows = session.scalars(
        select(MassItemRow)
        .where(MassItemRow.project_id == project_id)
        .order_by(MassItemRow.created_at)
    ).all()
    return [_mass_item_from_row(r) for r in rows]


def update_mass_item(session: Session, item_id: str, item: MassItemInput) -> MassItem:
    row = session.get(MassItemRow, item_id)
    if row is None:
        raise NotFoundError(f"質量部品が存在しません: {item_id}")
    row.name = item.name
    row.category = item.category.value
    row.payload = item.model_dump(mode="json")
    row.updated_at = _now_iso()
    session.commit()
    return _mass_item_from_row(row)


def delete_mass_item(session: Session, item_id: str) -> None:
    row = session.get(MassItemRow, item_id)
    if row is None:
        raise NotFoundError(f"質量部品が存在しません: {item_id}")
    session.delete(row)
    session.commit()


# --- approvals(状態遷移の監査ログ。追記のみ・削除不可) ---


def record_transition(
    session: Session,
    project_id: str,
    *,
    from_state: DesignState,
    to_state: DesignState,
    actor: str | None,
    comment: str | None,
) -> ApprovalRow:
    row = ApprovalRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        from_state=from_state.value,
        to_state=to_state.value,
        actor=actor,
        comment=comment,
        created_at=_now_iso(),
    )
    session.add(row)
    session.commit()
    return row


def list_approvals(session: Session, project_id: str) -> list[ApprovalRow]:
    get_project_row(session, project_id)
    return list(
        session.scalars(
            select(ApprovalRow)
            .where(ApprovalRow.project_id == project_id)
            .order_by(ApprovalRow.created_at.desc())
        ).all()
    )
