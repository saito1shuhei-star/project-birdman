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
| category | enum: distance / time_trial / other | 部門(滑空機/人力プロペラ等は将来細分化) |
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
| takeoff / turn / wind / materials / manufacturing / safety_factor / rules | — | — | 2–3 で追加 |
| revision | int | | 保存毎に+1 |

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

## 4. Phase 2以降の拡張枠(モデルのみ予約、未実装)

- WingPlanform(Step 4): セクション列(位置、翼弦、翼型名、ねじり)
- AnalysisRun(Step 5–6): SizingRunと同形式で solver=XFLR5/XROTOR
- MassItem(Step 9): 部品質量・座標・推定/実測・不確かさ
- KnowledgeEntry(§5): 設計判断・理由・判断者・日時
