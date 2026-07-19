"""SQLAlchemyテーブル定義(DATA_MODEL.md)。

物理量を素のfloat列に分解しない。仕様・結果はドメインモデルのJSONダンプで保持し、
読み戻し時にPydanticで再検証する。
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    team_name: Mapped[str] = mapped_column(String(200))
    aircraft_name: Mapped[str] = mapped_column(String(200))
    design_year: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(50))
    design_lead: Mapped[str] = mapped_column(String(200))
    unit_system: Mapped[str] = mapped_column(String(10))
    version: Mapped[str] = mapped_column(String(50))
    design_goal: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[str] = mapped_column(String(40))  # UTC ISO8601
    updated_at: Mapped[str] = mapped_column(String(40))


class RequirementSpecRow(Base):
    __tablename__ = "requirement_specs"
    __table_args__ = (UniqueConstraint("project_id", "revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)  # RequirementSpecInput(値+単位)
    created_at: Mapped[str] = mapped_column(String(40))


class SizingRunRow(Base):
    __tablename__ = "sizing_runs"
    __table_args__ = (Index("ix_sizing_runs_input_hash", "input_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    requirement_spec_id: Mapped[str] = mapped_column(ForeignKey("requirement_specs.id"))
    requirement_revision: Mapped[int] = mapped_column(Integer)
    input_hash: Mapped[str] = mapped_column(String(64))
    inputs_snapshot: Mapped[dict] = mapped_column(JSON)
    outputs: Mapped[dict] = mapped_column(JSON)
    execution: Mapped[dict] = mapped_column(JSON)
    result_status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[str] = mapped_column(String(40))


class WingPlanformRow(Base):
    __tablename__ = "wing_planforms"
    __table_args__ = (UniqueConstraint("project_id", "revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)  # WingPlanformInput(セクション列、値+単位)
    created_at: Mapped[str] = mapped_column(String(40))


class AnalysisRunRow(Base):
    """外部ソルバー(XFLR5/XROTOR等)による解析実行。mock/realはexecution内で区別。"""

    __tablename__ = "analysis_runs"
    __table_args__ = (Index("ix_analysis_runs_input_hash", "input_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    solver_name: Mapped[str] = mapped_column(String(50))  # "XFLR5" / "XROTOR" 等
    planform_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requirement_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict] = mapped_column(JSON)
    outputs: Mapped[dict] = mapped_column(JSON)
    execution: Mapped[dict] = mapped_column(JSON)
    result_status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[str] = mapped_column(String(40))
