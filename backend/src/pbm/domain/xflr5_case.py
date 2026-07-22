"""XFLR5ハンドオフ(手動実行の入力パッケージ)と結果取込の検証。

Codex版PBM(commit 6a9e400, src/birdman/xflr5.py)からの移植。
- 入力ZIPは「解析結果ではない」ことをマニフェスト・READMEに明示する
- 結果取込はalpha/CL/CD/Cm列が揃った表のみ受理し、欠損値の補完はしない(CON-003)
- 出典: XFLR5 6.62(SourceForge Ticket #57によりコマンド実行は非対応のため
  GUI手動実行+エクスポート表の取込を正式経路とする)
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from enum import StrEnum
from math import isfinite

from pydantic import BaseModel, Field, model_validator

from pbm.adapters.base import BinaryArtifact
from pbm.domain.quantities import Quantity, ensure_angle

XFLR5_INPUT_GENERATOR_VERSION = "pbm-xflr5-handoff-v1"
XFLR5_RESULT_PARSER_VERSION = "pbm-xflr5-polar-table-v1"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_REQUIRED_RESULT_FIELDS = ("alpha", "cl", "cd", "cm")


class Xflr5DataStatus(StrEnum):
    """翼型形状データの根拠状態。"""

    awaiting_reference = "awaiting_reference"  # 形状データ待ち
    estimated = "estimated"
    measured = "measured"


class Xflr5AnalysisKind(StrEnum):
    airfoil_polar = "airfoil_polar"
    wing_or_plane = "wing_or_plane"


class Xflr5Case(BaseModel):
    """手動または設定済み実行でXFLR5を開く前に保存する入力一式。"""

    case_name: str
    analysis_kind: Xflr5AnalysisKind = Xflr5AnalysisKind.airfoil_polar
    data_status: Xflr5DataStatus = Xflr5DataStatus.awaiting_reference
    airfoil_name: str
    airfoil_dat: str | None = None
    reynolds_numbers: list[float] = Field(min_length=1, max_length=20)
    mach_numbers: list[float] = Field(min_length=1, max_length=20)
    ncrit: float = Field(ge=1, le=20, default=9.0)
    alpha_start: Quantity = Quantity(value=-5.0, unit="deg")
    alpha_end: Quantity = Quantity(value=15.0, unit="deg")
    alpha_step: Quantity = Quantity(value=0.5, unit="deg")
    forced_transition_top: float = Field(ge=0, le=1, default=1.0)
    forced_transition_bottom: float = Field(ge=0, le=1, default=1.0)
    input_source: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _validate(self) -> Xflr5Case:
        if not _SAFE_NAME.fullmatch(self.case_name):
            raise ValueError("case_name: ASCII英数字・ドット・ハイフン・アンダースコアのみ")
        if not _SAFE_NAME.fullmatch(self.airfoil_name):
            raise ValueError("airfoil_name: ASCII英数字・ドット・ハイフン・アンダースコアのみ")
        if not self.input_source.strip():
            raise ValueError("input_source: 入力値の出典は必須です")
        if self.data_status is Xflr5DataStatus.awaiting_reference:
            if self.airfoil_dat is not None:
                raise ValueError(
                    "翼型座標を渡す場合はdata_statusをestimated/measuredにしてください"
                )
        elif self.airfoil_dat is None:
            raise ValueError("estimated/measuredの場合は翼型座標(airfoil_dat)が必要です")
        if self.airfoil_dat is not None:
            validate_airfoil_dat(self.airfoil_dat)
        if any(v <= 0 for v in self.reynolds_numbers):
            raise ValueError("Reynolds数はすべて正の値が必要です")
        if any(not 0 <= v < 1 for v in self.mach_numbers):
            raise ValueError("Mach数は0以上1未満が必要です")
        for name in ("alpha_start", "alpha_end", "alpha_step"):
            ensure_angle(getattr(self, name), name)
        start = self.alpha_start.to("deg").value
        end = self.alpha_end.to("deg").value
        step = self.alpha_step.to("deg").value
        if end <= start:
            raise ValueError("alpha_endはalpha_startより大きい必要があります")
        if step <= 0 or step > end - start:
            raise ValueError("alpha_stepは正かつ迎角範囲以下が必要です")
        return self

    @property
    def ready_for_execution(self) -> bool:
        """形状データと出典が揃っている場合のみ真。"""
        return (
            self.data_status is not Xflr5DataStatus.awaiting_reference
            and self.airfoil_dat is not None
        )

    def normalized_payload(self) -> dict:
        return {
            "case_name": self.case_name,
            "analysis_kind": self.analysis_kind.value,
            "data_status": self.data_status.value,
            "airfoil_name": self.airfoil_name,
            "airfoil_geometry_supplied": self.airfoil_dat is not None,
            "reynolds_numbers": list(self.reynolds_numbers),
            "mach_numbers": list(self.mach_numbers),
            "ncrit": self.ncrit,
            "alpha_start_deg": self.alpha_start.to("deg").value,
            "alpha_end_deg": self.alpha_end.to("deg").value,
            "alpha_step_deg": self.alpha_step.to("deg").value,
            "forced_transition_top": self.forced_transition_top,
            "forced_transition_bottom": self.forced_transition_bottom,
            "input_source": self.input_source.strip(),
            "ready_for_execution": self.ready_for_execution,
            "generator_version": XFLR5_INPUT_GENERATOR_VERSION,
            "aerodynamic_result_available": False,
        }

    def create_input_package(self) -> BinaryArtifact:
        """マニフェスト・README・翼型座標を含む上限つきZIPを作成する。

        **これは入力準備であり解析結果ではない**(README/マニフェストに明記)。
        """
        manifest = {
            **self.normalized_payload(),
            "workflow": [
                "XFLR5でairfoil.datを開く(同梱されている場合)",
                "保存されたReynolds・Mach・Ncrit・迎角・遷移値を入力する",
                "選択した解析を実行する",
                "alpha, CL, CD, Cmを含む表をエクスポートする",
                "エクスポートした生の表をProject BirdManへ取り込む",
            ],
            "limitations": [
                "このパッケージは計算済みの空力係数を含まない",
                "XFLR5 6.62はコマンド実行非対応のためGUI手動実行が必要",
                "プロセスが正常終了しても空力的な妥当性は保証されない",
            ],
        }
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            )
            archive.writestr(
                "README.txt",
                (
                    "Project BirdMan XFLR5 handoff\n"
                    "This archive is input preparation, not an analysis result.\n"
                    "Do not record it as a real aerodynamic result.\n"
                    "See manifest.json for units, evidence status, and the manual workflow.\n"
                ),
            )
            if self.airfoil_dat is not None:
                archive.writestr("airfoil.dat", _normalized_text(self.airfoil_dat))
        content = stream.getvalue()
        if len(content) > 2_000_000:
            raise ValueError("XFLR5入力パッケージが2000000バイトを超えています")
        return BinaryArtifact.from_bytes(f"{self.case_name}-xflr5-input.zip", content)


def validate_airfoil_dat(content: str) -> str:
    """翼型座標ファイルの形式検証(形状の空力的妥当性までは主張しない)。"""
    normalized = _normalized_text(content)
    if len(normalized.encode("utf-8")) > 500_000:
        raise ValueError("翼型座標データが500000バイトを超えています")
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if len(lines) < 11:
        raise ValueError("翼型DATは名称行+10行以上の座標が必要です")
    for line in lines[1:]:
        parts = line.replace(",", " ").split()
        if len(parts) != 2:
            raise ValueError("翼型座標の各行はxとyの2値が必要です")
        try:
            x_value, y_value = (float(part) for part in parts)
        except ValueError as error:
            raise ValueError("翼型座標は数値である必要があります") from error
        if not (isfinite(x_value) and isfinite(y_value)):
            raise ValueError("翼型座標は有限値である必要があります")
        if not -1.0 <= x_value <= 2.0 or not -1.0 <= y_value <= 1.0:
            raise ValueError("翼型座標が正規化範囲(x:−1〜2, y:−1〜1)を外れています")
    return normalized


def parse_xflr5_result_table(raw_text: str) -> dict:
    """alpha/CL/CD/Cm列が明示された行のみパースする。派生値の追加はしない。"""
    if not raw_text.strip():
        raise ValueError("XFLR5エクスポート結果が空です")
    if len(raw_text.encode("utf-8")) > 2_000_000:
        raise ValueError("XFLR5エクスポート結果が2000000バイトを超えています")
    lines = [
        line.strip()
        for line in raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip() and not line.lstrip().startswith(("#", "//"))
    ]
    header_index = -1
    header: list[str] = []
    delimiter: str | None = None
    for index, line in enumerate(lines):
        fields, candidate = _split_table_line(line)
        normalized = [_normalized_header(v) for v in fields]
        if all(required in normalized for required in _REQUIRED_RESULT_FIELDS):
            header_index = index
            header = normalized
            delimiter = candidate
            break
    if header_index < 0:
        raise ValueError("XFLR5結果にはalpha, CL, CD, Cmの列見出しが必要です")
    indexes = {name: header.index(name) for name in _REQUIRED_RESULT_FIELDS}
    optional_names = ("cdp", "top_xtr", "bot_xtr", "cpmin", "xcp")
    optional_indexes = {name: header.index(name) for name in optional_names if name in header}
    rows: list[dict[str, float]] = []
    for line in lines[header_index + 1 :]:
        fields = _split_with_delimiter(line, delimiter)
        if not fields or all(set(field) <= {"-", "="} for field in fields):
            continue
        required_width = max((*indexes.values(), *optional_indexes.values()), default=-1) + 1
        if len(fields) < required_width:
            continue
        try:
            row = {name: _finite_float(fields[col]) for name, col in indexes.items()}
            row.update(
                {name: _finite_float(fields[col]) for name, col in optional_indexes.items()}
            )
        except ValueError:
            continue
        rows.append(row)
    if not rows:
        raise ValueError("必要な列見出しの下に数値行が見つかりませんでした")
    return {
        "parser_version": XFLR5_RESULT_PARSER_VERSION,
        "columns": list(rows[0]),
        "rows": rows,
        "row_count": len(rows),
        "required_columns_complete": True,
        "derived_values_added": False,
    }


def _split_table_line(line: str) -> tuple[list[str], str | None]:
    for delimiter in ("\t", ",", ";"):
        if delimiter in line:
            return next(csv.reader([line], delimiter=delimiter)), delimiter
    return line.split(), None


def _split_with_delimiter(line: str, delimiter: str | None) -> list[str]:
    if delimiter is None:
        return line.split()
    return next(csv.reader([line], delimiter=delimiter))


def _normalized_header(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    aliases = {
        "a": "alpha",
        "bottom_xtr": "bot_xtr",
    }
    return aliases.get(cleaned, cleaned)


def _finite_float(value: str) -> float:
    number = float(value)
    if not isfinite(number):
        raise ValueError("number is not finite")
    return number


def _normalized_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")
