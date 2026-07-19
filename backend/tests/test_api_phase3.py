"""API統合テスト: 質量台帳(T-302)・静安定(T-303)・梁解析(T-301)。"""

import pytest

from tests.conftest import RC1_JSON
from tests.test_api_aero import PLANFORM_JSON

MASS_ITEM_A = {
    "name": "主桁",
    "category": "wing_structure",
    "mass": {"value": 10, "unit": "kg"},
    "position_x": {"value": 1.0, "unit": "m"},
}
MASS_ITEM_B = {
    "name": "パイロット",
    "category": "pilot",
    "mass": {"value": 30, "unit": "kg"},
    "position_x": {"value": 3.0, "unit": "m"},
    "source": "measured",
}

STABILITY_JSON = {
    "horizontal_tail_area": {"value": 2.5, "unit": "m^2"},
    "tail_arm": {"value": 4, "unit": "m"},
    "wing_ac_position": {"value": 0.9, "unit": "m"},
    "tail_aspect_ratio": 8.0,
}

SPAR_JSON = {
    "half_span": {"value": 15, "unit": "m"},
    "load_factor": 1.0,
    "total_mass": {"value": 100, "unit": "kg"},
    "lift_distribution": "elliptic",
    "spar_outer_diameter": {"value": 0.1, "unit": "m"},
    "spar_wall_thickness": {"value": 1, "unit": "mm"},
    "elastic_modulus": {"value": 200, "unit": "GPa"},
    "allowable_stress": {"value": 800, "unit": "MPa"},
    "required_safety_factor": 1.5,
}


def _setup_project(client, sample_project_json) -> str:
    return client.post("/api/projects", json=sample_project_json).json()["id"]


class TestMassItemsCrud:
    def test_crud_and_properties(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)

        res = client.post(f"/api/projects/{project_id}/mass-items", json=MASS_ITEM_A)
        assert res.status_code == 201
        item_a = res.json()
        client.post(f"/api/projects/{project_id}/mass-items", json=MASS_ITEM_B)

        items = client.get(f"/api/projects/{project_id}/mass-items").json()
        assert len(items) == 2

        # 質量特性(RC-M1: cg_x=2.5)
        props = client.get(f"/api/projects/{project_id}/mass-properties").json()
        assert props["quantities"]["total_mass"]["value"] == pytest.approx(40.0)
        assert props["quantities"]["cg_x"]["value"] == pytest.approx(2.5)
        assert props["quantities"]["inertia_yy"]["value"] == pytest.approx(30.0)

        # 更新(実測値へ)
        res = client.put(
            f"/api/mass-items/{item_a['id']}",
            json=MASS_ITEM_A | {"mass": {"value": 12, "unit": "kg"}, "source": "measured"},
        )
        assert res.status_code == 200
        assert res.json()["mass"]["value"] == 12

        # 削除
        assert client.delete(f"/api/mass-items/{item_a['id']}").status_code == 204
        assert len(client.get(f"/api/projects/{project_id}/mass-items").json()) == 1

    def test_properties_409_when_empty(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        assert client.get(f"/api/projects/{project_id}/mass-properties").status_code == 409

    def test_target_delta_uses_requirements(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)  # 目標40kg
        client.post(
            f"/api/projects/{project_id}/mass-items",
            json=MASS_ITEM_A | {"mass": {"value": 45, "unit": "kg"}},
        )
        props = client.get(f"/api/projects/{project_id}/mass-properties").json()
        assert any(w["code"] == "MASS_OVER_TARGET" for w in props["warnings"])

    def test_invalid_item_422(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.post(
            f"/api/projects/{project_id}/mass-items",
            json=MASS_ITEM_A | {"mass": {"value": 10, "unit": "m"}},
        )
        assert res.status_code == 422


class TestStabilityEndpoint:
    def _setup_full(self, client, sample_project_json) -> str:
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        client.put(f"/api/projects/{project_id}/planform", json=PLANFORM_JSON)
        client.post(f"/api/projects/{project_id}/mass-items", json=MASS_ITEM_A)
        client.post(f"/api/projects/{project_id}/mass-items", json=MASS_ITEM_B)
        return project_id

    def test_stability_run(self, client, sample_project_json):
        project_id = self._setup_full(client, sample_project_json)
        res = client.post(
            f"/api/projects/{project_id}/stability-analyses", json=STABILITY_JSON
        )
        assert res.status_code == 201
        run = res.json()
        assert run["execution"]["execution_mode"] == "analytical_estimate"
        assert run["execution"]["solver_name"] == "pbm.static_stability"
        assert run["planform_revision"] == 1
        assert run["request"]["cg_x_m"] == pytest.approx(2.5)  # 台帳由来の文脈が保存される
        sm = run["outputs"]["quantities"]["static_margin"]["value"]
        assert isinstance(sm, float)
        runs = client.get(f"/api/projects/{project_id}/stability-analyses").json()
        assert len(runs) == 1

    def test_409_without_mass_items(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        client.put(f"/api/projects/{project_id}/planform", json=PLANFORM_JSON)
        res = client.post(
            f"/api/projects/{project_id}/stability-analyses", json=STABILITY_JSON
        )
        assert res.status_code == 409

    def test_stability_runs_not_mixed_into_aero_list(self, client, sample_project_json):
        """analysis_runs共有テーブルでもソルバー種別でリストが分離される。"""
        project_id = self._setup_full(client, sample_project_json)
        client.post(f"/api/projects/{project_id}/stability-analyses", json=STABILITY_JSON)
        client.post(f"/api/projects/{project_id}/aero-analyses")
        aero = client.get(f"/api/projects/{project_id}/aero-analyses").json()
        stab = client.get(f"/api/projects/{project_id}/stability-analyses").json()
        assert len(aero) == 1 and aero[0]["solver_name"] == "XFLR5"
        assert len(stab) == 1 and stab[0]["execution"]["solver_name"] == "pbm.static_stability"


class TestSparEndpoint:
    def test_spar_run(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.post(f"/api/projects/{project_id}/spar-analyses", json=SPAR_JSON)
        assert res.status_code == 201
        run = res.json()
        assert run["execution"]["execution_mode"] == "analytical_estimate"
        assert run["outputs"]["quantities"]["root_bending_moment"]["value"] == pytest.approx(
            3121.55, rel=1e-3
        )
        assert run["outputs"]["quantities"]["safety_factor"]["value"] > 1.5
        runs = client.get(f"/api/projects/{project_id}/spar-analyses").json()
        assert len(runs) == 1

    def test_missing_human_inputs_422(self, client, sample_project_json):
        """荷重倍数・許容応力等の人間確定項目は省略不可(既定値なし)。"""
        project_id = _setup_project(client, sample_project_json)
        body = {k: v for k, v in SPAR_JSON.items() if k != "load_factor"}
        res = client.post(f"/api/projects/{project_id}/spar-analyses", json=body)
        assert res.status_code == 422
