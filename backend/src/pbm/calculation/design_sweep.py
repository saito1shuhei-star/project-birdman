"""設計変数のグリッドスイープと2目的パレート抽出(Step 11 / T-401)。純粋関数。

評価は初期サイジング(pbm.calculation.initial_sizing)をそのまま用いる:
同じ式・同じ検証・同じ警告(トレーサビリティの一貫性)。
目的: 必要パイロット出力の最小化 × 揚抗比の最大化。
制約: サイジングのviolation警告を持つ案は不可行(feasible=False)。

パレート判定(標準的な支配関係):
  案aが案bを支配 ⟺ power_a ≤ power_b かつ LD_a ≥ LD_b かつ少なくとも一方が厳密
"""

from __future__ import annotations

from itertools import product

from pbm.calculation.initial_sizing import run_initial_sizing
from pbm.domain.optimization import (
    DesignSweepOutput,
    DesignSweepRequest,
    SweepCandidate,
    SweepVariable,
)
from pbm.domain.quantities import Quantity
from pbm.domain.requirements import RequirementSpecInput
from pbm.domain.results import AssumptionRecord, CalcWarning, Severity


def _apply_variables(
    base: RequirementSpecInput, assignment: dict[str, float]
) -> RequirementSpecInput:
    """基準要求仕様に変数値(SI)を適用した新しい仕様を作る(基準は変更しない)。"""
    updates: dict = {}
    if SweepVariable.wingspan.value in assignment:
        updates["wingspan_limit"] = Quantity(
            value=assignment[SweepVariable.wingspan.value], unit="m"
        )
    if SweepVariable.cruise_speed.value in assignment:
        updates["target_cruise_speed"] = Quantity(
            value=assignment[SweepVariable.cruise_speed.value], unit="m/s"
        )
    if SweepVariable.cl_cruise.value in assignment:
        updates["cl_cruise"] = assignment[SweepVariable.cl_cruise.value]
    return base.model_copy(update=updates)


def compute_pareto_flags(points: list[tuple[float, float]]) -> list[bool]:
    """(最小化目的, 最大化目的) の点列に対しパレートフロントか否かを返す。"""
    flags: list[bool] = []
    for i, (min_i, max_i) in enumerate(points):
        dominated = False
        for j, (min_j, max_j) in enumerate(points):
            if i == j:
                continue
            if (
                min_j <= min_i
                and max_j >= max_i
                and (min_j < min_i or max_j > max_i)
            ):
                dominated = True
                break
        flags.append(not dominated)
    return flags


def run_design_sweep(
    base: RequirementSpecInput, request: DesignSweepRequest
) -> DesignSweepOutput:
    """グリッドスイープを実行し、候補一覧(可行性・パレートフラグ付き)を返す。"""
    axes = [(v.variable.value, v.values()) for v in request.variables]
    names = [name for name, _ in axes]

    candidates: list[SweepCandidate] = []
    for combo in product(*(vals for _, vals in axes)):
        assignment = dict(zip(names, combo, strict=True))
        spec = _apply_variables(base, assignment)
        out = run_initial_sizing(spec)
        violations = [w.code for w in out.warnings if w.severity is Severity.violation]
        candidates.append(
            SweepCandidate(
                values=assignment,
                feasible=not violations,
                violation_codes=violations,
                required_pilot_power=out.quantities["required_pilot_power"],
                lift_to_drag=out.quantities["lift_to_drag"],
                wing_area=out.quantities["wing_area"],
                stall_speed=out.quantities["stall_speed"],
                power_margin=out.quantities["power_margin"],
            )
        )

    feasible = [c for c in candidates if c.feasible]
    if feasible:
        flags = compute_pareto_flags(
            [(c.required_pilot_power.value, c.lift_to_drag.value) for c in feasible]
        )
        for c, flag in zip(feasible, flags, strict=True):
            c.pareto = flag

    warnings: list[CalcWarning] = []
    if not feasible:
        warnings.append(CalcWarning(
            code="NO_FEASIBLE_CANDIDATE", severity=Severity.warning,
            message="可行な設計案がありません。変数範囲または要求仕様を見直してください",
        ))

    assumptions = [
        AssumptionRecord(
            id="A-150", name="スイープ評価モデル",
            value="初期サイジング(定常水平飛行・A-101〜A-108の仮定)と同一",
            rationale=(
                "掃引しない入力は基準要求仕様の値を使用。評価は解析的推定であり、"
                "採用判断は人間が行うこと(PROJECT_BRIEF §2)"
            ),
        ),
    ]

    # 必要出力の小さい順に提示(採用判断は人間)
    candidates.sort(key=lambda c: c.required_pilot_power.value)
    return DesignSweepOutput(
        candidates=candidates,
        evaluated=len(candidates),
        feasible_count=len(feasible),
        pareto_count=sum(1 for c in candidates if c.pareto),
        assumptions=assumptions,
        warnings=warnings,
    )
