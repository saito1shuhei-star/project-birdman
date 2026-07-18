"""API統合テスト: Phase 1 縦スライス全体(VALIDATION_PLAN.md §3)。"""

import pytest

from tests.conftest import RC1_JSON


def _create_project(client, sample_project_json) -> str:
    res = client.post("/api/projects", json=sample_project_json)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "draft"
    return body["id"]


class TestHealth:
    def test_health(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


class TestVerticalSlice:
    """プロジェクト作成 → 要求仕様 → サイジング → レポート の一連の流れ。"""

    def test_full_flow(self, client, sample_project_json):
        project_id = _create_project(client, sample_project_json)

        # 要求仕様入力(revision 1)
        res = client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        assert res.status_code == 200
        assert res.json()["revision"] == 1

        # サイジング実行
        res = client.post(f"/api/projects/{project_id}/sizing-runs")
        assert res.status_code == 201
        run = res.json()
        assert run["execution"]["execution_mode"] == "analytical_estimate"  # FR-024
        assert run["execution"]["solver_name"] == "pbm.initial_sizing"
        assert len(run["input_hash"]) == 64
        assert run["outputs"]["quantities"]["wing_area"]["value"] == pytest.approx(
            28.4638, rel=1e-3
        )
        assert run["outputs"]["quantities"]["wing_area"]["unit"] == "m^2"
        assert any(w["code"] == "POWER_DEFICIT" for w in run["outputs"]["warnings"])

        # プロジェクトは calculated へ
        assert client.get(f"/api/projects/{project_id}").json()["status"] == "calculated"

        # 一覧・詳細
        runs = client.get(f"/api/projects/{project_id}/sizing-runs").json()
        assert len(runs) == 1 and runs[0]["id"] == run["id"]
        detail = client.get(f"/api/sizing-runs/{run['id']}").json()
        assert detail["input_hash"] == run["input_hash"]

        # HTMLレポート(FR-030, FR-032)
        res = client.get(f"/api/sizing-runs/{run['id']}/report")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        html = res.text
        assert "analytical_estimate" in html          # 実行モードの明示
        assert "S = W / (q · CL_cruise)" in html      # 使用した式
        assert "A-104" in html                        # 仮定ID
        assert "飛行安全を保証するものではありません" in html  # 免責(FR-032)
        assert "m^2" in html                          # 単位の明記

    def test_rerun_is_reproducible(self, client, sample_project_json):
        """FR-022: 同一入力での再実行はinput_hashと数値が一致する。"""
        project_id = _create_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        run1 = client.post(f"/api/projects/{project_id}/sizing-runs").json()
        run2 = client.post(f"/api/projects/{project_id}/sizing-runs").json()
        assert run1["id"] != run2["id"]                       # 履歴として別実行
        assert run1["input_hash"] == run2["input_hash"]
        assert run1["outputs"]["quantities"] == run2["outputs"]["quantities"]


class TestValidationAtBoundary:
    """FR-011: API境界での単位・次元・範囲検証。"""

    def test_unitless_rejected(self, client, sample_project_json):
        project_id = _create_project(client, sample_project_json)
        res = client.put(
            f"/api/projects/{project_id}/requirements",
            json=RC1_JSON | {"pilot_mass": 60},
        )
        assert res.status_code == 422

    def test_wrong_dimension_rejected(self, client, sample_project_json):
        project_id = _create_project(client, sample_project_json)
        res = client.put(
            f"/api/projects/{project_id}/requirements",
            json=RC1_JSON | {"pilot_mass": {"value": 60, "unit": "m"}},
        )
        assert res.status_code == 422

    def test_out_of_range_rejected(self, client, sample_project_json):
        project_id = _create_project(client, sample_project_json)
        res = client.put(
            f"/api/projects/{project_id}/requirements",
            json=RC1_JSON | {"target_cruise_speed": {"value": 50, "unit": "m/s"}},
        )
        assert res.status_code == 422

    def test_alternative_units_accepted(self, client, sample_project_json):
        project_id = _create_project(client, sample_project_json)
        res = client.put(
            f"/api/projects/{project_id}/requirements",
            json=RC1_JSON | {"target_cruise_speed": {"value": 27, "unit": "km/h"}},
        )
        assert res.status_code == 200


class TestGuards:
    def test_sizing_without_requirements_conflicts(self, client, sample_project_json):
        project_id = _create_project(client, sample_project_json)
        res = client.post(f"/api/projects/{project_id}/sizing-runs")
        assert res.status_code == 409

    def test_invalid_transition_rejected(self, client, sample_project_json):
        project_id = _create_project(client, sample_project_json)
        res = client.post(
            f"/api/projects/{project_id}/transition",
            json={"to": "approved", "actor": "誰か"},
        )
        assert res.status_code == 409

    def test_approval_requires_actor(self, client, sample_project_json):
        project_id = _create_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        client.post(f"/api/projects/{project_id}/sizing-runs")
        client.post(f"/api/projects/{project_id}/transition", json={"to": "review_required"})
        res = client.post(f"/api/projects/{project_id}/transition", json={"to": "approved"})
        assert res.status_code == 409  # actorなし

    def test_manufacturing_export_guard(self, client, sample_project_json):
        """FR-004: 未承認プロジェクトから製造用データを生成できない。"""
        project_id = _create_project(client, sample_project_json)
        res = client.post(f"/api/projects/{project_id}/manufacturing-export")
        assert res.status_code == 409

        # 承認フローを通すとガードは通過する(本体はPhase 5 → 501)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        client.post(f"/api/projects/{project_id}/sizing-runs")
        client.post(f"/api/projects/{project_id}/transition", json={"to": "review_required"})
        res = client.post(
            f"/api/projects/{project_id}/transition",
            json={"to": "approved", "actor": "設計責任者", "comment": "テスト承認"},
        )
        assert res.status_code == 200
        res = client.post(f"/api/projects/{project_id}/manufacturing-export")
        assert res.status_code == 501

    def test_requirements_update_returns_project_to_draft(self, client, sample_project_json):
        project_id = _create_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        client.post(f"/api/projects/{project_id}/sizing-runs")
        assert client.get(f"/api/projects/{project_id}").json()["status"] == "calculated"
        res = client.put(
            f"/api/projects/{project_id}/requirements",
            json=RC1_JSON | {"pilot_mass": {"value": 61, "unit": "kg"}},
        )
        assert res.status_code == 200
        assert res.json()["revision"] == 2
        assert client.get(f"/api/projects/{project_id}").json()["status"] == "draft"

    def test_not_found(self, client):
        assert client.get("/api/projects/nonexistent").status_code == 404
        assert client.get("/api/sizing-runs/nonexistent").status_code == 404
