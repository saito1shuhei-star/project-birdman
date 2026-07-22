"""XROTOR構造化入力(スクリプト生成・サマリ取込)のテスト。

Codex版PBM(commit 6a9e400)のtest_xrotor_input.pyから移植・適応。
"""

import pytest
from pydantic import ValidationError

from pbm.adapters.xrotor import parse_xrotor_summary
from pbm.domain.xrotor_case import XrotorCase


def _q(value: float, unit: str) -> dict:
    return {"value": value, "unit": unit}


def _airfoil() -> dict:
    return {
        "zero_lift_angle": _q(0, "deg"),
        "lift_curve_slope": _q(6.28, "1/rad"),
        "stall_lift_curve_slope": _q(0.1, "1/rad"),
        "maximum_lift_coefficient": 1.5,
        "minimum_lift_coefficient": -0.5,
        "stall_transition_width": 0.1,
        "moment_coefficient": -0.1,
        "minimum_drag_coefficient": 0.013,
        "lift_coefficient_at_minimum_drag": 0.5,
        "quadratic_drag_coefficient": 0.004,
        "reference_reynolds_number": 200_000,
        "reynolds_exponent": -0.4,
        "critical_mach_number": 0.8,
        "source": "XROTOR 7.55 distribution defaults; not aircraft evidence",
    }


def _case(**overrides) -> dict:
    base = {
        "case_name": "BirdMan example",
        "blade_count": 2,
        "flight_speed": _q(36, "km/h"),
        "tip_radius": _q(160, "cm"),
        "hub_radius": _q(15, "cm"),
        "rotational_speed": _q(120, "rpm"),
        "altitude": _q(0, "m"),
        "air_density": _q(1.225, "kg/m^3"),
        "dynamic_viscosity": _q(0.01789, "mPa*s"),
        "speed_of_sound": _q(340, "m/s"),
        "stations": [
            {"radius": _q(15, "cm"), "chord": _q(20, "cm"), "blade_angle": _q(35, "deg")},
            {"radius": _q(80, "cm"), "chord": _q(15, "cm"), "blade_angle": _q(20, "deg")},
            {"radius": _q(160, "cm"), "chord": _q(8, "cm"), "blade_angle": _q(10, "deg")},
        ],
        "airfoil": _airfoil(),
        "apply_prandtl_corrections": False,
    }
    return base | overrides


class TestScriptGeneration:
    def test_generates_official_arbi_flow_with_si_conversions(self):
        case = XrotorCase.model_validate(_case())
        payload = case.normalized_payload()
        script = case.generate_script()

        assert payload["flight_speed_mps"] == pytest.approx(10.0, abs=1e-12)
        assert payload["dynamic_viscosity_pa_s"] == pytest.approx(1.789e-5, abs=1e-12)
        assert "ARBI\n2\n10\n1.6\n0.15\n3\n" in script
        assert "0.09375 0.125 35" in script  # r/R=15/160, c/R=20/160, 35deg
        assert "DENS 1.225" in script
        assert "VISC 1.789e-05" in script
        assert ".AERO\nEDIT\n1\n0\n2\n6.28" in script
        assert ".OPER\nRPM 120\n\nQUIT\n" in script
        assert "/" not in script  # パス区切りが混入しない(実行時検証と整合)

    def test_prandtl_flag(self):
        script = XrotorCase.model_validate(
            _case(apply_prandtl_corrections=True)
        ).generate_script()
        assert "\nY\n" in script


class TestCaseValidation:
    def test_rejects_station_not_reaching_tip(self):
        stations = _case()["stations"]
        stations[-1]["radius"] = _q(150, "cm")
        with pytest.raises(ValidationError, match="最後のステーション"):
            XrotorCase.model_validate(_case(stations=stations))

    def test_rejects_hub_mismatch(self):
        stations = _case()["stations"]
        stations[0]["radius"] = _q(20, "cm")
        with pytest.raises(ValidationError, match="最初のステーション"):
            XrotorCase.model_validate(_case(stations=stations))

    def test_rejects_non_ascii_case_name(self):
        with pytest.raises(ValidationError, match="case_name"):
            XrotorCase.model_validate(_case(case_name="機体1号"))

    def test_rejects_plain_dimensionless_angle(self):
        stations = _case()["stations"]
        stations[0]["blade_angle"] = _q(35, "1")  # 角度単位でない
        with pytest.raises(ValidationError, match="角度単位"):
            XrotorCase.model_validate(_case(stations=stations))

    def test_rejects_wrong_rpm_dimension(self):
        with pytest.raises(ValidationError, match="rotational_speed"):
            XrotorCase.model_validate(_case(rotational_speed=_q(120, "m/s")))

    def test_requires_airfoil_source(self):
        airfoil = _airfoil() | {"source": "   "}
        with pytest.raises(ValidationError):
            XrotorCase.model_validate(_case(airfoil=airfoil))


class TestSummaryParser:
    def test_parses_only_complete_summary(self):
        stdout = """
        thrust(N) = 123.4
        power(W) = 250.0
        torque(N-m) = 19.9
        Efficiency = 0.82
        speed(m/s) = 10
        rpm = 120
        """
        assert parse_xrotor_summary(stdout) == {
            "thrust_n": 123.4,
            "power_w": 250.0,
            "torque_nm": 19.9,
            "efficiency": 0.82,
            "flight_speed_mps": 10.0,
            "rotational_speed_rpm": 120.0,
        }

    def test_incomplete_summary_returns_none(self):
        assert parse_xrotor_summary("thrust(N) = 123.4") is None
        assert parse_xrotor_summary("") is None
