# DOMAIN_MODEL — ドメインモデル

実装: `backend/src/pbm/domain/`。Pydantic v2 モデル。物理量はすべて `Quantity`。

## 1. 物理量 (quantities.py)

```
Quantity
  value: float          # 有限値のみ(NaN/inf拒否)
  unit: str             # Pintが解釈できる単位文字列("kg", "m/s", "W", "dimensionless")
  メソッド: to("unit"), si() -> SI正規化Quantity, magnitude_si, dimensionality
```

- `ensure_dimension(q, "[mass]")` — 次元検証。不一致は `UnitDimensionError`
- 無次元係数(CL, e, 効率)は `float` + Fieldの範囲制約で扱う(単位系事故の対象外。REQUIREMENTS FR-011の例外として明示)

## 2. エンティティ

### Project (entities.py)

| 属性 | 型 | 備考 |
|---|---|---|
| id | UUID(str) | |
| team_name / aircraft_name | str | 必須 |
| design_year | int | 例: 2026 |
| category | enum: glider / human_powered_propeller / other | 部門(「鳥人間コンテストルールブック2025」大会概要により確定。滑空機部門/人力プロペラ機部門。ASSUMPTIONS A-203) |
| design_lead | str | 設計責任者 |
| unit_system | enum: SI(将来拡張枠) | 表示単位系。内部は常にSI |
| version | str | 機体設計バージョン |
| design_goal | str | 自由記述 |
| status | DesignState | 状態機械(下記) |
| created_at / updated_at | datetime(UTC) | |

### RequirementSpec — Step 2(Phase 1 サブセット)

| 属性 | 型 | 次元 | Phase |
|---|---|---|---|
| pilot_mass | Quantity | [mass] | 1 |
| airframe_mass_target | Quantity | [mass] | 1 |
| pilot_power_sustained | Quantity | [power] | 1 |
| pilot_power_max | Quantity? | [power] | 1(任意) |
| target_cruise_speed | Quantity | [speed] | 1 |
| target_distance | Quantity? | [length] | 1(任意・記録のみ) |
| wingspan_limit | Quantity | [length] | 1 |
| air_density | Quantity | [density] | 1(既定 1.225 kg/m³) |
| cl_cruise / cl_max / cd0 / oswald_efficiency | float | 無次元 | 1(既定値=ASSUMPTIONS参照) |
| propeller_efficiency / drivetrain_efficiency | float | 無次元 (0,1] | 1(既定値=ASSUMPTIONS参照) |
| wind_speed_limit | Quantity | [speed] | 1(既定 5 m/s、A-113。記録のみ・初期サイジング未使用) |
| flight_altitude_limit | Quantity | [length] | 1(既定 10 m、A-114。記録のみ・初期サイジング未使用) |
| pilot_age | int? | 無次元(歳) | 1(任意・記録のみ。大会規則適合判定はPBMが行わない) |
| turn / materials / manufacturing / safety_factor / rules | — | — | 2–3 で追加 |
| revision | int | | 保存毎に+1 |

`wind_speed_limit`/`flight_altitude_limit`はPROJECT_BRIEF Step 2の「離陸条件・風速条件」の一部として値を捕捉するが、CALCULATION_SPEC.mdの定常水平飛行モデルでは未使用(Phase 2–3の飛行包絡線・離陸解析で利用予定)。

### SizingRun — Step 3 の1回の実行

| 属性 | 型 |
|---|---|
| id / project_id / requirement_revision | |
| inputs_snapshot | RequirementSpec(JSON) |
| outputs | SizingOutput |
| execution | SolverExecution(execution_mode=analytical_estimate) |
| created_at | datetime |

### SizingOutput (results.py)

| 属性 | 型 | 内容 |
|---|---|---|
| quantities | dict[str, Quantity] | total_mass, required_lift, wing_area, wing_loading, aspect_ratio, mean_chord, stall_speed, induced_drag_coefficient*, parasite_drag_coefficient*, drag_total, required_thrust, lift_to_drag, aero_power, required_pilot_power, power_margin, reynolds_number(*は無次元だがQuantity(dimensionless)で記録) |
| formulas | list[FormulaRecord] | 使用した式(下記) |
| assumptions | list[AssumptionRecord] | 使用した仮定 |
| warnings | list[CalcWarning] | code / severity(info,warning,violation) / message |

### FormulaRecord

symbol, name, expression(例 `"S = W / (q · CL_cruise)"`), substitutions(記号→値+単位), result(Quantity), source(出典 or ASSUMPTIONSのID)

### AssumptionRecord

id(ASSUMPTIONS.mdのID), name, value, rationale

### SolverExecution (adapters/base.py — ドメイン結果に埋め込む)

solver_name, solver_version, execution_mode(real/mock/imported/analytical_estimate), input_hash(SHA-256),
started_at, finished_at, exit_code?, stdout?, stderr?, raw_output_path?, parser_version?, result_status(ok/failed/partial)

## 3. 状態 (workflow/states.py)

```
DesignState = draft | calculated | analyzed | review_required | approved | rejected | superseded
```

許可遷移(それ以外は InvalidTransitionError):

| from | to |
|---|---|
| draft | calculated |
| calculated | analyzed, review_required, draft |
| analyzed | review_required, draft |
| review_required | approved, rejected, draft |
| approved | superseded |
| rejected | draft |

- 要求仕様の更新 ⇒ プロジェクトは draft へ戻る(計算結果は残るが最新リビジョンと不一致になる)
- approved 以外で製造用データ生成 API を呼ぶと `ApprovalRequiredError`
- approve/reject は actor(人名)必須

## 4. Phase 2 実装済みモデル(T-202〜T-204)

- **WingPlanform**(planform.py): WingSection(spanwise_position, chord, twist_deg, airfoil)の列。
  左右対称・片翼定義(y昇順、先頭y=0)。導出量: span/area(台形積分)/aspect_ratio/mean_chord/taper_ratio
- **AeroAnalysisRequest/Output**(aero_analysis.py): 空力解析の入出力(polar[α,CL,CD,Cm,stalled], (L/D)max)
- **PropAnalysisRequest/Output**(prop_analysis.py): プロペラ解析の入出力(推力・誘導速度・Froude効率・円板荷重)
- **AnalysisRun**(persistence.analysis_runs): solver_name + planform/requirement revision + SolverExecution。
  mock/realはexecution_modeで機械的に区別(CON-003)

## 5. Phase 3 実装済みモデル(T-301〜T-303)

- **MassItem**(mass_item.py): 部品名・カテゴリ(pilot/contest_equipment等9種)・質量・座標(A-135座標系)・
  材料・推定/実測・不確かさ・担当者。点質量近似(A-136)
- **MassPropertiesOutput**(calculation.mass_properties): 総質量・重心・慣性モーメント・内訳・目標差
- **StabilityRequest/Output**(stability.py): 尾翼構成 → V_H・中立点・静安定余裕
- **SparAnalysisRequest/Output**(structure.py): 主桁梁解析。荷重倍数・材料値・要求安全率は既定値なし(人間確定)

## 6. 拡張枠(未実装)

- KnowledgeEntry(§5): 設計判断・理由・判断者・日時
- Approval(Phase 3後半): 承認監査ログ
