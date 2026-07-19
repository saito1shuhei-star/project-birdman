"""API統合テスト: 承認監査(T-304)・レポート統合・設計スイープ(T-401)。"""

import pytest

from tests.conftest import RC1_JSON
from tests.test_api_aero import PLANFORM_JSON
from tests.test_api_phase3 import MASS_ITEM_A, MASS_ITEM_B, SPAR_JSON, STABILITY_JSON


def _setup_project(client, sample_project_json) -> str:
    return client.post("/api/projects", json=sample_project_json).json()["id"]


class TestApprovalAudit:
    def test_manual_transition_recorded(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        client.post(f"/api/projects/{project_id}/sizing-runs")
        client.post(f"/api/projects/{project_id}/transition", json={"to": "review_required"})
        client.post(
            f"/api/projects/{project_id}/transition",
            json={"to": "approved", "actor": "設計責任者", "comment": "承認テスト"},
        )
        log = client.get(f"/api/projects/{project_id}/approvals").json()
        # 自動遷移(draft→calculated)+手動2件 = 3件、新しい順
        assert len(log) == 3
        assert log[0]["to_state"] == "approved"
        assert log[0]["actor"] == "設計責任者"
        assert log[0]["comment"] == "承認テスト"
        auto = log[-1]
        assert auto["from_state"] == "draft" and auto["to_state"] == "calculated"
        assert auto["actor"] is None  # 自動遷移

    def test_rejected_transition_not_recorded(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.post(
            f"/api/projects/{project_id}/transition", json={"to": "approved", "actor": "x"}
        )
        assert res.status_code == 409
        assert client.get(f"/api/projects/{project_id}/approvals").json() == []

    def test_transitions_endpoint(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.get(f"/api/projects/{project_id}/transitions").json()
        assert res["current"] == "draft"
        assert res["allowed"] == ["calculated"]
        assert set(res["actor_required"]) == {"approved", "rejected"}


class TestReportIntegration:
    def test_report_includes_project_snapshot_sections(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        run = client.post(f"/api/projects/{project_id}/sizing-runs").json()
        client.put(f"/api/projects/{project_id}/planform", json=PLANFORM_JSON)
        client.post(f"/api/projects/{project_id}/aero-analyses")
        client.post(f"/api/projects/{project_id}/mass-items", json=MASS_ITEM_A)
        client.post(f"/api/projects/{project_id}/mass-items", json=MASS_ITEM_B)
        client.post(f"/api/projects/{project_id}/stability-analyses", json=STABILITY_JSON)
        client.post(f"/api/projects/{project_id}/spar-analyses", json=SPAR_JSON)

        html = client.get(f"/api/sizing-runs/{run['id']}/report").text
        assert "プロジェクト現況(Step 4–9)" in html
        assert "主翼平面形(rev.1)" in html
        assert "実XFLR5解析ではない" in html          # mockの明示
        assert "質量・重心(台帳より" in html
        assert "静安定(最新)" in html
        assert "主桁梁解析(最新)" in html
        assert "設計状態の変更履歴" in html
        assert "自動遷移" in html
        assert "レポート生成時点の最新データ" in html   # 時点の注意書き

    def test_report_without_extras_still_works(self, client, sample_project_json):
        """Step 4以降が未入力でもPhase 1レポートは従来どおり生成できる。"""
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        run = client.post(f"/api/projects/{project_id}/sizing-runs").json()
        res = client.get(f"/api/sizing-runs/{run['id']}/report")
        assert res.status_code == 200
        assert "主翼平面形(rev." not in res.text
        assert "飛行安全を保証するものではありません" in res.text


class TestDesignSweepEndpoint:
    def test_sweep_run(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        res = client.post(
            f"/api/projects/{project_id}/design-sweeps",
            json={
                "variables": [
                    {"variable": "wingspan", "minimum": 25, "maximum": 35, "steps": 3},
                    {"variable": "cruise_speed", "minimum": 6.5, "maximum": 8, "steps": 3},
                ]
            },
        )
        assert res.status_code == 201
        run = res.json()
        assert run["execution"]["solver_name"] == "pbm.design_sweep"
        assert run["execution"]["execution_mode"] == "analytical_estimate"
        assert run["outputs"]["evaluated"] == 9
        assert run["requirement_revision"] == 1
        # 可行案があればパレート案も存在する
        if run["outputs"]["feasible_count"] > 0:
            assert run["outputs"]["pareto_count"] >= 1
        runs = client.get(f"/api/projects/{project_id}/design-sweeps").json()
        assert len(runs) == 1

    def test_sweep_409_without_requirements(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.post(
            f"/api/projects/{project_id}/design-sweeps",
            json={
                "variables": [
                    {"variable": "wingspan", "minimum": 25, "maximum": 30, "steps": 2}
                ]
            },
        )
        assert res.status_code == 409

    def test_sweep_not_mixed_into_other_lists(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        client.put(f"/api/projects/{project_id}/requirements", json=RC1_JSON)
        client.post(
            f"/api/projects/{project_id}/design-sweeps",
            json={
                "variables": [
                    {"variable": "wingspan", "minimum": 25, "maximum": 30, "steps": 2}
                ]
            },
        )
        assert client.get(f"/api/projects/{project_id}/aero-analyses").json() == []
        assert client.get(f"/api/projects/{project_id}/spar-analyses").json() == []


class TestSparTaperAndBuckling:
    def test_uniform_section_unchanged_regression(self, client, sample_project_json):
        """テーパー未指定は従来(一定断面)と同一結果(回帰)。"""
        project_id = _setup_project(client, sample_project_json)
        run = client.post(f"/api/projects/{project_id}/spar-analyses", json=SPAR_JSON).json()
        q = run["outputs"]["quantities"]
        assert q["root_bending_moment"]["value"] == pytest.approx(3121.55, rel=1e-3)
        assert q["max_bending_stress"]["value"] == pytest.approx(
            q["root_bending_stress"]["value"], rel=1e-12
        )
        assert q["max_stress_position"]["value"] == pytest.approx(0.0, abs=1e-12)
        # 座屈スクリーニング比(RC-B1手計算: σ_cr=2.421e9 Pa → 比≈0.169)
        assert q["buckling_stress_ratio_root"]["value"] == pytest.approx(0.1692, rel=2e-3)

    def test_tapered_spar_reduces_tip_stiffness(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        tapered = SPAR_JSON | {
            "spar_tip_outer_diameter": {"value": 0.05, "unit": "m"},
            "spar_tip_wall_thickness": {"value": 0.5, "unit": "mm"},
        }
        run_t = client.post(
            f"/api/projects/{project_id}/spar-analyses", json=tapered
        ).json()
        run_u = client.post(
            f"/api/projects/{project_id}/spar-analyses", json=SPAR_JSON
        ).json()
        # 翼端側が細い分たわみは大きくなる。根元断面は同一なので根元応力は同一
        assert (
            run_t["outputs"]["quantities"]["tip_deflection"]["value"]
            > run_u["outputs"]["quantities"]["tip_deflection"]["value"]
        )
        assert run_t["outputs"]["quantities"]["root_bending_stress"]["value"] == pytest.approx(
            run_u["outputs"]["quantities"]["root_bending_stress"]["value"], rel=1e-9
        )

    def test_tip_only_one_field_rejected(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.post(
            f"/api/projects/{project_id}/spar-analyses",
            json=SPAR_JSON | {"spar_tip_outer_diameter": {"value": 0.05, "unit": "m"}},
        )
        assert res.status_code == 422

    def test_buckling_screening_warning_for_thin_tapered_tip(self, client, sample_project_json):
        """薄肉・大応力の条件で座屈スクリーニング警告が出る。"""
        project_id = _setup_project(client, sample_project_json)
        risky = SPAR_JSON | {
            "load_factor": 2.5,
            "spar_outer_diameter": {"value": 0.09, "unit": "m"},
            "spar_wall_thickness": {"value": 0.6, "unit": "mm"},
            "allowable_stress": {"value": 2000, "unit": "MPa"},
        }
        run = client.post(f"/api/projects/{project_id}/spar-analyses", json=risky).json()
        codes = {w["code"] for w in run["outputs"]["warnings"]}
        assert "BUCKLING_SCREENING" in codes