"""モックプロペラ解析(運動量理論)の数値回帰テスト(T-203)。

手計算リファレンス RC-P1: ρ=1.225 kg/m³, V=7.5 m/s, D=3 m, P=250 W。
A = π·3²/4 = 7.068583 m²
2ρA = 17.31803
w³ − 7.5·w² = 250/17.31803 = 14.43581 → w ≈ 7.7409 m/s(Newton法で検算済み)
v_i ≈ 0.2409 m/s
T = 2ρA·w·v_i ≈ 17.31803 × 7.7409 × 0.24091 ≈ 32.30 N
η_ideal = T·V/P ≈ 32.30×7.5/250 ≈ 0.9689 = V/(V+v_i) = 7.5/7.7409(Froude効率の恒等式)
"""

import pytest
from pydantic import ValidationError

from pbm.calculation.prop_mock_momentum import run_mock_momentum_analysis
from pbm.domain.prop_analysis import PropAnalysisRequest

RC_P1 = {
    "flight_speed": {"value": 7.5, "unit": "m/s"},
    "input_power": {"value": 250, "unit": "W"},
    "diameter": {"value": 3, "unit": "m"},
    "air_density": {"value": 1.225, "unit": "kg/m^3"},
}


def _request(**overrides) -> PropAnalysisRequest:
    return PropAnalysisRequest.model_validate(RC_P1 | overrides)


class TestHandCalculatedReference:
    def test_disk_area(self):
        out = run_mock_momentum_analysis(_request())
        assert out.quantities["disk_area"].value == pytest.approx(7.068583, rel=1e-6)

    def test_slipstream_and_induced_velocity(self):
        out = run_mock_momentum_analysis(_request())
        assert out.quantities["slipstream_velocity"].value == pytest.approx(7.7409, rel=1e-3)
        assert out.quantities["induced_velocity"].value == pytest.approx(0.2409, rel=2e-3)

    def test_thrust(self):
        out = run_mock_momentum_analysis(_request())
        assert out.quantities["thrust_ideal"].value == pytest.approx(32.30, rel=1e-3)

    def test_ideal_efficiency_and_froude_identity(self):
        out = run_mock_momentum_analysis(_request())
        eta = out.quantities["ideal_efficiency"].value
        assert eta == pytest.approx(0.9689, rel=1e-3)
        # Froude効率の恒等式 η = V / (V + v_i)
        v = 7.5
        vi = out.quantities["induced_velocity"].value
        assert eta == pytest.approx(v / (v + vi), rel=1e-9)

    def test_power_balance_consistency(self):
        """T·(V+v_i) = P(運動量理論のエネルギー収支)が成り立つ。"""
        out = run_mock_momentum_analysis(_request())
        thrust = out.quantities["thrust_ideal"].value
        w = out.quantities["slipstream_velocity"].value
        assert thrust * w == pytest.approx(250.0, rel=1e-9)

    def test_formulas_and_warnings(self):
        out = run_mock_momentum_analysis(_request())
        symbols = [f.symbol for f in out.formulas]
        assert symbols == ["A", "w", "T", "η_ideal"]
        codes = {w.code for w in out.warnings}
        assert "MOCK_IDEAL_EFFICIENCY" in codes  # 理論上限であることを常に警告
        assert any(a.id == "A-120" for a in out.assumptions)


class TestPhysicalTrends:
    def test_larger_diameter_gives_higher_efficiency(self):
        """大直径ほど誘導速度が下がり理想効率が上がる(HPA大直径プロペラの根拠)。"""
        small = run_mock_momentum_analysis(_request(diameter={"value": 1.5, "unit": "m"}))
        large = run_mock_momentum_analysis(_request(diameter={"value": 4.0, "unit": "m"}))
        assert (
            large.quantities["ideal_efficiency"].value
            > small.quantities["ideal_efficiency"].value
        )

    def test_more_power_gives_more_thrust_less_efficiency(self):
        low = run_mock_momentum_analysis(_request(input_power={"value": 200, "unit": "W"}))
        high = run_mock_momentum_analysis(_request(input_power={"value": 400, "unit": "W"}))
        assert high.quantities["thrust_ideal"].value > low.quantities["thrust_ideal"].value
        assert (
            high.quantities["ideal_efficiency"].value
            < low.quantities["ideal_efficiency"].value
        )

    def test_geometry_unused_warning_when_hub_specified(self):
        out = run_mock_momentum_analysis(
            _request(hub_diameter={"value": 0.1, "unit": "m"}, blade_count=3)
        )
        assert any(w.code == "MOCK_GEOMETRY_UNUSED" for w in out.warnings)


class TestValidation:
    def test_wrong_dimension_rejected(self):
        with pytest.raises(ValidationError, match="次元が不正"):
            _request(diameter={"value": 3, "unit": "kg"})

    def test_unitless_rejected(self):
        with pytest.raises(ValidationError):
            PropAnalysisRequest.model_validate(RC_P1 | {"input_power": 250})

    @pytest.mark.parametrize(
        "override",
        [
            {"flight_speed": {"value": 50, "unit": "m/s"}},   # > 20
            {"diameter": {"value": 10, "unit": "m"}},          # > 6
            {"input_power": {"value": 10, "unit": "W"}},       # < 50
            {"air_density": {"value": 0.1, "unit": "kg/m^3"}},
        ],
    )
    def test_out_of_range_rejected(self, override):
        with pytest.raises(ValidationError):
            _request(**override)

    def test_hub_must_be_smaller_than_diameter(self):
        with pytest.raises(ValidationError, match="hub_diameter"):
            _request(hub_diameter={"value": 3.5, "unit": "m"})

    def test_alternative_units_equivalent(self):
        base = run_mock_momentum_analysis(_request())
        alt = run_mock_momentum_analysis(
            _request(
                flight_speed={"value": 27, "unit": "km/h"},
                diameter={"value": 3000, "unit": "mm"},
            )
        )
        assert alt.quantities["thrust_ideal"].value == pytest.approx(
            base.quantities["thrust_ideal"].value, rel=1e-9
        )
