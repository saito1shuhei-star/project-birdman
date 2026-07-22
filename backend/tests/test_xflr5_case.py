"""XFLR5ハンドオフ・結果表取込のテスト(Codex版から移植・適応)。"""

import base64
import io
import json
import zipfile

import pytest
from pydantic import ValidationError

from pbm.domain.xflr5_case import (
    Xflr5Case,
    parse_xflr5_result_table,
    validate_airfoil_dat,
)

_DAT = "TESTFOIL\n" + "\n".join(
    f"{x:.4f} {y:.4f}"
    for x, y in [
        (1.0, 0.0), (0.8, 0.02), (0.6, 0.04), (0.4, 0.05), (0.2, 0.04),
        (0.0, 0.0), (0.2, -0.02), (0.4, -0.02), (0.6, -0.015), (0.8, -0.01), (1.0, 0.0),
    ]
)


def _case(**overrides) -> dict:
    base = {
        "case_name": "wing-polar-01",
        "airfoil_name": "DAE-11",
        "data_status": "estimated",
        "airfoil_dat": _DAT,
        "reynolds_numbers": [500_000],
        "mach_numbers": [0.03],
        "input_source": "翼型座標: UIUCデータベース(テスト用ダミー形状)",
    }
    return base | overrides


class TestHandoffPackage:
    def test_creates_zip_with_manifest_and_disclaimer(self):
        case = Xflr5Case.model_validate(_case())
        package = case.create_input_package()
        content = base64.b64decode(package.content_base64)
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            assert {"manifest.json", "README.txt", "airfoil.dat"} <= names
            manifest = json.loads(archive.read("manifest.json"))
            readme = archive.read("README.txt").decode("utf-8")
        assert manifest["aerodynamic_result_available"] is False  # 結果を含まないことを明示
        assert manifest["ready_for_execution"] is True
        assert "not an analysis result" in readme

    def test_awaiting_reference_without_dat(self):
        case = Xflr5Case.model_validate(
            _case(data_status="awaiting_reference", airfoil_dat=None)
        )
        assert case.ready_for_execution is False

    def test_estimated_requires_dat(self):
        with pytest.raises(ValidationError, match="翼型座標"):
            Xflr5Case.model_validate(_case(airfoil_dat=None))

    def test_alpha_range_validation(self):
        with pytest.raises(ValidationError, match="alpha_end"):
            Xflr5Case.model_validate(
                _case(
                    alpha_start={"value": 10, "unit": "deg"},
                    alpha_end={"value": 5, "unit": "deg"},
                )
            )

    def test_mach_range_validation(self):
        with pytest.raises(ValidationError, match="Mach"):
            Xflr5Case.model_validate(_case(mach_numbers=[1.2]))


class TestAirfoilDat:
    def test_valid_dat_accepted(self):
        assert validate_airfoil_dat(_DAT) == _DAT

    def test_too_few_rows_rejected(self):
        with pytest.raises(ValueError, match="10行以上"):
            validate_airfoil_dat("FOIL\n1.0 0.0\n0.5 0.1\n0.0 0.0")

    def test_out_of_range_coordinates_rejected(self):
        bad = "FOIL\n" + "\n".join(f"{x} 5.0" for x in range(11))
        with pytest.raises(ValueError, match="正規化範囲"):
            validate_airfoil_dat(bad)


class TestResultTableParser:
    _TABLE = """
    xflr5 v6.62 polar export
    alpha    CL      CD      Cm
    ------  ------  ------  ------
    -2.0    0.11    0.012   -0.06
     0.0    0.35    0.011   -0.07
     2.0    0.58    0.012   -0.07
    """

    def test_parses_required_columns(self):
        result = parse_xflr5_result_table(self._TABLE)
        assert result["row_count"] == 3
        assert result["rows"][1] == {"alpha": 0.0, "cl": 0.35, "cd": 0.011, "cm": -0.07}
        assert result["derived_values_added"] is False  # 派生値を勝手に足さない

    def test_tab_separated_with_alias_header(self):
        table = "a\tCL\tCD\tCm\n1.0\t0.4\t0.01\t-0.05\n"
        result = parse_xflr5_result_table(table)
        assert result["rows"][0]["alpha"] == 1.0

    def test_missing_cm_column_rejected(self):
        with pytest.raises(ValueError, match="Cm"):
            parse_xflr5_result_table("alpha CL CD\n1.0 0.4 0.01\n")

    def test_no_numeric_rows_rejected(self):
        with pytest.raises(ValueError, match="数値行"):
            parse_xflr5_result_table("alpha CL CD Cm\n---- ---- ---- ----\n")

    def test_optional_columns_captured(self):
        table = "alpha CL CD Cm CDp Top_Xtr Bot_Xtr\n2.0 0.5 0.01 -0.06 0.004 0.7 1.0\n"
        result = parse_xflr5_result_table(table)
        assert result["rows"][0]["cdp"] == 0.004
        assert result["rows"][0]["bot_xtr"] == 1.0
