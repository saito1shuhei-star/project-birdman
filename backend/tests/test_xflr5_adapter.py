"""XFLR5Adapterのテスト(T-202)。mock/realの区別とreal未実装の明示を検証する。"""

import pytest

from pbm.adapters.base import ExecutionMode
from pbm.adapters.xflr5 import XFLR5Adapter
from pbm.domain.aero_analysis import AeroAnalysisRequest
from pbm.domain.errors import SolverNotImplementedError, SolverUnavailableError

_REQUEST = AeroAnalysisRequest(
    aspect_ratio=10.0,
    oswald_efficiency=0.9,
    parasite_drag_coefficient=0.02,
    cl_max=1.4,
)


class TestAvailability:
    def test_unavailable_when_path_unset(self):
        adapter = XFLR5Adapter(xflr5_path=None)
        assert adapter.is_available() is False

    def test_unavailable_when_path_does_not_exist(self, tmp_path):
        adapter = XFLR5Adapter(xflr5_path=str(tmp_path / "nonexistent_xflr5.exe"))
        assert adapter.is_available() is False

    def test_available_when_path_exists(self, tmp_path):
        fake_exe = tmp_path / "xflr5.exe"
        fake_exe.write_text("dummy")
        adapter = XFLR5Adapter(xflr5_path=str(fake_exe))
        assert adapter.is_available() is True

    def test_env_var_used_when_path_not_explicit(self, tmp_path, monkeypatch):
        fake_exe = tmp_path / "xflr5.exe"
        fake_exe.write_text("dummy")
        monkeypatch.setenv("PBM_XFLR5_PATH", str(fake_exe))
        adapter = XFLR5Adapter()
        assert adapter.is_available() is True


class TestMockRun:
    def test_default_mode_is_mock(self):
        adapter = XFLR5Adapter(xflr5_path=None)
        output, execution = adapter.run(_REQUEST)
        assert execution.execution_mode == ExecutionMode.mock
        assert execution.solver_name == "XFLR5"
        assert execution.result_status == "ok"
        assert len(execution.input_hash) == 64
        assert output.polar

    def test_mock_available_regardless_of_xflr5_presence(self, tmp_path):
        fake_exe = tmp_path / "xflr5.exe"
        fake_exe.write_text("dummy")
        adapter = XFLR5Adapter(xflr5_path=str(fake_exe))
        _, execution = adapter.run(_REQUEST, execution_mode=ExecutionMode.mock)
        assert execution.execution_mode == ExecutionMode.mock

    def test_same_request_same_hash(self):
        adapter = XFLR5Adapter(xflr5_path=None)
        _, exec1 = adapter.run(_REQUEST)
        _, exec2 = adapter.run(AeroAnalysisRequest.model_validate(_REQUEST.model_dump()))
        assert exec1.input_hash == exec2.input_hash


class TestRealModeNotFabricated:
    """CON-003: 解析を実行していない場合は実行したように見せない。"""

    def test_real_raises_when_unavailable(self):
        adapter = XFLR5Adapter(xflr5_path=None)
        with pytest.raises(SolverUnavailableError):
            adapter.run(_REQUEST, execution_mode=ExecutionMode.real)

    def test_real_raises_not_implemented_when_available(self, tmp_path):
        fake_exe = tmp_path / "xflr5.exe"
        fake_exe.write_text("dummy")
        adapter = XFLR5Adapter(xflr5_path=str(fake_exe))
        assert adapter.is_available() is True
        with pytest.raises(SolverNotImplementedError):
            adapter.run(_REQUEST, execution_mode=ExecutionMode.real)

    def test_unsupported_mode_rejected(self):
        adapter = XFLR5Adapter(xflr5_path=None)
        with pytest.raises(ValueError):
            adapter.run(_REQUEST, execution_mode=ExecutionMode.imported)
