"""解析ソフト・CAD・レポート出力の共通インターフェース(ARCHITECTURE.md §3)。

Phase 1 では初期サイジング(analytical_estimate)がSolverExecutionを使用する。
XFLR5 / XROTOR / Fusion 360 の具象アダプターは Phase 2 / 5 で実装する(TASKS T-202, T-203, T-501)。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class ExecutionMode(StrEnum):
    """実解析とモック等を機械的に区別する(FR-042, CON-003)。"""

    real = "real"                                  # 実際に外部ソルバーを実行した
    mock = "mock"                                  # ソルバー無しの模擬結果(開発・テスト用)
    imported = "imported"                          # 外部で実行済みの結果を取り込んだ
    analytical_estimate = "analytical_estimate"    # 理論式による解析的推定(ソルバー不使用)


class ResultStatus(StrEnum):
    ok = "ok"
    failed = "failed"
    partial = "partial"


class SolverExecution(BaseModel):
    """すべての解析・計算実行に付与する実行メタデータ(FR-024, FR-042)。"""

    solver_name: str
    solver_version: str
    execution_mode: ExecutionMode
    input_hash: str
    started_at: datetime
    finished_at: datetime
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    raw_output_path: str | None = None
    parser_version: str | None = None
    result_status: ResultStatus


class SolverAdapter(ABC):
    """外部解析ソフトの共通基底。外部ソフトは必ずこの層を経由する(PROJECT_BRIEF §8)。"""

    name: str
    version: str

    @abstractmethod
    def is_available(self) -> bool:
        """実行可能か(実行パス設定・存在確認)。Falseならrealモードは使用不可。"""

    @abstractmethod
    def run(self, request: Any) -> Any:
        """解析を実行し、SolverExecutionを含む結果を返す。失敗時もログを保存する(FR-044)。"""


class AerodynamicSolverAdapter(SolverAdapter, ABC):
    """空力解析(XFLR5等)。Phase 2。"""


class PropellerSolverAdapter(SolverAdapter, ABC):
    """プロペラ解析(XROTOR等)。Phase 2。"""


class CADAdapter(ABC):
    """CAD連携(Fusion 360等)。Phase 5。承認済み設計のみ出力可(FR-004)。"""

    @abstractmethod
    def export_parameters(self, design: Any, destination: Path) -> Path: ...


class ReportExporter(ABC):
    """レポート出力。Phase 1はHTML、Phase 5でPDF/CSV。"""

    format_name: str

    @abstractmethod
    def export(self, report_context: Any, destination: Path) -> Path: ...
