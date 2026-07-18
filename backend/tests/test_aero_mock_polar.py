"""モック空力ポーラ生成の数値回帰テスト(T-202)。

手計算リファレンス: AR=10, e=1.0(理想), CD0=0.02, alpha=0/4degの2点。
a = a0/(1+a0/(π·AR·e)) = 2π/(1+2π/(π·10·1)) = 2π/1.2 = 5.235987756 /rad
alpha=4deg → alpha_rad=π/45=0.06981317008
cl = a·alpha_rad = 5.235987756 × 0.06981317008 ≈ 0.3655409
cd = CD0 + cl²/(π·AR·e) = 0.02 + 0.3655409²/(π·10) ≈ 0.02 + 0.0042532 ≈ 0.0242532
L/D = cl/cd ≈ 15.0719
"""

import pytest

from pbm.calculation.aero_mock_polar import generate_mock_polar
from pbm.domain.aero_analysis import AeroAnalysisRequest


def _request(**overrides) -> AeroAnalysisRequest:
    base = dict(
        aspect_ratio=10.0,
        oswald_efficiency=1.0,
        parasite_drag_coefficient=0.02,
        cl_max=2.0,
        alpha_min_deg=0.0,
        alpha_max_deg=4.0,
        alpha_step_deg=4.0,
    )
    base.update(overrides)
    return AeroAnalysisRequest.model_validate(base)


class TestHandCalculatedReference:
    def test_alpha_zero_point(self):
        out = generate_mock_polar(_request())
        p0 = out.polar[0]
        assert p0.alpha_deg == pytest.approx(0.0)
        assert p0.cl == pytest.approx(0.0, abs=1e-12)
        assert p0.cd == pytest.approx(0.02, rel=1e-9)
        assert p0.cm == pytest.approx(0.0)
        assert p0.stalled is False

    def test_alpha_four_deg_point(self):
        out = generate_mock_polar(_request())
        p1 = out.polar[-1]
        assert p1.alpha_deg == pytest.approx(4.0)
        assert p1.cl == pytest.approx(0.3655409, rel=1e-4)
        assert p1.cd == pytest.approx(0.0242532, rel=1e-3)
        assert p1.stalled is False

    def test_max_lift_to_drag(self):
        out = generate_mock_polar(_request())
        assert out.max_lift_to_drag == pytest.approx(15.0719, rel=2e-3)
        assert out.cl_at_max_lift_to_drag == pytest.approx(0.3655409, rel=1e-4)

    def test_formulas_and_assumptions_recorded(self):
        out = generate_mock_polar(_request())
        assert out.formulas and out.formulas[0].symbol == "a"
        ids = {a.id for a in out.assumptions}
        assert {"A-102", "A-104"} <= ids


class TestStallClipping:
    def test_cl_clipped_at_cl_max_and_warning_emitted(self):
        # cl_max=0.3 < 未失速時の4degのCL(≈0.3655) → クリップされる
        req = _request(cl_max=0.3)
        out = generate_mock_polar(req)
        stalled_point = out.polar[-1]
        assert stalled_point.stalled is True
        assert stalled_point.cl == pytest.approx(0.3, rel=1e-9)
        assert any(w.code == "MOCK_POLAR_STALL_CLIPPED" for w in out.warnings)

    def test_negative_alpha_clipped_symmetrically(self):
        req = _request(alpha_min_deg=-4.0, alpha_max_deg=0.0, alpha_step_deg=4.0, cl_max=0.3)
        out = generate_mock_polar(req)
        p0 = out.polar[0]
        assert p0.alpha_deg == pytest.approx(-4.0)
        assert p0.stalled is True
        assert p0.cl == pytest.approx(-0.3, rel=1e-9)


class TestGeneralBehavior:
    def test_drag_increases_with_lift_magnitude(self):
        req = _request(alpha_min_deg=0.0, alpha_max_deg=4.0, alpha_step_deg=2.0)
        out = generate_mock_polar(req)
        cds = [p.cd for p in out.polar]
        assert cds == sorted(cds)  # alpha増加(=|CL|増加)に伴いCDも単調増加

    def test_higher_aspect_ratio_gives_higher_lift_to_drag(self):
        low_ar = generate_mock_polar(_request(aspect_ratio=6.0))
        high_ar = generate_mock_polar(_request(aspect_ratio=20.0))
        assert high_ar.max_lift_to_drag > low_ar.max_lift_to_drag
