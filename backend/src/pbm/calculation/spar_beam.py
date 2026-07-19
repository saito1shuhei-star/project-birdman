"""主桁の簡易梁解析(Step 8 / T-301)。純粋関数。

モデル(境界条件・荷重条件を明示: PROJECT_BRIEF Step 8):
- 半翼を翼根完全固定の片持ち梁とする(境界条件: y=0 でたわみ0・たわみ角0)
- 荷重: 揚力分布 w(y)(上向き)。半翼合計揚力 L_half = n·m_total·g / 2
  - elliptic: w(y) = w0·√(1−(y/s)²), w0 = 4·L_half/(π·s)
  - uniform : w(y) = L_half/s
- 翼(桁・構造)自重による荷重軽減は含まない(A-142。安全側の近似)
- 断面: 円管(外径D、肉厚t、一定)。I = π(D⁴−d⁴)/64, d = D−2t
- 応力: σ(y) = M(y)·(D/2) / I(線形弾性梁理論 A-143)
- たわみ: 曲率 M/(EI) を2回数値積分(台形則)
- 安全率: SF = σ_allow / σ_max(σ_allow・要求SFは人間入力。PROJECT_BRIEF §2)

出典: 材料力学の標準梁理論(Gere & Timoshenko, Mechanics of Materials)。
楕円分布の翼根モーメント解析解: M_root = 4·L_half·s/(3π)(∫y·w dy の閉形式)。
座屈・ねじり・接合部・疲労は本MVPの対象外(Phase 3後半で拡張)。
"""

from __future__ import annotations

import math

from pbm.calculation.initial_sizing import STANDARD_GRAVITY_M_S2
from pbm.domain.errors import CalculationError
from pbm.domain.quantities import Quantity
from pbm.domain.results import AssumptionRecord, CalcWarning, FormulaRecord, Severity
from pbm.domain.structure import (
    LiftDistribution,
    SparAnalysisOutput,
    SparAnalysisRequest,
    SparStation,
)

_SOURCE = "片持ち梁の標準理論(Gere & Timoshenko, Mechanics of Materials)"


def _lift_intensity(distribution: LiftDistribution, lift_half: float, s: float, y: float) -> float:
    """位置yの単位長さあたり揚力 w(y) [N/m]。"""
    if distribution is LiftDistribution.elliptic:
        ratio = min(1.0, y / s)
        return (4.0 * lift_half / (math.pi * s)) * math.sqrt(max(0.0, 1.0 - ratio**2))
    return lift_half / s


