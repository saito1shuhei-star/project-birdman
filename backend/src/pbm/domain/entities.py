"""プロジェクトエンティティ(DOMAIN_MODEL.md §2)。"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from pbm.domain.states import DesignState


class Category(StrEnum):
    """大会部門。正式区分は要確認(ASSUMPTIONS A-203)。"""

    distance = "distance"
    time_trial = "time_trial"
    other = "other"


class UnitSystem(StrEnum):
    """表示単位系。内部計算は常にSI(NFR-001)。"""

    SI = "SI"


class ProjectCreate(BaseModel):
    team_name: str = Field(min_length=1, max_length=200)
    aircraft_name: str = Field(min_length=1, max_length=200)
    design_year: int = Field(ge=1977, le=2100)  # 第1回鳥人間コンテストは1977年
    category: Category = Category.distance
    design_lead: str = Field(min_length=1, max_length=200)
    unit_system: UnitSystem = UnitSystem.SI
    version: str = Field(default="v0.1", max_length=50)
    design_goal: str = Field(default="", max_length=2000)


class Project(ProjectCreate):
    id: str
    status: DesignState = DesignState.draft
    created_at: datetime
    updated_at: datetime
