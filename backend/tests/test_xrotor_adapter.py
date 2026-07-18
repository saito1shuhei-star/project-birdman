"""XROTORAdapterのテスト(T-203)。mock/realの区別とreal未実装の明示を検証する。"""

import pytest

from pbm.adapters.base import ExecutionMode
from pbm.adapters.xrotor import XROTORAdapter
from pbm.domain.errors import SolverNotImplementedError, SolverUnavailableError
from pbm.domain.prop_analysis import PropAnalysisRequest

_REQUEST = PropAnalysisRequest.model_validate(
    {
        "flight_speed": {"value": 7.5, "unit": "m/s"},
        "input_power": {"value": 250, "unit": "W"},
        "diameter": {"value": 3, "unit": "m"},
    }
)


class TestAvailability:
    def test_unavailable_when_path_unset(self):
        adapter = XROTORAdapter(xrotor_path=None)
        assert adapter.is_available() is False

    def test_available_when_path_exists(self, tmp_path):
        fake_exe = tmp_path / "xrotor.exe"
        fake_exe.write_text("dummy")
        adapter = XROTORAdapter(xrotor_path=str(fake_exe))
        assert adapter.is_available() is True

    def test_env_var_used_when_path_not_explicit(self, tmp_path, monkeypatch):
        fake_exe = tmp_path / "xrotor.exe"
        fake_exe.write_text("dummy")
        monkeypatch.setenv("PBM_XROTOR_PATH", str(fake_exe))
        adapter = XROTORAdapter()
        assert adapter.is_available() is True


class TestMockRun:
    def test_default_mode_is_mock(self):
        adapter = XROTORAdapter(xrotor_path=None)
        output, execution = adapter.run(_REQUEST)
        assert execution.execution_mode == ExecutionMode.mock
        assert execution.solver_name == "XROTOR"
        assert execution.result_status == "ok"
        assert len(execution.input_hash) == 64
        assert output.quantities["thrust_ideal"].value == pytest.approx(32.30, rel=1e-3)

    def test_same_request_same_hash(self):
        adapter = XROTORAdapter(xrotor_path=None)
        _, exec1 = adapter.run(_REQUEST)
        _, exec2 = adapter.run(
            PropAnalysisRequest.model_validate(_REQUEST.model_dump())
        )
        assert exec1.input_hash == exec2.input_hash


class TestRealModeNotFabricated:
    """CON-003: 解析を実行していない場合は実行したように見せない。"""

    def test_real_raises_when_unavailable(self):
        adapter = XROTORAdapter(xrotor_path=None)
        with pytest.raises(SolverUnavailableError):
            adapter.run(_REQUEST, execution_mode=ExecutionMode.real)

    def test_real_raises_not_implemented_when_available(self, tmp_path):
        fake_exe = tmp_path / "xrotor.exe"
        fake_exe.write_text("dummy")
        adapter = XROTORAdapter(xrotor_path=str(fake_exe))
        with pytest.raises(SolverNotImplementedError):
            adapter.run(_REQUEST, execution_mode=ExecutionMode.real)

    def test_unsupported_mode_rejected(self):
        adapter = XROTORAdapter(xrotor_path=None)
        with pytest.raises(ValueError):
            adapter.run(_REQUEST, execution_mode=ExecutionMode.analytical_estimate)