def run_spar_analysis(request: SparAnalysisRequest) -> SparAnalysisOutput:
    """片持ち梁モデルで主桁のせん断・曲げ・応力・たわみ・安全率を計算する。"""
    s = request.half_span.magnitude_si
    n = request.load_factor
    total_mass = request.total_mass.magnitude_si
    d_root = request.spar_outer_diameter.magnitude_si
    t_root = request.spar_wall_thickness.magnitude_si
    # テーパー桁: 翼端断面(省略時=翼根と同一)。翼根⇔翼端を線形補間
    d_tip = (
        request.spar_tip_outer_diameter.magnitude_si
        if request.spar_tip_outer_diameter is not None
        else d_root
    )
    t_tip = (
        request.spar_tip_wall_thickness.magnitude_si
        if request.spar_tip_wall_thickness is not None
        else t_root
    )
    is_tapered = (d_tip != d_root) or (t_tip != t_root)
    e_mod = request.elastic_modulus.magnitude_si
    sigma_allow = request.allowable_stress.magnitude_si
    nu = request.poisson_ratio

    lift_half = n * total_mass * STANDARD_GRAVITY_M_S2 / 2.0

    n_pts = request.stations
    dy = s / (n_pts - 1)
    ys = [i * dy for i in range(n_pts)]
    w = [_lift_intensity(request.lift_distribution, lift_half, s, y) for y in ys]

    def _section(y: float) -> tuple[float, float, float]:
        """位置yの(外径D, 肉厚t, 断面二次モーメントI)。線形テーパー(A-141改)。"""
        frac = y / s
        d = d_root + (d_tip - d_root) * frac
        t = t_root + (t_tip - t_root) * frac
        inner = d - 2.0 * t
        return d, t, math.pi * (d**4 - inner**4) / 64.0

    sections = [_section(y) for y in ys]

    # せん断力 V(y) = ∫y..s w dξ、曲げモーメント M(y) = ∫y..s w(ξ)·(ξ−y) dξ
    # (翼端から翼根へ台形則で累積: dV = w dξ, dM = V dξ)
    shear = [0.0] * n_pts
    moment = [0.0] * n_pts
    for i in range(n_pts - 2, -1, -1):
        shear[i] = shear[i + 1] + 0.5 * (w[i] + w[i + 1]) * dy
        moment[i] = moment[i + 1] + 0.5 * (shear[i] + shear[i + 1]) * dy

    stress = [
        m * (sec[0] / 2.0) / sec[2] for m, sec in zip(moment, sections, strict=True)
    ]

    # たわみ: θ(y) = ∫0..y M/(E·I(y)) dξ、δ(y) = ∫0..y θ dξ(境界条件 θ(0)=δ(0)=0)
    slope = [0.0] * n_pts
    deflection = [0.0] * n_pts
    curvature = [
        m / (e_mod * sec[2]) for m, sec in zip(moment, sections, strict=True)
    ]
    for i in range(1, n_pts):
        slope[i] = slope[i - 1] + 0.5 * (curvature[i - 1] + curvature[i]) * dy
        deflection[i] = deflection[i - 1] + 0.5 * (slope[i - 1] + slope[i]) * dy

    # 最大応力(テーパー桁では翼根以外に現れ得るため全ステーション探索)
    max_idx = max(range(n_pts), key=lambda i: stress[i])
    sigma_max = stress[max_idx]
    inertia = sections[0][2]  # 翼根断面(レポート用)
    safety_factor = sigma_allow / sigma_max if sigma_max > 0 else math.inf
    tip_deflection = deflection[-1]
    deflection_ratio = tip_deflection / s

    # 局所座屈スクリーニング(A-144): 円筒殻の古典弾性座屈 σ_cr = E·t/(r·√(3(1−ν²)))
    # 出典: Timoshenko & Gere, Theory of Elastic Stability。実機はNASA SP-8007の
    # ノックダウン(0.2〜0.7)がかかるため、応力比>0.5で警告する保守的スクリーニング
    buckling_factor = math.sqrt(3.0 * (1.0 - nu**2))
    buckling_ratio_max = 0.0
    buckling_ratio_at_root = 0.0
    for i in range(n_pts):
        d_i, t_i, _ = sections[i]
        sigma_cr = e_mod * t_i / ((d_i / 2.0) * buckling_factor)
        ratio = stress[i] / sigma_cr if sigma_cr > 0 else math.inf
        if i == 0:
            buckling_ratio_at_root = ratio
        buckling_ratio_max = max(buckling_ratio_max, ratio)

    if not all(math.isfinite(v) for v in (sigma_max, safety_factor, tip_deflection)):
        raise CalculationError("梁解析の結果が非有限値です(入力を確認してください)")

    def _fmt(value: float, unit: str = "") -> str:
        return f"{format(value, '.6g')} {unit}".strip()

    quantities = {
        "lift_half_wing": Quantity(value=lift_half, unit="N"),
        "section_moment_of_inertia": Quantity(value=inertia, unit="m^4"),
        "root_shear": Quantity(value=shear[0], unit="N"),
        "root_bending_moment": Quantity(value=moment[0], unit="N*m"),
        "root_bending_stress": Quantity(value=stress[0], unit="Pa"),
        "max_bending_stress": Quantity(value=sigma_max, unit="Pa"),
        "max_stress_position": Quantity(value=ys[max_idx], unit="m"),
        "tip_deflection": Quantity(value=tip_deflection, unit="m"),
        "tip_deflection_ratio": Quantity(value=deflection_ratio, unit="dimensionless"),
        "safety_factor": Quantity(value=safety_factor, unit="dimensionless"),
        "buckling_stress_ratio_root": Quantity(
            value=buckling_ratio_at_root, unit="dimensionless"
        ),
        "buckling_stress_ratio_max": Quantity(
            value=buckling_ratio_max, unit="dimensionless"
        ),
    }

    formulas = [
        FormulaRecord(
            symbol="L_half", name="半翼揚力(荷重条件)",
            expression="L_half = n·m_total·g / 2",
            substitutions={
                "n": _fmt(n), "m_total": _fmt(total_mass, "kg"),
                "g": _fmt(STANDARD_GRAVITY_M_S2, "m/s²"),
            },
            result=quantities["lift_half_wing"],
            source="荷重条件(荷重倍数nは人間が確定した入力値。PROJECT_BRIEF §2)",
        ),
        FormulaRecord(
            symbol="I", name="断面二次モーメント(円管・翼根)",
            expression="I(y) = π·(D(y)⁴ − d(y)⁴) / 64, d = D − 2t(D, tは線形テーパー)",
            substitutions={
                "D_root": _fmt(d_root, "m"), "t_root": _fmt(t_root, "m"),
                "D_tip": _fmt(d_tip, "m"), "t_tip": _fmt(t_tip, "m"),
            },
            result=quantities["section_moment_of_inertia"], source=_SOURCE,
        ),
        FormulaRecord(
            symbol="M_root", name="翼根曲げモーメント",
            expression="M(y) = ∫y..s w(ξ)·(ξ−y) dξ(台形則)。境界条件: 翼根完全固定",
            substitutions={
                "分布": request.lift_distribution.value, "s": _fmt(s, "m"),
                "L_half": _fmt(lift_half, "N"),
            },
            result=quantities["root_bending_moment"], source=_SOURCE,
        ),
        FormulaRecord(
            symbol="σ_root", name="翼根曲げ応力", expression="σ(y) = M(y)·(D(y)/2) / I(y)",
            substitutions={
                "M": _fmt(moment[0], "N·m"), "D/2": _fmt(d_root / 2, "m"),
                "I": _fmt(inertia, "m⁴"),
            },
            result=quantities["root_bending_stress"], source=_SOURCE + "(線形弾性 A-143)",
        ),
        FormulaRecord(
            symbol="δ_tip", name="翼端たわみ",
            expression="δ = ∬ M/(E·I) dy²(台形則2回積分。境界条件: δ(0)=θ(0)=0)",
            substitutions={"E": _fmt(e_mod, "Pa"), "I": _fmt(inertia, "m⁴")},
            result=quantities["tip_deflection"], source=_SOURCE,
        ),
        FormulaRecord(
            symbol="SF", name="安全率", expression="SF = σ_allow / σ_max",
            substitutions={
                "σ_allow": _fmt(sigma_allow, "Pa"),
                "σ_max": _fmt(sigma_max, "Pa"),
                "最大応力位置": _fmt(ys[max_idx], "m"),
            },
            result=quantities["safety_factor"],
            source="σ_allowは人間が確定した入力値(PROJECT_BRIEF §10。PBMは材料強度を決定しない)",
        ),
        FormulaRecord(
            symbol="σ_cr", name="局所座屈スクリーニング(古典弾性座屈)",
            expression="σ_cr = E·t / (r·√(3(1−ν²)))(各ステーションで σ/σ_cr を評価)",
            substitutions={
                "E": _fmt(e_mod, "Pa"), "ν": _fmt(nu),
                "max(σ/σ_cr)": _fmt(buckling_ratio_max),
            },
            result=quantities["buckling_stress_ratio_max"],
            source=(
                "Timoshenko & Gere, Theory of Elastic Stability。実機はNASA SP-8007の"
                "ノックダウン(0.2–0.7)適用が必要(A-144)。スクリーニングのみ"
            ),
        ),
    ]

    warnings: list[CalcWarning] = []
    if safety_factor < request.required_safety_factor:
        warnings.append(CalcWarning(
            code="SAFETY_FACTOR_DEFICIT", severity=Severity.violation,
            message=(
                f"安全率 {safety_factor:.2f} が要求値 {request.required_safety_factor:.2f} "
                "を下回っています。桁断面の増強または荷重条件の見直しが必要です"
            ),
        ))
    if deflection_ratio > 0.10:
        warnings.append(CalcWarning(
            code="DEFLECTION_LARGE", severity=Severity.warning,
            message=(
                f"翼端たわみ比 {deflection_ratio:.3f} > 0.10。線形梁理論(A-143)の"
                "適用範囲を超えつつあります。幾何非線形・上反角変化の影響に注意"
            ),
        ))
    if t_root / d_root < 0.01:
        warnings.append(CalcWarning(
            code="THIN_WALL_BUCKLING_RISK", severity=Severity.warning,
            message=(
                f"肉厚/外径比 {t_root/d_root:.4f} < 0.01。薄肉のため局所座屈の詳細検討が必要です"
            ),
        ))
    if buckling_ratio_max > 0.5:
        warnings.append(CalcWarning(
            code="BUCKLING_SCREENING", severity=Severity.warning,
            message=(
                f"曲げ応力が古典弾性座屈応力の {buckling_ratio_max:.2f} 倍に達しています"
                "(スクリーニング閾値0.5超、A-144)。実機のノックダウン(NASA SP-8007: "
                "0.2–0.7)を考慮すると座屈リスクがあります。詳細解析・要素試験で検証してください"
            ),
        ))

    assumptions = [
        AssumptionRecord(
            id="A-140", name="揚力分布", value=request.lift_distribution.value,
            rationale="elliptic=理想分布/uniform=保守側。実分布は翼幅方向解析(Phase 2)で更新",
        ),
        AssumptionRecord(
            id="A-141", name="円管桁(線形テーパー)",
            value=(
                f"root: D={d_root:g} m, t={t_root:g} m / tip: D={d_tip:g} m, t={t_tip:g} m"
                + ("" if is_tapered else "(一定断面)")
            ),
            rationale="断面は線形テーパーの円管。積層構成・非円形断面は未対応",
        ),
        AssumptionRecord(
            id="A-144", name="局所座屈スクリーニング閾値", value="σ/σ_cr(古典) > 0.5 で警告",
            rationale=(
                "古典弾性座屈(Timoshenko & Gere)に対する実機ノックダウンは"
                "NASA SP-8007で0.2–0.7。0.5は保守的スクリーニングであり、"
                "座屈成立性の判定には詳細解析・要素試験が必要"
            ),
        ),
        AssumptionRecord(
            id="A-145", name="等方性近似(ポアソン比)", value=f"ν={nu:g}",
            rationale="座屈式は等方材料前提。CFRP積層の異方性は未対応(要詳細解析)",
        ),
        AssumptionRecord(
            id="A-142", name="自重による荷重軽減を無視", value="—",
            rationale="翼構造自重は揚力と逆向きに働き応力を下げるため、無視は安全側",
        ),
        AssumptionRecord(
            id="A-143", name="線形弾性・小変形の梁理論", value="—",
            rationale="たわみ比>0.1では幾何非線形の影響が無視できない(警告で通知)",
        ),
    ]

    step = max(1, (n_pts - 1) // 20)  # 出力は最大21点に間引き
    stations = [
        SparStation(
            y=Quantity(value=ys[i], unit="m"),
            shear=Quantity(value=shear[i], unit="N"),
            bending_moment=Quantity(value=moment[i], unit="N*m"),
            bending_stress=Quantity(value=stress[i], unit="Pa"),
            deflection=Quantity(value=deflection[i], unit="m"),
        )
        for i in list(range(0, n_pts, step)) + ([n_pts - 1] if (n_pts - 1) % step else [])
    ]

    return SparAnalysisOutput(
        quantities=quantities,
        stations=stations,
        formulas=formulas,
        assumptions=assumptions,
        warnings=warnings,
    )
