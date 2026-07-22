"""XROTORアダプター(Step 6 / TASKS T-203)。

- mock: 運動量理論による理想値(pbm.calculation.prop_mock_momentum)
- real: **サーバー設定された実行ファイルによる実実行**(Codex版PBM commit 6a9e400
  src/birdman/xrotor_adapter.py からの移植)。入力スクリプト・stdout/stderr・
  生成された生ファイルをすべて証跡(BinaryArtifact)として保持する(FR-044)
- imported: 手動実行したXROTORの公式サマリテキストの取り込み(parse_xrotor_summary)。
  不完全なサマリからの値の捏造はしない(CON-003)

実行ファイルは環境変数 PBM_XROTOR_PATH、版名は PBM_XROTOR_VERSION(XROTOR 7.55を想定。
7.69へ変更する場合は入力順・結果形式の再確認が必要: REFERENCES.md)。
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

import pbm
from pbm.adapters.base import (
    BinaryArtifact,
    ExecutionMode,
    PropellerSolverAdapter,
    ResultStatus,
    SolverExecution,
)
from pbm.calculation.prop_mock_momentum import run_mock_momentum_analysis
from pbm.domain.errors import SolverNotImplementedError, SolverUnavailableError
from pbm.domain.prop_analysis import PropAnalysisOutput, PropAnalysisRequest
from pbm.workflow.hashing import compute_input_hash

_MOCK_SOLVER_VERSION = f"pbm-mock-momentum-{pbm.__version__}"
XROTOR_RAW_PARSER_VERSION = "pbm-xrotor-raw-v1"
XROTOR_SUMMARY_PARSER_VERSION = "pbm-xrotor-summary-v1"
_MAX_ARTIFACT_BYTES = 2_000_000
_MAX_TOTAL_ARTIFACT_BYTES = 10_000_000


class XrotorRunStatus(StrEnum):
    """プロセスとしての結果(空力的な妥当性とは独立に保持する)。"""

    completed = "completed"
    failed = "failed"
    timed_out = "timed_out"


class XrotorScriptRunResult(BaseModel):
    """実実行1回分の完全な証跡(外部ソフト方針: FR-042/FR-044)。"""

    command: list[str]
    input_file: BinaryArtifact
    executed_at: datetime
    exit_code: int | None
    stdout: str
    stderr: str
    raw_result_files: list[BinaryArtifact]
    software_version: str
    parser_version: str
    execution_mode: ExecutionMode
    run_status: XrotorRunStatus
    is_real_analysis: bool
    parsed_summary: dict[str, float] | None = None  # 公式サマリが完全な場合のみ


_SUMMARY_FIELDS = {
    "thrust_n": re.compile(r"thrust\s*\(N\)\s*[:=]\s*([-+0-9.eE]+)", re.IGNORECASE),
    "power_w": re.compile(r"power\s*\(W\)\s*[:=]\s*([-+0-9.eE]+)", re.IGNORECASE),
    "torque_nm": re.compile(r"torque\s*\(N-m\)\s*[:=]\s*([-+0-9.eE]+)", re.IGNORECASE),
    "efficiency": re.compile(r"Efficiency\s*[:=]\s*([-+0-9.eE]+)", re.IGNORECASE),
    "flight_speed_mps": re.compile(r"speed\s*\(m/s\)\s*[:=]\s*([-+0-9.eE]+)", re.IGNORECASE),
    "rotational_speed_rpm": re.compile(r"\brpm\s*[:=]\s*([-+0-9.eE]+)", re.IGNORECASE),
}


def parse_xrotor_summary(stdout: str) -> dict[str, float] | None:
    """公式テキストサマリが完全な場合のみパースする。欠損値の補完・捏造はしない。"""
    parsed: dict[str, float] = {}
    for name, pattern in _SUMMARY_FIELDS.items():
        match = pattern.search(stdout)
        if match is None:
            return None
        parsed[name] = float(match.group(1))
    return parsed


def validate_xrotor_script(script: str) -> bytes:
    """XROTOR入力スクリプトの安全検証(パス脱出・非ASCII・制御文字を拒否)。"""
    if not script.strip():
        raise ValueError("XROTOR入力スクリプトが空です")
    if len(script.encode("utf-8")) > 200_000:
        raise ValueError("XROTOR入力スクリプトが200000バイトを超えています")
    if "\x00" in script:
        raise ValueError("XROTOR入力スクリプトにNUL文字が含まれています")
    if any(ch in script for ch in ("\\", "/", ":")):
        raise ValueError("XROTOR入力スクリプトにパス区切り文字は使用できません")
    if any(ord(ch) > 127 for ch in script):
        raise ValueError("XROTOR入力スクリプトはASCIIのみ使用できます")
    for ch in script:
        if ch not in "\r\n\t" and not ch.isprintable():
            raise ValueError("XROTOR入力スクリプトに未対応の制御文字が含まれています")
    return script.replace("\r\n", "\n").replace("\r", "\n").encode("ascii")


class XROTORAdapter(PropellerSolverAdapter):
    """XROTORプロペラ解析の共通インターフェース実装。"""

    name = "XROTOR"

    def __init__(
        self,
        xrotor_path: str | None = None,
        software_version: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        # 明示指定がなければ環境変数PBM_XROTOR_PATH / PBM_XROTOR_VERSION(ARCHITECTURE.md §8)
        if xrotor_path is not None:
            self._xrotor_path = xrotor_path
        else:
            self._xrotor_path = os.environ.get("PBM_XROTOR_PATH")
        if software_version is not None:
            self._software_version = software_version
        else:
            self._software_version = os.environ.get("PBM_XROTOR_VERSION")
        self._timeout_seconds = timeout_seconds
        self.version = self._software_version or "unknown(real未接続)"

    def is_available(self) -> bool:
        """PBM_XROTOR_PATHが設定され、実行ファイルが実在するか。"""
        return bool(self._xrotor_path) and Path(self._xrotor_path).exists()

    def run_script(
        self,
        input_script: str,
        execution_mode: ExecutionMode = ExecutionMode.mock,
    ) -> XrotorScriptRunResult:
        """XROTOR入力スクリプトを実行する(real)か、明示的なモック記録を返す(mock)。

        realはシェルを介さず一時ディレクトリで隔離実行し、入力・stdout/stderr・
        生成ファイルをすべてBinaryArtifactで保持する(Codex版からの移植)。
        """
        input_bytes = validate_xrotor_script(input_script)
        executed_at = datetime.now(UTC)
        input_artifact = BinaryArtifact.from_bytes("xrotor.in", input_bytes)

        if execution_mode == ExecutionMode.mock:
            mock_bytes = (
                b"MOCK RESULT ONLY\n"
                b"No XROTOR executable was run and no aerodynamic result was calculated.\n"
            )
            return XrotorScriptRunResult(
                command=["mock:xrotor"],
                input_file=input_artifact,
                executed_at=executed_at,
                exit_code=0,
                stdout="MOCK XROTOR run only. No aerodynamic analysis was performed.",
                stderr="",
                raw_result_files=[BinaryArtifact.from_bytes("mock-result.txt", mock_bytes)],
                software_version="mock-not-applicable",
                parser_version=XROTOR_RAW_PARSER_VERSION,
                execution_mode=ExecutionMode.mock,
                run_status=XrotorRunStatus.completed,
                is_real_analysis=False,
            )
        if execution_mode != ExecutionMode.real:
            raise ValueError(f"run_scriptはmock/realのみサポートします(指定: {execution_mode})")

        if not self.is_available():
            raise SolverUnavailableError(
                "XROTORが利用できません(PBM_XROTOR_PATH未設定または実行ファイル不在)"
            )
        if not (self._software_version and self._software_version.strip()):
            raise SolverUnavailableError(
                "real実行にはPBM_XROTOR_VERSION(実行ファイルの版名)が必要です"
            )
        executable = Path(self._xrotor_path).expanduser().resolve(strict=False)
        if not executable.is_file():
            raise SolverUnavailableError("設定されたXROTOR実行ファイルが見つかりません")
        command = [str(executable)]
        creation_flags = (
            subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )
        with tempfile.TemporaryDirectory(prefix="pbm-xrotor-") as raw_directory:
            directory = Path(raw_directory)
            input_path = directory / "xrotor.in"
            input_path.write_bytes(input_bytes)
            try:
                completed = subprocess.run(
                    command,
                    input=input_bytes,
                    cwd=directory,
                    capture_output=True,
                    timeout=self._timeout_seconds,
                    shell=False,
                    check=False,
                    creationflags=creation_flags,
                )
                status = (
                    XrotorRunStatus.completed
                    if completed.returncode == 0
                    else XrotorRunStatus.failed
                )
                exit_code: int | None = completed.returncode
                stdout_bytes = completed.stdout
                stderr_bytes = completed.stderr
            except subprocess.TimeoutExpired as error:
                status = XrotorRunStatus.timed_out
                exit_code = None
                stdout_bytes = error.stdout or b""
                stderr_bytes = error.stderr or b""
            raw_results = _collect_result_files(directory, excluded=input_path)

        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        return XrotorScriptRunResult(
            command=command,
            input_file=input_artifact,
            executed_at=executed_at,
            exit_code=exit_code,
            stdout=stdout_text,
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            raw_result_files=raw_results,
            software_version=self._software_version.strip(),
            parser_version=XROTOR_RAW_PARSER_VERSION,
            execution_mode=ExecutionMode.real,
            run_status=status,
            is_real_analysis=True,
            parsed_summary=parse_xrotor_summary(stdout_text),
        )

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
                "運動量理論リクエスト(PropAnalysisRequest)のreal実行は未対応です。"
                "実XROTOR実行は構造化ケース(XrotorCase)からrun_script()を使用してください。"
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


def _collect_result_files(directory: Path, *, excluded: Path) -> list[BinaryArtifact]:
    """作業ディレクトリに生成されたファイルをサイズ上限つきで回収する(証跡)。"""
    artifacts: list[BinaryArtifact] = []
    total_size = 0
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path == excluded or not path.is_file():
            continue
        size = path.stat().st_size
        if size > _MAX_ARTIFACT_BYTES:
            raise ValueError(
                f"XROTOR結果ファイル {path.name!r} が {_MAX_ARTIFACT_BYTES} バイトを超えています"
            )
        total_size += size
        if total_size > _MAX_TOTAL_ARTIFACT_BYTES:
            raise ValueError(
                f"XROTOR結果ファイルの合計が {_MAX_TOTAL_ARTIFACT_BYTES} バイトを超えています"
            )
        artifacts.append(BinaryArtifact.from_bytes(path.name, path.read_bytes()))
    return artifacts
