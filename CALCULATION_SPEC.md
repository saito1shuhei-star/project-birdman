# CALCULATION_SPEC — 計算仕様(Phase 1: 初期サイジング)

実装: `backend/src/pbm/calculation/initial_sizing.py`(純粋関数)。
すべての入力はSI正規化済み `Quantity`。出力の各値に式(FormulaRecord)・仮定・警告を付与する。

## 0. 記号と定数

| 記号 | 意味 | 単位 | 出典 |
|---|---|---|---|
| g | 標準重力加速度 = 9.80665 | m/s² | CODATA / ISO 80000-3 定義値 |
| ρ | 空気密度(既定 1.225) | kg/m³ | ISA海面標準(ICAO Doc 7488)。入力で上書き可 |
| μ | 空気粘性係数 = 1.789e-5 | Pa·s | ISA海面 15°C(ICAO Doc 7488) |
| m_pilot, m_af | パイロット質量、機体質量目標 | kg | 入力 |
| P_avail | パイロット持続出力 | W | 入力 |
| V | 目標巡航速度 | m/s | 入力 |
| b | 翼幅(翼幅制限を設計翼幅として使用) | m | 入力(仮定 A-101) |
| C_L, C_Lmax | 巡航揚力係数、最大揚力係数 | − | 入力/仮定 A-102, A-103 |
| C_D0 | 有害抗力係数(機体全体、S基準) | − | 入力/仮定 A-104 |
| e | オズワルド効率係数 | − | 入力/仮定 A-105 |
| η_p, η_d | プロペラ効率、駆動系効率 | − | 入力/仮定 A-106, A-107 |

## 1. 計算式(実行順)

各式は教科書的な定常水平飛行の関係式(出典: Anderson, "Introduction to Flight" / McCormick, "Aerodynamics, Aeronautics, and Flight Mechanics" の標準式)。

| # | 式 | 説明 |
|---|---|---|
| 1 | m_total = m_pilot + m_af | 全備質量 [kg] |
| 2 | W = m_total · g | 全備重量 = 定常水平飛行の必要揚力 L [N] |
| 3 | q = ½ · ρ · V² | 動圧 [Pa] |
| 4 | S = W / (q · C_L) | 必要翼面積 [m²](L=W を C_L で満たす) |
| 5 | W/S = W / S | 翼面荷重 [N/m²](= q·C_L) |
| 6 | AR = b² / S | アスペクト比 [−] |
| 7 | c̄ = S / b | 平均翼弦 [m](矩形近似。仮定 A-108) |
| 8 | V_stall = √(2W / (ρ · S · C_Lmax)) | 失速速度 [m/s] |
| 9 | C_Di = C_L² / (π · AR · e) | 誘導抗力係数 [−](楕円分布からの補正 e) |
| 10 | C_D = C_D0 + C_Di | 全機抗力係数 [−] |
| 11 | D = q · S · C_D | 全抗力 = 必要推力 T_req [N] |
| 12 | L/D = C_L / C_D | 揚抗比 [−] |
| 13 | P_aero = D · V | 抗力に抗する空力所要動力 [W] |
| 14 | P_pilot_req = P_aero / (η_p · η_d) | パイロット必要出力 [W] |
| 15 | ΔP = P_avail − P_pilot_req | 出力収支 [W](負なら持続飛行不可) |
| 16 | Re = ρ · V · c̄ / μ | 平均翼弦基準レイノルズ数 [−] |

## 2. 入力検証(範囲外は HTTP 422 拒否)

非物理値(≦0、NaN、inf)は常に拒否。妥当範囲(根拠: 鳥人間コンテスト出場機の一般的範囲、ASSUMPTIONS A-110):

| 入力 | 許容範囲(拒否境界) |
|---|---|
| pilot_mass | 30–150 kg |
| airframe_mass_target | 5–150 kg |
| pilot_power_sustained | 50–1500 W |
| target_cruise_speed | 3–20 m/s |
| wingspan_limit | 3–45 m |
| air_density | 0.9–1.4 kg/m³ |
| cl_cruise | 0.1–2.5 |
| cl_max | 0.5–3.0 かつ > cl_cruise |
| cd0 | 0.005–0.1 |
| oswald_efficiency | 0.5–1.0 |
| propeller_efficiency, drivetrain_efficiency | 0.3–1.0 |

## 3. 警告(計算は成功、severity付きで結果に添付)

| code | 条件 | severity | 意味 |
|---|---|---|---|
| POWER_DEFICIT | ΔP < 0 | violation | 必要出力がパイロット持続出力を超過 |
| POWER_MARGIN_LOW | 0 ≤ ΔP < 0.1·P_avail | warning | 出力余裕10%未満 |
| STALL_MARGIN_LOW | V / V_stall < 1.15 | warning | 失速余裕不足(推奨 V ≥ 1.15·V_stall、A-111) |
| ASPECT_RATIO_HIGH | AR > 40 | warning | 構造成立性・剛性に注意(HPA上限域) |
| ASPECT_RATIO_LOW | AR < 15 | info | HPAとして低AR。誘導抗力大 |
| REYNOLDS_LOW | Re < 2.0e5 | warning | 低Re領域。翼型データの適用範囲に注意 |
| WING_LOADING_HIGH | W/S > 60 N/m² | warning | HPAとして高翼面荷重(A-112) |
| CL_CRUISE_HIGH | C_L > 1.3 | info | 巡航CLが高い。失速余裕・抵抗増に注意 |

## 4. 適用範囲・限界(レポートに明記)

- 定常・等速・水平飛行のみ。旋回・離陸・突風は対象外(Phase 3+)
- C_D0, e, η_p, η_d は推定値。実測・詳細解析(XFLR5/XROTOR, Phase 2)で更新すること
- 翼幅制限値を設計翼幅として使用(A-101)。テーパー・ねじりの影響は含まない
- **本計算は analytical_estimate であり、実機の飛行安全を保証しない**

## 5. 数値方針

- ゼロ除算になり得る分母(q·C_L, S, b, η_p·η_d, μ 等)は入力検証で正値を保証
- 出力のNaN/infは CalculationError(発生時はバグ)
- 表示有効数字: レポートで4桁(内部は倍精度を保持)
- 再現性: 同一入力(input_hash一致)⇒ ビット同一の出力(純関数・乱数不使用)

## 6. 検証値(手計算リファレンス)

VALIDATION_PLAN.md §2 参照。tests/test_initial_sizing.py の期待値と同一の計算過程を記載している。
