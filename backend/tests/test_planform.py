"""WingPlanformの幾何計算・検証テスト(T-204)。

手計算リファレンス:
- 矩形翼: 翼弦1.0m一定、半翼幅15m → S = 2×15×1.0 = 30 m², b = 30 m, AR = 30, λ = 1.0
- テーパー翼: 翼根1.2m→翼端0.6m(線形、半翼幅15m)
  → S = 2 × 15×(1.2+0.6)/2 = 27 m², AR = 900/27 = 33.333, λ = 0.5, c̄ = 27/30 = 0.9 m
- 3セクション(0m:1.2m→10m:1.0m→15m:0.5m)
  → 半翼面積 = 10×(1.2+1.0)/2 + 5×(1.0+0.5)/2 = 11.0 + 3.75 = 14.75 → S = 29.5 m²
"""

import pytest
from pydantic import ValidationError

from pbm.domain.planform import WingPlanformInput


def _section(y_m: float, chord_m: float, **kw) -> dict:
    return {
        "spanwise_position": {"value": y_m, "unit": "m"},
        "chord": {"value": chord_m, "unit": "m"},
    } | kw


class TestGeometryHandCalc:
    def test_rectangular_wing(self):
        p = WingPlanformInput.model_validate(
            {"sections": [_section(0, 1.0), _section(15, 1.0)]}
        )
        assert p.span_si == pytest.approx(30.0)
        assert p.area_si == pytest.approx(30.0)
        assert p.aspect_ratio == pytest.approx(30.0)
        assert p.taper_ratio == pytest.approx(1.0)
        assert p.mean_chord_si == pytest.approx(1.0)

    def test_tapered_wing(self):
        p = WingPlanformInput.model_validate(
            {"sections": [_section(0, 1.2), _section(15, 0.6)]}
        )
        assert p.area_si == pytest.approx(27.0)
        assert p.aspect_ratio == pytest.approx(900.0 / 27.0, rel=1e-9)
        assert p.taper_ratio == pytest.approx(0.5)
        assert p.mean_chord_si == pytest.approx(0.9)

    def test_three_section_wing(self):
        p = WingPlanformInput.model_validate(
            {"sections": [_section(0, 1.2), _section(10, 1.0), _section(15, 0.5)]}
        )
        assert p.area_si == pytest.approx(29.5)

    def test_millimeter_input_equivalent(self):
        base = WingPlanformInput.model_validate(
            {"sections": [_section(0, 1.0), _section(15, 1.0)]}
        )
        alt = WingPlanformInput.model_validate(
            {
                "sections": [
                    {
                        "spanwise_position": {"value": 0, "unit": "mm"},
                        "chord": {"value": 1000, "unit": "mm"},
                    },
                    {
                        "spanwise_position": {"value": 15000, "unit": "mm"},
                        "chord": {"value": 1000, "unit": "mm"},
                    },
                ]
            }
        )
        assert alt.area_si == pytest.approx(base.area_si, rel=1e-12)

    def test_derived_quantities_have_units(self):
        p = WingPlanformInput.model_validate(
            {"sections": [_section(0, 1.0), _section(15, 1.0)]}
        )
        derived = p.derived_quantities()
        assert derived["area"].unit == "m^2"
        assert derived["span"].value == pytest.approx(30.0)


class TestValidation:
    def test_first_section_must_be_root(self):
        with pytest.raises(ValidationError, match="翼根"):
            WingPlanformInput.model_validate(
                {"sections": [_section(1.0, 1.0), _section(15, 1.0)]}
            )

    def test_sections_must_be_ascending(self):
        with pytest.raises(ValidationError, match="昇順"):
            WingPlanformInput.model_validate(
                {"sections": [_section(0, 1.0), _section(10, 1.0), _section(5, 0.8)]}
            )

    def test_minimum_two_sections(self):
        with pytest.raises(ValidationError):
            WingPlanformInput.model_validate({"sections": [_section(0, 1.0)]})

    def test_span_range(self):
        with pytest.raises(ValidationError, match="半翼幅"):
            WingPlanformInput.model_validate(
                {"sections": [_section(0, 1.0), _section(30, 1.0)]}  # 全翼幅60m > 45m
            )

    def test_chord_range(self):
        with pytest.raises(ValidationError, match="chord"):
            WingPlanformInput.model_validate(
                {"sections": [_section(0, 5.0), _section(15, 5.0)]}  # 翼弦5m > 3m
            )

    def test_wrong_dimension_rejected(self):
        with pytest.raises(ValidationError, match="次元が不正"):
            WingPlanformInput.model_validate(
                {
                    "sections": [
                        {
                            "spanwise_position": {"value": 0, "unit": "kg"},
                            "chord": {"value": 1, "unit": "m"},
                        },
                        _section(15, 1.0),
                    ]
                }
            )
