"""初期サイジングの数値回帰テスト(VALIDATION_PLAN.md §2 RC-1)と入力検証テスト。

期待値はCALCULATION_SPEC.md §1の式による手計算値。期待値の変更は
CALCULATION_SPEC / ASSUMPTIONS の改訂とセットでのみ行うこと(VALIDATION_PLAN §5)。
"""

import pytest
from pydantic import ValidationError

from pbm.calculation.initial_sizing import run_initial_sizing
from pbm.domain.requirements import RequirementSpecInput
from pbm.workflow.sizing_service import compute_input_hash, execute_sizing
from tests.conftest import RC1_JSON

# (キー, 期待値, 相対許容差)
RC1_EXPECTED = [
    ("total_mass", 100.0, 1e-12),
    ("required_lift", 980.665, 1e-9),
    ("dynamic_pressure", 34.453125, 1e-9),
    ("wing_area", 28.4638, 1e-3),
    ("wing_loading", 34.4531, 1e-3),
    ("aspect_ratio", 31.619, 1e-3),
    ("mean_chord", 0.94879, 1e-3),
    ("stall_speed", 6.3386, 1e-3),
    ("induced_drag_coefficient", 0.011186, 1e-3),
    ("drag_coefficient_total", 0.031186, 1e-3),
    ("required_thrust", 30.583, 1e-3),
    ("lift_to_drag", 32.066, 1e-3),
    ("aero_power", 229.37, 1e-3),
    ("required_pilot_power", 301.81, 1e-3),
    ("power_margin", -51.81, 1e-2),
    ("reynolds_number", 4.873e5, 1e-3),
]


class TestRC1Regression:
    @pytest.mark.parametrize(("key", "expected", "rel"), RC1_EXPECTED)
    def test_values_match_hand_calculation(self, rc1_spec, key, expected, rel):
        out = run_initial_sizing(rc1_spec)
        assert out.quantities[key].value == pytest.approx(expected, rel=rel)

    def test_expected_warnings(self, rc1_spec):
        out = run_initial_sizing(rc1_spec)
        codes = {w.code for w in out.warnings}
        assert "POWER_DEFICIT" in codes           # ΔP < 0
        assert "STALL_MARGIN_LOW" not in codes    # V/V_stall = 1.183 ≥ 1.15
        assert "ASPECT_RATIO_HIGH" not in codes   # AR = 31.6 ≤ 40
        deficit = next(w for w in out.warnings if w.code == "POWER_DEFICIT")
        assert deficit.severity == "violation"

    def test_every_result_has_formula_records(self, rc1_spec):
        out = run_initial_sizing(rc1_spec)
        assert len(out.formulas) == 16            # CALCULATION_SPEC §1 の式1〜16
        for f in out.formulas:
            assert f.expression and f.source and f.substitutions

    def test_assumptions_recorded_with_ids(self, rc1_spec):
        out = run_initial_sizing(rc1_spec)
        ids = {a.id for a in out.assumptions}
        assert {"A-001", "A-002", "A-101", "A-104", "A-106"} <= ids


class TestReproducibility:
    """FR-022: 同一入力 ⇒ 同一ハッシュ・同一出力。"""

    def test_same_input_same_hash_and_output(self, rc1_spec):
        spec2 = RequirementSpecInput.model_validate(RC1_JSON)
        assert compute_input_hash(rc1_spec) == compute_input_hash(spec2)
        out1, _ = execute_sizing(rc1_spec)
        out2, _ = execute_sizing(spec2)
        assert out1.model_dump() == out2.model_dump()

    def test_different_input_different_hash(self, rc1_spec):
        changed = RC1_JSON | {"pilot_mass": {"value": 61, "unit": "kg"}}
        spec2 = RequirementSpecInput.model_validate(changed)
        assert compute_input_hash(rc1_spec) != compute_input_hash(spec2)


class TestUnitEquivalence:
    """単位を変えても物理的に同じ入力なら同じ結果になる(NFR-001)。"""

    def test_imperial_and_kmh_input(self, rc1_spec):
        alt = RequirementSpecInput.model_validate(
            RC1_JSON
            | {
                "pilot_mass": {"value": 60000, "unit": "g"},
                "target_cruise_speed": {"value": 27, "unit": "km/h"},   # = 7.5 m/s
                "wingspan_limit": {"value": 30000, "unit": "mm"},
            }
        )
        base = run_initial_sizing(rc1_spec)
        out = run_initial_sizing(alt)
        for key in ("wing_area", "required_pilot_power", "reynolds_number"):
            assert out.quantities[key].value == pytest.approx(
                base.quantities[key].value, rel=1e-9
            )


class TestInputValidation:
    """FR-011, FR-012: 次元・範囲・単位なしの拒否。"""

    def test_wrong_dimension_rejected(self):
        with pytest.raises(ValidationError, match="次元が不正"):
            RequirementSpecInput.model_validate(
                RC1_JSON | {"pilot_mass": {"value": 60, "unit": "m"}}
            )

    def test_unitless_physical_quantity_rejected(self):
        with pytest.raises(ValidationError):
            RequirementSpecInput.model_validate(RC1_JSON | {"pilot_mass": 60})

    @pytest.mark.parametrize(
        "override",
        [
            {"pilot_mass": {"value": -60, "unit": "kg"}},
            {"pilot_mass": {"value": 10, "unit": "kg"}},                  # < 30 kg
            {"target_cruise_speed": {"value": 50, "unit": "m/s"}},        # > 20 m/s
            {"wingspan_limit": {"value": 100, "unit": "m"}},              # > 45 m
            {"air_density": {"value": 0.1, "unit": "kg/m^3"}},            # < 0.9
            {"cl_cruise": 5.0},                                            # > 2.5
            {"propeller_efficiency": 1.5},                                 # > 1.0
        ],
    )
    def test_out_of_range_rejected(self, override):
        with pytest.raises(ValidationError):
            RequirementSpecInput.model_validate(RC1_JSON | override)

    def test_cl_max_must_exceed_cl_cruise(self):
        with pytest.raises(ValidationError, match="cl_max"):
            RequirementSpecInput.model_validate(RC1_JSON | {"cl_max": 0.9, "cl_cruise": 1.0})

    def test_nan_rejected(self):
        with pytest.raises(ValidationError):
            RequirementSpecInput.model_validate(
                RC1_JSON | {"pilot_mass": {"value": float("nan"), "unit": "kg"}}
            )


class TestDefaults:
    """係数省略時はASSUMPTIONSの既定値が適用され、既定値使用が記録される。"""

    def test_defaults_applied_and_marked(self):
        minimal = {
            k: RC1_JSON[k]
            for k in (
                "pilot_mass",
                "airframe_mass_target",
                "pilot_power_sustained",
                "target_cruise_speed",
                "wingspan_limit",
            )
        }
        spec = RequirementSpecInput.model_validate(minimal)
        assert spec.cl_cruise == 1.0 and spec.cd0 == 0.020
        assert not spec.user_specified("cl_cruise")
        out = run_initial_sizing(spec)
        cd0_assumption = next(a for a in out.assumptions if a.id == "A-104")
        assert "既定値" in cd0_assumption.rationale
        # 既定値はRC-1の明示値と同一なので結果も一致する
        base = run_initial_sizing(RequirementSpecInput.model_validate(RC1_JSON))
        assert out.quantities["wing_area"].value == pytest.approx(
            base.quantities["wing_area"].value, rel=1e-12
        )
