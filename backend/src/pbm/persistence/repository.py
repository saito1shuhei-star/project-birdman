"""リポジトリ: ドメインモデル ⇔ テーブル行の変換と永続化操作。

履歴主義: サイジング実行・要求仕様は上書きせず常に追記する(DATA_MODEL.md)。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pbm.adapters.base import SolverExecution
from pbm.domain.entities import Project, ProjectCreate
from pbm.domain.errors import NotFoundError
from pbm.domain.requirements import RequirementSpecInput
from pbm.domain.results import SizingOutput, SizingRunResult
from pbm.domain.states import DesignState
from pbm.persistence.models import ProjectRow, RequirementSpecRow, SizingRunRow


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
