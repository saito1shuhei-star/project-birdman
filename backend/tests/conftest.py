"""テスト共通フィクスチャ。DBはテスト毎に一時ディレクトリのSQLiteへ分離する(A-202)。"""

import pytest
from fastapi.testclient import TestClient

from pbm.api.main import create_app
from pbm.domain.quantities import Quantity
from pbm.domain.requirements import RequirementSpecInput


@pytest.fixture()
def client(tmp_path) -> TestClient:
    db_url = f"sqlite:///{(tmp_path / 'test_pbm.sqlite3').as_posix()}"
    app = create_app(database_url=db_url)
    return TestClient(app)


# 手計算リファレンスケース RC-1(VALIDATION_PLAN.md §2)
RC1_JSON = {
    "pilot_mass": {"value": 60, "unit": "kg"},
    "airframe_mass_target": {"value": 40, "unit": "kg"},
    "pilot_power_sustained": {"value": 250, "unit": "W"},
    "target_cruise_speed": {"value": 7.5, "unit": "m/s"},
    "wingspan_limit": {"value": 30, "unit": "m"},
    "air_density": {"value": 1.225, "unit": "kg/m^3"},
    "cl_cruise": 1.0,
    "cl_max": 1.4,
    "cd0": 0.020,
    "oswald_efficiency": 0.90,
    "propeller_efficiency": 0.80,
    "drivetrain_efficiency": 0.95,
}


@pytest.fixture()
def rc1_spec() -> RequirementSpecInput:
    return RequirementSpecInput.model_validate(RC1_JSON)


@pytest.fixture()
def sample_project_json() -> dict:
    return {
        "team_name": "CIT鳥人間",
        "aircraft_name": "PBM-01",
        "design_year": 2026,
        "category": "human_powered_propeller",
        "design_lead": "テスト設計者",
        "version": "v0.1",
        "design_goal": "安定して1km",
    }


def make_quantity(value: float, unit: str) -> Quantity:
    return Quantity(value=value, unit=unit)
