"""主桁簡易梁解析の解析解リファレンステスト(T-301)。

RC-B1: 半翼幅s=15 m, n=1, m_total=100 kg → L_half = 100·9.80665/2 = 490.3325 N
円管: D=0.1 m, t=0.001 m → I = π(0.1⁴−0.098⁴)/64 = 3.81083e-7 m⁴

解析解:
- 楕円分布の翼根モーメント: M_root = 4·L_half·s/(3π) = 3121.55 N·m
- 一様分布の翼根モーメント: M_root = L_half·s/2 = 3677.49 N·m
- 翼根せん断: V_root = L_half = 490.3325 N(分布によらず)
- 楕円の翼根応力: σ = 3121.55·0.05/3.81083e-7 = 4.0956e8 Pa
- 一様分布の片持ち梁たわみ(等分布荷重の解析解): δ_tip = w·s⁴/(8EI)
  w = L_half/s = 32.6888 N/m, E=200 GPa → δ = 32.6888·50625/(8·200e9·3.81083e-7) = 2.7141 m
"""

import pytest
from pydantic import ValidationError

from pbm.calculation.spar_beam import run_spar_analysis
from pbm.domain.structure import SparAnalysisRequest

RC_B1 = {
    "half_span": {"value": 15, "unit": "m"},
    "load_factor": 1.0,
    "total_mass": {"value": 100, "unit": "kg"},
    "lift_distribution": "elliptic",
    "spar_outer_diameter": {"value": 0.1, "unit": "m"},
    "spar_wall_thickness": {"value": 1, "unit": "mm"},
    "elastic_modulus": {"value": 200, "unit": "GPa"},
    "allowable_stress": {"value": 800, "unit": "MPa"},
    "required_safety_factor": 1.5,
    "stations": 401,
}


def _run(**overrides):
    return run_spar_analysis(SparAnalysisRequest.model_validate(RC_B1 | overrides))


class TestAnalyticReference:
    def test_section_inertia(self):
        out = _run()
        assert out.quantities["section_moment_of_inertia"].value == pytest.approx(
            3.81083e-7, rel=1e-4
        )

    def test_root_shear_equals_half_lift(self):
        out = _run()
        assert out.quantities["lift_half_wing"].value == pytest.approx(490.3325, rel=1e-6)
        assert out.quantities["root_shear"].value == pytest.approx(490.3325, rel=1e-3)

    def test_elliptic_root_moment(self):
        out = _run()
        assert out.quantities["root_bending_moment"].value == pytest.approx(3121.55, rel=1e-3)

    def test_uniform_root_moment(self):
        out = _run(lift_distribution="uniform")
        assert out.quantities["root_bending_moment"].value == pytest.approx(3677.49, rel=1e-4)

    def test_elliptic_root_stress(self):
        out = _run()
        assert out.quantities["root_bending_stress"].value == pytest.approx(4.0956e8, rel=1e-3)

    def test_uniform_tip_deflection_vs_analytic(self):
        """等分布荷重の片持ち梁 δ=w·s⁴/(8EI) と数値2回積分が一致する。"""
        out = _run(lift_distribution="uniform")
        assert out.quantities["tip_deflection"].value == pytest.approx(2.7141, rel=1e-3)

    def test_safety_factor(self):
        out = _run()
        assert out.quantities["safety_factor"].value == pytest.approx(
            800e6 / 4.0956e8, rel=1e-3
        )

    def test_load_factor_scales_linearly(self):
        n1 = _run()
        n2 = _run(load_factor=2.0)
        assert n2.quantities["root_bending_moment"].value == pytest.approx(
            2 * n1.quantities["root_bending_moment"].value, rel=1e-9
        )


class TestWarnings:
    def test_safety_factor_deficit_violation(self):
        out = _run(required_safety_factor=3.0)  # SF≈1.95 < 3.0
        assert any(w.code == "SAFETY_FACTOR_DEFICIT" for w in out.warnings)

    def test_large_deflection_warning(self):
        out = _run(lift_distribution="uniform")  # たわみ比 2.71/15 = 0.18 > 0.1
        assert any(w.code == "DEFLECTION_LARGE" for w in out.warnings)

    def test_thin_wall_warning(self):
        out = _run(
            spar_outer_diameter={"value": 0.15, "unit": "m"},
            spar_wall_thickness={"value": 0.5, "unit": "mm"},  # t/D = 0.0033
        )
        assert any(w.code == "THIN_WALL_BUCKLING_RISK" for w in out.warnings)


class TestHumanConfirmedInputsRequired:
    """荷重倍数・許容応力・要求安全率は既定値なし(PROJECT_BRIEF §2, §10)。"""

    @pytest.mark.parametrize(
        "missing", ["load_factor", "allowable_stress", "required_safety_factor",
                     "elastic_modulus"]
    )
    def test_missing_human_input_rejected(self, missing):
        payload = {k: v for k, v in RC_B1.items() if k != missing}
        with pytest.raises(ValidationError):
            SparAnalysisRequest.model_validate(payload)


class TestValidation:
    def test_wall_thicker_than_radius_rejected(self):
        with pytest.raises(ValidationError, match="円管"):
            SparAnalysisRequest.model_validate(
                RC_B1 | {"spar_wall_thickness": {"value": 60, "unit": "mm"}}
            )

    def test_wrong_dimension_rejected(self):
        with pytest.raises(ValidationError, match="次元が不正"):
            SparAnalysisRequest.model_validate(
                RC_B1 | {"elastic_modulus": {"value": 200, "unit": "kg"}}
            )

    def test_formula_and_boundary_conditions_recorded(self):
        out = _run()
        assert any("境界条件" in f.expression for f in out.formulas)
        assert any(a.id == "A-142" for a in out.assumptions)  # 自重軽減無視(安全側)
        stations_y = [s.y.value for s in out.stations]
        assert stations_y[0] == 0.0 and stations_y[-1] == pytest.approx(15.0)
