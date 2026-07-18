"""XROTORアダプター(Step 6 / TASKS T-203)。

段階的実装方針はXFLR5アダプター(pbm.adapters.xflr5)と同一:
1. mock先行: XROTOR未接続でも運動量理論による理想値でデータ形式を検証できる
2. real後続: 実際のXROTOR実行・結果パース(実機XROTORでの検証が必要)

**現時点でrealモードは未実装。** 未実装のまま実行済みのように見せることは
CON-003に反するため、real要求時は明示的に例外を送出する。
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pbm
from pbm.adapters.base import ExecutionMode, PropellerSolverAdapter, ResultStatus, SolverExecution
from pbm.calculation.prop_mock_momentum import run_mock_momentum_analysis
from pbm.domain.errors import SolverNotImplementedError, SolverUnavailableError
from pbm.domain.prop_analysis import PropAnalysisOutput, PropAnalysisRequest
from pbm.workflow.hashing import compute_input_hash

_MOCK_SOLVER_VERSION = f"pbm-mock-momentum-{pbm.__version__}"


class XROTORAdapter(PropellerSolverAdapter):
    """XROTORプロペラ解析の共通インターフェース実装。"""

    name = "XROTOR"

    def __init__(self, xrotor_path: str | None = None) -> None:
        # 明示指定がなければ環境変数PBM_XROTOR_PATH(ARCHITECTURE.md §8)を参照する
        if xrotor_path is not None:
            self._xrotor_path = xrotor_path
        else:
            self._xrotor_path = os.environ.get("PBM_XROTOR_PATH")
        self.version = "unknown(real未接続)"

    def is_available(self) -> bool:
        """PBM_XROTOR_PATHが設定され、実行ファイルが実在するか。"""
        return bool(self._xrotor_path) and Path(self._xrotor_path).exists()

    def run(
        self,
        request: PropAnalysisRequest,
        execution_mode: ExecutionMode = ExecutionMode.mock,
    ) -> tuple[PropAnalysisOutput, SolverExecution]:
        """プロペラ解析を実行する。

        execution_mode=mock: 運動量理論による理想性能の推定(実XROTORではない)。
        execution_mode=real: 現時点では未実装。利用不可ならSolverUnavailableError、
            利用可能でもSolverNotImplementedError(実行連携は継続実装中)。
        """
        if execution_mode == ExecutionMode.real:
            if not self.is_available():
                raise SolverUnavailableError(
                    "XROTORが利用できません(PBM_XROTOR_PATH未設定または実行ファイル不在)。"
                    "realモードへの黙示的なmockフォールバックは行いません(CON-003)。"
                    "mockモードを明示的に指定するか、PBM_XROTOR_PATHを設定してください。"
                )
            raise SolverNotImplementedError(
                "XROTORのreal実行連携は未実装です(TASKS T-203の継続作業)。"
                "現時点で利用できるのはexecution_mode=mockのみです。"
            )
        if execution_mode != ExecutionMode.mock:
            raise ValueError(
                f"XROTORAdapterはmock/realのみサポートします(指定値: {execution_mode})"
            )

        input_hash = compute_input_hash(request)
        started_at = datetime.now(UTC)
        output = run_mock_momentum_analysis(request)  # 失敗時は例外が伝播(握りつぶさない)
        finished_at = datetime.now(UTC)

        execution = SolverExecution(
            solver_name=self.name,
            solver_version=_MOCK_SOLVER_VERSION,
            execution_mode=ExecutionMode.mock,
            input_hash=input_hash,
            started_at=started_at,
            finished_at=finished_at,
            result_status=ResultStatus.ok,
        )
        return output, execution
