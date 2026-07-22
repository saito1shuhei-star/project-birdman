"""API統合テスト: XROTORスクリプト/実行/取込・XFLR5ハンドオフ/取込(Codex版統合)。"""

import base64

import pytest

from tests.test_xflr5_case import _DAT
from tests.test_xrotor_case import _airfoil, _case


def _setup_project(client, sample_project_json) -> str:
    return client.post("/api/projects", json=sample_project_json).json()["id"]


XFLR5_CASE = {
    "case_name": "wing-polar-01",
    "airfoil_name": "DAE-11",
    "data_status": "estimated",
    "airfoil_dat": _DAT,
    "reynolds_numbers": [500_000],
    "mach_numbers": [0.03],
    "input_source": "テスト用ダミー形状",
}

XFLR5_TABLE = "alpha CL CD Cm\n0.0 0.35 0.011 -0.07\n2.0 0.58 0.012 -0.07\n"

XROTOR_SUMMARY = (
    "thrust(N) = 30.5\npower(W) = 250.0\ntorque(N-m) = 19.9\n"
    "Efficiency = 0.82\nspeed(m/s) = 7.5\nrpm = 120\n"
)


class TestXrotorEndpoints:
    def test_script_generation(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.post(f"/api/projects/{project_id}/xrotor-scripts", json=_case())
        assert res.status_code == 200
        body = res.json()
        assert "ARBI" in body["script"]
        assert body["payload"]["flight_speed_mps"] == pytest.approx(10.0)

    def test_mock_run_recorded_with_explicit_mock(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.post(
            f"/api/projects/{project_id}/xrotor-runs",
            json={"case": _case(), "execution_mode": "mock"},
        )
        assert res.status_code == 201
        run = res.json()
        assert run["execution"]["execution_mode"] == "mock"
        assert run["outputs"]["is_real_analysis"] is False
        assert "MOCK" in run["outputs"]["stdout"]
        runs = client.get(f"/api/projects/{project_id}/xrotor-runs").json()
        assert len(runs) == 1

    def test_real_run_unavailable_conflicts(self, client, sample_project_json, monkeypatch):
        monkeypatch.delenv("PBM_XROTOR_PATH", raising=False)
        project_id = _setup_project(client, sample_project_json)
        res = client.post(
            f"/api/projects/{project_id}/xrotor-runs",
            json={"case": _case(), "execution_mode": "real"},
        )
        assert res.status_code == 409  # SolverUnavailableError

    def test_import_complete_summary(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.post(
            f"/api/projects/{project_id}/xrotor-imports",
            json={
                "summary_text": XROTOR_SUMMARY,
                "source_description": "部室PCでXROTOR 7.55を手動実行",
            },
        )
        assert res.status_code == 201
        run = res.json()
        assert run["execution"]["execution_mode"] == "imported"
        assert run["outputs"]["summary"]["thrust_n"] == pytest.approx(30.5)
        assert run["outputs"]["derived_values_added"] is False

    def test_import_incomplete_summary_rejected(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.post(
            f"/api/projects/{project_id}/xrotor-imports",
            json={"summary_text": "thrust(N) = 30.5", "source_description": "test"},
        )
        assert res.status_code == 422  # 不完全なサマリの捏造取込を拒否

    def test_invalid_case_units_rejected(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        bad = _case(rotational_speed={"value": 120, "unit": "m/s"})
        res = client.post(f"/api/projects/{project_id}/xrotor-scripts", json=bad)
        assert res.status_code == 422


class TestXflr5Endpoints:
    def test_handoff_package(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.post(f"/api/projects/{project_id}/xflr5-handoffs", json=XFLR5_CASE)
        assert res.status_code == 200
        body = res.json()
        assert body["payload"]["aerodynamic_result_available"] is False
        package = body["package"]
        assert package["filename"].endswith("-xflr5-input.zip")
        assert len(base64.b64decode(package["content_base64"])) == package["size_bytes"]

    def test_import_table(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.post(
            f"/api/projects/{project_id}/xflr5-imports",
            json={
                "raw_table_text": XFLR5_TABLE,
                "case_name": "wing-polar-01",
                "source_description": "XFLR5 6.62 GUIからエクスポート",
            },
        )
        assert res.status_code == 201
        run = res.json()
        assert run["execution"]["execution_mode"] == "imported"
        assert run["outputs"]["table"]["row_count"] == 2
        runs = client.get(f"/api/projects/{project_id}/xflr5-imports").json()
        assert len(runs) == 1

    def test_import_bad_table_rejected(self, client, sample_project_json):
        project_id = _setup_project(client, sample_project_json)
        res = client.post(
            f"/api/projects/{project_id}/xflr5-imports",
            json={"raw_table_text": "no table here", "source_description": "test"},
        )
        assert res.status_code == 422

    def test_imports_not_mixed_into_mock_aero_list(self, client, sample_project_json):
        """取込(XFLR5.import)とモック解析(XFLR5)のリストが混ざらない。"""
        project_id = _setup_project(client, sample_project_json)
        client.post(
            f"/api/projects/{project_id}/xflr5-imports",
            json={"raw_table_text": XFLR5_TABLE, "source_description": "test"},
        )
        assert client.get(f"/api/projects/{project_id}/aero-analyses").json() == []


def test_helpers_importable():
    """テスト間で共有するヘルパーが正しくエクスポートされている。"""
    assert callable(_airfoil) and callable(_case)
