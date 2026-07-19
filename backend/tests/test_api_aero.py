"""API統合テスト: 主翼平面形(Step 4)+空力解析(Step 5)の縦スライス(T-204)。"""

import pytest

from tests.conftest import RC1_JSON

PLANFORM_JSON = {
    "sections": [
        {
            "spanwise_position": {"value": 0, "unit": "m"},
            "chord": {"value": 1.2, "unit": "m"},
            "airfoil": "DAE-11",
        },
        {
            "spanwise_position": {"value": 15, "unit": "m"},
            "chord": {"value": 0.6, "unit": "m"},
            "airfoil": "DAE-11",
        },
    ]
}


def _setup_project(client, sample_project_json) -> str:
    res = client.post("/api/projects", json=sample_project_json)
    assert res.status_code == 201
    return res.json()["id"]


class TestPlanformEndpoints:
    def test_put_and_get_planform(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.put(f"/api/projects/{project_id}/planform", json=PLANFORM_JSON)
        assert res.status_code == 200
        body = res.json()
        assert body["revision"] == 1
        assert body["derived"]["area"]["value"] == pytest.approx(27.0)
        assert body["derived"]["aspect_ratio"]["value"] == pytest.approx(900 / 27, rel=1e-6)
        assert body["derived"]["taper_ratio"]["value"] == pytest.approx(0.5)

        res = client.get(f"/api/projects/{project_id}/planform")
        assert res.status_code == 200
        assert res.json()["planform"]["sections"][0]["airfoil"] == "DAE-11"

    def test_planform_revision_increments(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/planform", json=PLANFORM_JSON)
        res = client.put(f"/api/projects/{project_id}/planform", json=PLANFORM_JSON)
        assert res.json()["revision"] == 2

    def test_get_planform_404_when_missing(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        assert client.get(f"/api/projects/{project_id}/planform").status_code == 404

    def test_invalid_planform_422(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        bad = {"sections": [PLANFORM_JSON["sections"][0]]}  # 1セクションのみ
        res = client.put(f"/api/projects/{project_id}/planform", json=bad)
        assert res.status_code == 422


class TestAeroAnalysisEndpoints:
    def test_full_aero_slice(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        client.put(f"/api/projects/{project_id}/planform", json=PLANFORM_JSON)

        res = client.post(f"/api/projects/{project_id}/aero-analyses")
        assert res.status_code == 201
        run = res.json()
        # モックであることが機械的に判別できる(CON-003)
        assert run["execution"]["execution_mode"] == "mock"
        assert run["solver_name"] == "XFLR5"
        assert run["planform_revision"] == 1
        assert run["requirement_revision"] == 1
        # リクエストは平面形のARと要求仕様の係数から組み立てられる
        assert run["request"]["aspect_ratio"] == pytest.approx(900 / 27, rel=1e-6)
        assert run["request"]["parasite_drag_coefficient"] == pytest.approx(0.020)
        assert run["request"]["airfoil_name"] == "DAE-11"
        assert run["outputs"]["polar"]
        assert run["outputs"]["max_lift_to_drag"] > 0

        # 一覧・個別取得
        runs = client.get(f"/api/projects/{project_id}/aero-analyses").json()
        assert len(runs) == 1
        detail = client.get(f"/api/aero-analyses/{run['id']}").json()
        assert detail["input_hash"] == run["input_hash"]

    def test_status_calculated_to_analyzed(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        client.post(f"/api/projects/{project_id}/sizing-runs")
        assert client.get(f"/api/projects/{project_id}").json()["status"] == "calculated"
        client.put(f"/api/projects/{project_id}/planform", json=PLANFORM_JSON)
        client.post(f"/api/projects/{project_id}/aero-analyses")
        assert client.get(f"/api/projects/{project_id}").json()["status"] == "analyzed"

    def test_409_without_planform(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        res = client.post(f"/api/projects/{project_id}/aero-analyses")
        assert res.status_code == 409

    def test_409_without_requirements(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/planform", json=PLANFORM_JSON)
        res = client.post(f"/api/projects/{project_id}/aero-analyses")
        assert res.status_code == 409

    def test_rerun_reproducible(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        client.put(f"/api/projects/{project_id}/planform", json=PLANFORM_JSON)
        run1 = client.post(f"/api/projects/{project_id}/aero-analyses").json()
        run2 = client.post(f"/api/projects/{project_id}/aero-analyses").json()
        assert run1["input_hash"] == run2["input_hash"]
        assert run1["outputs"]["polar"] == run2["outputs"]["polar"]
