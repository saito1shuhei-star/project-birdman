"""XFLR5アダプター(Step 5 / TASKS T-202)。

段階的実装方針(ROADMAP.md Phase 2、PROJECT_BRIEF §12):
1. mock先行: XFLR5未接続でもStep 5のデータ形式・トレーサビリティを検証できる
2. real後続: 実際のXFLR5実行・結果パース(TASKS T-203以降で継続実装)

**現時点でrealモードは未実装。** 未実装のまま実行済みのように見せることは
CON-003(解析未実行を実行済みに見せない)に反するため、real要求時は
明示的に SolverUnavailableError / SolverNotImplementedError を送出する。
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pbm
from pbm.adapters.base import AerodynamicSolverAdapter, ExecutionMode, ResultStatus, SolverExecution
from pbm.calculation.aero_mock_polar import generate_mock_polar
from pbm.domain.aero_analysis import AeroAnalysisOutput, AeroAnalysisRequest
from pbm.domain.errors import SolverNotImplementedError, SolverUnavailableError
from pbm.workflow.hashing import compute_input_hash

_MOCK_SOLVER_VERSION = f"pbm-mock-lifting-line-{pbm.__version__}"


class XFLR5Adapter(AerodynamicSolverAdapter):
    """XFLR5空力解析の共通インターフェース実装。"""

    name = "XFLR5"

    def __init__(self, xflr5_path: str | None = None) -> None:
        # 明示指定がなければ環境変数PBM_XFLR5_PATH(ARCHITECTURE.md §8)を参照する
        if xflr5_path is not None:
            self._xflr5_path = xflr5_path
        else:
            self._xflr5_path = os.environ.get("PBM_XFLR5_PATH")
        self.version = "unknown(real未接続)"

    def is_available(self) -> bool:
        """PBM_XFLR5_PATHが設定され、実行ファイルが実在するか。"""
        return bool(self._xflr5_path) and Path(self._xflr5_path).exists()

    def run(
        self,
        request: AeroAnalysisRequest,
        execution_mode: ExecutionMode = ExecutionMode.mock,
    ) -> tuple[AeroAnalysisOutput, SolverExecution]:
        """空力解析を実行する。

        execution_mode=mock: 揚力線理論による近似ポーラを生成する(実XFLR5ではない)。
        execution_mode=real: 現時点では未実装。利用不可ならSolverUnavailableError、
            利用可能でもSolverNotImplementedError(実行連携は継続実装中)。
        """
        if execution_mode == ExecutionMode.real:
            if not self.is_available():
                raise SolverUnavailableError(
                    "XFLR5が利用できません(PBM_XFLR5_PATH未設定または実行ファイル不在)。"
                    "realモードへの黙示的なmockフォールバックは行いません(CON-003)。"
                    "mockモードを明示的に指定するか、PBM_XFLR5_PATHを設定してください。"
                )
            raise SolverNotImplementedError(
                "XFLR5のreal実行連携は未実装です(TASKS T-202の継続作業)。"
                "現時点で利用できるのはexecution_mode=mockのみです。"
            )
        if execution_mode != ExecutionMode.mock:
            raise ValueError(
                f"XFLR5Adapterはmock/realのみサポートします(指定値: {execution_mode})"
            )

        input_hash = compute_input_hash(request)
        started_at = datetime.now(UTC)
        output = generate_mock_polar(request)  # 失敗時は例外が伝播(握りつぶさない)
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
