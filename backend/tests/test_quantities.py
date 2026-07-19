"""Quantity(単位付き物理量)の単体テスト(NFR-001, NFR-005)。"""

import pytest
from pydantic import ValidationError

from pbm.domain.errors import UnitDimensionError
from pbm.domain.quantities import Quantity, ensure_dimension


class TestConstruction:
    def test_basic(self):
        q = Quantity(value=60.0, unit="kg")
        assert q.value == 60.0
        assert q.unit == "kg"

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_non_finite(self, bad):
        with pytest.raises(ValidationError, match="NaN"):
            Quantity(value=bad, unit="kg")

    def test_rejects_unknown_unit(self):
        with pytest.raises(ValidationError, match="解釈できない単位"):
            Quantity(value=1.0, unit="totally_bogus_unit")


class TestConversion:
    def test_lb_to_kg(self):
        q = Quantity(value=132.27735731092653, unit="lb")  # = 60 kg ちょうど
        assert q.to("kg").value == pytest.approx(60.0, rel=1e-12)

    def test_kmh_to_si(self):
        q = Quantity(value=36.0, unit="km/h")
        assert q.magnitude_si == pytest.approx(10.0, rel=1e-12)

    def test_si_normalization(self):
        q = Quantity(value=1.225, unit="g/cm^3")
        si = q.si()
        assert si.value == pytest.approx(1225.0, rel=1e-12)
        assert "kilogram" in si.unit and "meter" in si.unit

    def test_incompatible_conversion_raises(self):
        with pytest.raises(UnitDimensionError):
            Quantity(value=1.0, unit="kg").to("m")


class TestDimensionCheck:
    def test_matching_dimension_passes(self):
        ensure_dimension(Quantity(value=60, unit="kg"), "[mass]")
        ensure_dimension(Quantity(value=7.5, unit="m/s"), "[length] / [time]")
        ensure_dimension(Quantity(value=1.2, unit="kg/m^3"), "[mass] / [length] ** 3")

    def test_mismatch_raises(self):
        with pytest.raises(UnitDimensionError, match="次元が不正"):
            ensure_dimension(Quantity(value=60, unit="m"), "[mass]", field_name="pilot_mass")


class TestFrontendOfferedUnits:
    """フロントエンドの単位選択UI(T-114)が提供する全単位がバックエンドで受理される。

    frontend/app/projects/[id]/page.tsx のquantityField単位リストと同期を保つこと。
    """

    @pytest.mark.parametrize(
        ("unit", "dimension"),
        [
            ("kg", "[mass]"), ("g", "[mass]"), ("lb", "[mass]"),
            ("W", "[power]"), ("kW", "[power]"),
            ("m/s", "[length] / [time]"), ("km/h", "[length] / [time]"),
            ("knot", "[length] / [time]"),
            ("m", "[length]"), ("cm", "[length]"), ("mm", "[length]"), ("ft", "[length]"),
            ("kg/m^3", "[mass] / [length] ** 3"), ("g/L", "[mass] / [length] ** 3"),
        ],
    )
    def test_unit_parses_with_expected_dimension(self, unit, dimension):
        ensure_dimension(Quantity(value=1.0, unit=unit), dimension)

    def test_g_per_liter_equals_kg_per_m3(self):
        # 1 g/L = 1 kg/m³(空気密度の代替単位として提供)
        q = Quantity(value=1.225, unit="g/L")
        assert q.magnitude_si == pytest.approx(1.225, rel=1e-12)
