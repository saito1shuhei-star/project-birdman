"""静安定余裕計算の手計算リファレンステスト(T-303)。

RC-S1: 翼 S=27 m², c̄=0.9 m, AR=33.3333, e=0.9 / 尾翼 S_t=2.5 m², l_t=4 m,
AR_t=8, e_t=0.9, η_t=0.9 / x_ac=0.9 m, x_cg=1.05 m

手計算:
a_w = 2π/(1+2π/(π·33.3333·0.9)) = 6.28319/1.066667 = 5.89049 /rad
a_t = 2π/(1+2π/(π·8·0.9)) = 6.28319/1.27778 = 4.91728 /rad
V_H = 2.5·4/(27·0.9) = 0.411523
dε/dα = 2·5.89049/(π·33.3333) = 0.112500
shift = 0.9·0.411523·(4.91728/5.89049)·(1−0.1125) = 0.274395
x_np = 0.9 + 0.9·0.274395 = 1.146955 m
SM = (1.146955 − 1.05)/0.9 = 0.107728
"""

import pytest
from pydantic import ValidationError

from pbm.calculation.static_stability import compute_static_stability
from pbm.domain.stability import StabilityRequest

RC_S1 = {
    "horizontal_tail_area": {"value": 2.5, "unit": "m^2"},
    "tail_arm": {"value": 4, "unit": "m"},
    "wing_ac_position": {"value": 0.9, "unit": "m"},
    "tail_aspect_ratio": 8.0,
    "tail_oswald_efficiency": 0.9,
    "tail_efficiency": 0.9,
}

WING = {
    "wing_area_si": 27.0,
    "wing_mean_chord_si": 0.9,
    "wing_aspect_ratio": 900.0 / 27.0,
    "wing_oswald_efficiency": 0.9,
}


def _run(cg_x: float = 1.05, **overrides):
    req = StabilityRequest.model_validate(RC_S1 | overrides)
    return compute_static_stability(req, cg_x_si=cg_x, **WING)


class TestHandCalculatedReference:
    def test_lift_slopes(self):
        out = _run()
        assert out.quantities["wing_lift_slope"].value == pytest.approx(5.89049, rel=1e-4)
        assert out.quantities["tail_lift_slope"].value == pytest.approx(4.91728, rel=1e-4)

    def test_tail_volume(self):
        out = _run()
        assert out.quantities["tail_volume_horizontal"].value == pytest.approx(
            0.411523, rel=1e-5
        )

    def test_downwash_derivative(self):
        out = _run()
        assert out.quantities["downwash_derivative"].value == pytest.approx(0.1125, rel=1e-4)

    def test_neutral_point_and_static_margin(self):
        out = _run()
        assert out.quantities["neutral_point_x"].value == pytest.approx(1.146955, rel=1e-4)
        assert out.quantities["static_margin"].value == pytest.approx(0.107728, rel=1e-3)

    def test_healthy_margin_no_warnings(self):
        out = _run()
        assert out.warnings == []

    def test_formulas_recorded(self):
        out = _run()
        assert [f.symbol for f in out.formulas] == ["V_H", "dε/dα", "x_np", "SM"]


class TestWarnings:
    def test_unstable_when_cg_aft_of_np(self):
        out = _run(cg_x=1.30)  # x_np=1.147より後方
        assert out.quantities["static_margin"].value < 0
        assert any(w.code == "STATICALLY_UNSTABLE" for w in out.warnings)

    def test_low_margin_warning(self):
        out = _run(cg_x=1.13)  # SM ≈ (1.147-1.13)/0.9 = 0.019
        assert any(w.code == "STATIC_MARGIN_LOW" for w in out.warnings)

    def test_high_margin_warning(self):
        out = _run(cg_x=0.90)  # SM ≈ 0.274
        assert any(w.code == "STATIC_MARGIN_HIGH" for w in out.warnings)

    def test_atypical_tail_volume_info(self):
        out = _run(horizontal_tail_area={"value": 0.5, "unit": "m^2"})  # V_H ≈ 0.082
        assert any(w.code == "TAIL_VOLUME_ATYPICAL" for w in out.warnings)


class TestValidation:
    def test_wrong_dimension_rejected(self):
        with pytest.raises(ValidationError, match="次元が不正"):
            StabilityRequest.model_validate(
                RC_S1 | {"horizontal_tail_area": {"value": 2.5, "unit": "m"}}
            )

    def test_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            StabilityRequest.model_validate(RC_S1 | {"tail_arm": {"value": 50, "unit": "m"}})

    def test_alternative_units_equivalent(self):
        base = _run()
        alt = _run(tail_arm={"value": 400, "unit": "cm"})
        assert alt.quantities["static_margin"].value == pytest.approx(
            base.quantities["static_margin"].value, rel=1e-9
        )
