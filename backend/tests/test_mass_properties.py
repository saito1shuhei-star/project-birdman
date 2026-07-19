"""質量特性計算の手計算リファレンステスト(T-302)。

RC-M1: 部品A 10kg@(x=1,y=0,z=0)、部品B 30kg@(x=3,y=0,z=0)
→ 総質量40kg、x_cg = (10·1+30·3)/40 = 2.5 m
→ Iyy(重心まわり) = 10·(1−2.5)² + 30·(3−2.5)² = 22.5 + 7.5 = 30 kg·m²
→ Ixx = 0(全部品がx軸上)、Izz = Iyy = 30
"""

import pytest
from pydantic import ValidationError

from pbm.calculation.mass_properties import compute_mass_properties
from pbm.domain.errors import CalculationError
from pbm.domain.mass_item import MassItemInput
from pbm.domain.quantities import Quantity


def _item(name: str, mass_kg: float, x_m: float, **kw) -> MassItemInput:
    return MassItemInput.model_validate(
        {
            "name": name,
            "mass": {"value": mass_kg, "unit": "kg"},
            "position_x": {"value": x_m, "unit": "m"},
        }
        | kw
    )


class TestHandCalculatedReference:
    def test_total_and_cg(self):
        out = compute_mass_properties([_item("A", 10, 1.0), _item("B", 30, 3.0)])
        assert out.quantities["total_mass"].value == pytest.approx(40.0)
        assert out.quantities["cg_x"].value == pytest.approx(2.5)
        assert out.quantities["cg_y"].value == pytest.approx(0.0)

    def test_inertia_about_cg(self):
        out = compute_mass_properties([_item("A", 10, 1.0), _item("B", 30, 3.0)])
        assert out.quantities["inertia_yy"].value == pytest.approx(30.0)
        assert out.quantities["inertia_zz"].value == pytest.approx(30.0)
        assert out.quantities["inertia_xx"].value == pytest.approx(0.0, abs=1e-12)

    def test_gram_input_equivalent(self):
        base = compute_mass_properties([_item("A", 10, 1.0), _item("B", 30, 3.0)])
        alt = compute_mass_properties(
            [
                MassItemInput.model_validate(
                    {
                        "name": "A",
                        "mass": {"value": 10000, "unit": "g"},
                        "position_x": {"value": 100, "unit": "cm"},
                    }
                ),
                _item("B", 30, 3.0),
            ]
        )
        assert alt.quantities["cg_x"].value == pytest.approx(
            base.quantities["cg_x"].value, rel=1e-12
        )

    def test_breakdown_and_source_counts(self):
        out = compute_mass_properties(
            [
                _item("桁", 12, 1.0, category="wing_structure"),
                _item("リブ", 6, 1.1, category="wing_structure", source="measured"),
                _item("パイロット", 60, 0.8, category="pilot"),
            ]
        )
        wing = next(b for b in out.breakdown if b.category == "wing_structure")
        assert wing.mass.value == pytest.approx(18.0)
        assert wing.item_count == 2
        assert out.quantities["airframe_mass"].value == pytest.approx(18.0)  # パイロット除く
        assert out.estimated_item_count == 2 and out.measured_item_count == 1


class TestWarnings:
    def test_mass_over_target_violation(self):
        out = compute_mass_properties(
            [_item("機体", 45, 1.0, category="wing_structure")],
            airframe_mass_target=Quantity(value=40, unit="kg"),
        )
        codes = {w.code for w in out.warnings}
        assert "MASS_OVER_TARGET" in codes
        assert out.quantities["airframe_mass_delta"].value == pytest.approx(5.0)

    def test_all_estimated_and_missing_items_info(self):
        out = compute_mass_properties([_item("桁", 12, 1.0)])
        codes = {w.code for w in out.warnings}
        assert {"ALL_ESTIMATED", "NO_PILOT_ITEM", "NO_CONTEST_EQUIPMENT"} <= codes

    def test_no_over_target_when_under(self):
        out = compute_mass_properties(
            [_item("機体", 30, 1.0)],
            airframe_mass_target=Quantity(value=40, unit="kg"),
        )
        assert "MASS_OVER_TARGET" not in {w.code for w in out.warnings}


class TestValidation:
    def test_empty_items_rejected(self):
        with pytest.raises(CalculationError):
            compute_mass_properties([])

    def test_non_physical_mass_rejected(self):
        with pytest.raises(ValidationError):
            _item("bad", -5, 0.0)

    def test_wrong_dimension_rejected(self):
        with pytest.raises(ValidationError, match="次元が不正"):
            MassItemInput.model_validate(
                {"name": "bad", "mass": {"value": 1, "unit": "m"}}
            )
