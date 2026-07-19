"""設計スイープ・パレート抽出のテスト(T-401)。"""

import pytest
from pydantic import ValidationError

from pbm.calculation.design_sweep import compute_pareto_flags, run_design_sweep
from pbm.domain.optimization import DesignSweepRequest
from pbm.domain.requirements import RequirementSpecInput
from tests.conftest import RC1_JSON


def _request(**kw) -> DesignSweepRequest:
    return DesignSweepRequest.model_validate(kw)


class TestParetoLogic:
    def test_dominated_point_excluded(self):
        # (最小化, 最大化): A(300,30) B(310,35) C(320,25)
        # CはBに支配される(310≤320 かつ 35≥25)。AとBは互いに非支配
        flags = compute_pareto_flags([(300, 30), (310, 35), (320, 25)])
        assert flags == [True, True, False]

    def test_identical_points_both_pareto(self):
        flags = compute_pareto_flags([(300, 30), (300, 30)])
        assert flags == [True, True]

    def test_single_point(self):
        assert compute_pareto_flags([(1, 1)]) == [True]


class TestSweepPhysics:
    def test_power_decreases_with_wingspan(self, rc1_spec):
        """翼幅が大きいほど誘導抗力が減り必要出力が下がる(単調性)。"""
        req = _request(
            variables=[{"variable": "wingspan", "minimum": 25, "maximum": 35, "steps": 3}]
        )
        out = run_design_sweep(rc1_spec, req)
        assert out.evaluated == 3
        by_span = sorted(out.candidates, key=lambda c: c.values["wingspan"])
        powers = [c.required_pilot_power.value for c in by_span]
        assert powers[0] > powers[1] > powers[2]

    def test_base_spec_not_mutated(self, rc1_spec):
        req = _request(
            variables=[{"variable": "wingspan", "minimum": 25, "maximum": 35, "steps": 2}]
        )
        before = rc1_spec.model_dump()
        run_design_sweep(rc1_spec, req)
        assert rc1_spec.model_dump() == before

    def test_infeasible_marked_by_violation(self):
        """出力の小さいパイロットでは全案がPOWER_DEFICITで不可行になる。"""
        weak = RequirementSpecInput.model_validate(
            RC1_JSON | {"pilot_power_sustained": {"value": 120, "unit": "W"}}
        )
        req = _request(
            variables=[{"variable": "wingspan", "minimum": 25, "maximum": 30, "steps": 2}]
        )
        out = run_design_sweep(weak, req)
        assert out.feasible_count == 0
        assert all("POWER_DEFICIT" in c.violation_codes for c in out.candidates)
        assert any(w.code == "NO_FEASIBLE_CANDIDATE" for w in out.warnings)

    def test_two_variables_grid(self, rc1_spec):
        req = _request(
            variables=[
                {"variable": "wingspan", "minimum": 28, "maximum": 32, "steps": 2},
                {"variable": "cruise_speed", "minimum": 7, "maximum": 8, "steps": 3},
            ]
        )
        out = run_design_sweep(rc1_spec, req)
        assert out.evaluated == 6
        assert {tuple(sorted(c.values)) for c in out.candidates} == {
            ("cruise_speed", "wingspan")
        }

    def test_candidates_sorted_by_power(self, rc1_spec):
        req = _request(
            variables=[{"variable": "cruise_speed", "minimum": 6, "maximum": 9, "steps": 4}]
        )
        out = run_design_sweep(rc1_spec, req)
        powers = [c.required_pilot_power.value for c in out.candidates]
        assert powers == sorted(powers)


class TestRequestValidation:
    def test_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            _request(
                variables=[{"variable": "cruise_speed", "minimum": 1, "maximum": 25, "steps": 3}]
            )

    def test_duplicate_variable_rejected(self):
        with pytest.raises(ValidationError, match="複数指定"):
            _request(
                variables=[
                    {"variable": "wingspan", "minimum": 25, "maximum": 30, "steps": 2},
                    {"variable": "wingspan", "minimum": 30, "maximum": 35, "steps": 2},
                ]
            )

    def test_too_many_evaluations_rejected(self):
        with pytest.raises(ValidationError, match="上限"):
            _request(
                variables=[
                    {"variable": "wingspan", "minimum": 25, "maximum": 30, "steps": 15},
                    {"variable": "cruise_speed", "minimum": 6, "maximum": 9, "steps": 14},
                ]
            )  # 15×14=210 > 200

    def test_min_must_be_less_than_max(self):
        with pytest.raises(ValidationError):
            _request(
                variables=[{"variable": "wingspan", "minimum": 30, "maximum": 30, "steps": 2}]
            )
