"""サイジング実行サービス: 計算エンジンの呼び出しと実行メタデータの付与。

計算式そのものは pbm.calculation にのみ存在する(開発ルール: 計算式をUI/APIに書かない)。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pbm
from pbm.adapters.base import ExecutionMode, ResultStatus, SolverExecution
from pbm.calculation.initial_sizing import run_initial_sizing
from pbm.domain.requirements import RequirementSpecInput
from pbm.domain.results import SizingOutput
from pbm.workflow.hashing import compute_input_hash

SOLVER_NAME = "pbm.initial_sizing"

__all__ = ["compute_input_hash", "execute_sizing"]


def execute_sizing(spec: RequirementSpecInput) -> tuple[SizingOutput, SolverExecution]:
    """初期サイジングを実行し、結果と実行メタデータを返す。

    execution_mode は analytical_estimate(理論式による推定。外部ソルバー不使用)。
    """
    input_hash = compute_input_hash(spec)
    started_at = datetime.now(UTC)
    outputs = run_initial_sizing(spec)  # 失敗時はCalculationErrorが伝播(握りつぶさない)
    finished_at = datetime.now(UTC)
    execution = SolverExecution(
        solver_name=SOLVER_NAME,
        solver_version=pbm.__version__,
        execution_mode=ExecutionMode.analytical_estimate,
        input_hash=input_hash,
        started_at=started_at,
        finished_at=finished_at,
        result_status=ResultStatus.ok,
    )
    return outputs, execution
