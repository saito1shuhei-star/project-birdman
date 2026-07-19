# API_SPEC — REST API仕様(Phase 1)

Base URL: `http://localhost:8000`。全ボディはJSON。物理量は必ず `{"value": <number>, "unit": "<pint単位>"}`。
エラー: 404(不存在)、409(不正状態遷移)、422(検証エラー: 単位・次元・範囲・必須欠落)、500(内部エラー)。
OpenAPIドキュメント: `/docs`(自動生成)。

## ヘルスチェック

`GET /api/health` → 200 `{"status": "ok", "version": "<pbm version>"}`

## プロジェクト

`POST /api/projects` → 201
```json
{
  "team_name": "CIT鳥人間", "aircraft_name": "PBM-01", "design_year": 2026,
  "category": "distance", "design_lead": "斉藤", "unit_system": "SI",
  "version": "v0.1", "design_goal": "安定して1km"
}
```
返却: 上記 + `id`, `status`("draft"), `created_at`, `updated_at`

`GET /api/projects` → 200 リスト(作成日時降順)
`GET /api/projects/{project_id}` → 200 / 404

## 要求仕様

`PUT /api/projects/{project_id}/requirements` → 200(revisionを+1して新規保存。projectはdraftへ戻る)
```json
{
  "pilot_mass": {"value": 60, "unit": "kg"},
  "airframe_mass_target": {"value": 40, "unit": "kg"},
  "pilot_power_sustained": {"value": 250, "unit": "W"},
  "pilot_power_max": {"value": 400, "unit": "W"},
  "target_cruise_speed": {"value": 7.5, "unit": "m/s"},
  "target_distance": {"value": 1000, "unit": "m"},
  "wingspan_limit": {"value": 30, "unit": "m"},
  "air_density": {"value": 1.225, "unit": "kg/m^3"},
  "wind_speed_limit": {"value": 5.0, "unit": "m/s"},
  "flight_altitude_limit": {"value": 10.0, "unit": "m"},
  "pilot_age": 20,
  "cl_cruise": 1.0, "cl_max": 1.4, "cd0": 0.020, "oswald_efficiency": 0.90,
  "propeller_efficiency": 0.80, "drivetrain_efficiency": 0.95
}
```
- 単位付き項目に素の数値を渡す → 422
- 次元不一致("pilot_mass": {"value":1,"unit":"m"})→ 422
- 範囲外(CALCULATION_SPEC §2)→ 422
- 任意項目: pilot_power_max, target_distance, pilot_age。係数類・wind_speed_limit・flight_altitude_limitは省略時ASSUMPTIONSの既定値(A-102〜A-107, A-113, A-114)
- wingspan_limitは大会規則ではなくチーム独自の設計制約(FR-015)。wind_speed_limit/flight_altitude_limitは現行の初期サイジング計算には未使用(記録のみ、Phase 2–3で利用)。pilot_ageはPBMが大会規則適合判定を行うものではなく記録のみ(PROJECT_BRIEF §10)
- 返却: 保存済み仕様 + `revision`, `id`, `created_at`

`GET /api/projects/{project_id}/requirements` → 200 最新リビジョン / 404(未入力)
`GET /api/projects/{project_id}/requirements/history` → 200 全リビジョン

## 初期サイジング

`POST /api/projects/{project_id}/sizing-runs` → 201(最新要求仕様で実行。projectはcalculatedへ)
返却(抜粋):
```json
{
  "id": "…", "project_id": "…", "requirement_revision": 1,
  "input_hash": "sha256…",
  "outputs": {
    "quantities": {"wing_area": {"value": 28.4638, "unit": "m^2"}, "…": "…"},
    "formulas": [{"symbol": "S", "name": "必要翼面積",
                   "expression": "S = W / (q · CL_cruise)",
                   "substitutions": {"W": "980.665 N", "q": "34.453 Pa", "CL_cruise": "1.0"},
                   "result": {"value": 28.4638, "unit": "m^2"},
                   "source": "定常水平飛行 L=W(Anderson, Introduction to Flight)"}],
    "assumptions": [{"id": "A-104", "name": "有害抗力係数の既定値", "value": "0.020", "rationale": "…"}],
    "warnings": [{"code": "POWER_DEFICIT", "severity": "violation", "message": "…"}]
  },
  "execution": {"solver_name": "pbm.initial_sizing", "solver_version": "0.1.0",
                 "execution_mode": "analytical_estimate", "input_hash": "…",
                 "started_at": "…", "finished_at": "…", "result_status": "ok"},
  "created_at": "…"
}
```
要求仕様未入力 → 409。

`GET /api/projects/{project_id}/sizing-runs` → 200 リスト(降順、outputsは要約)
`GET /api/sizing-runs/{run_id}` → 200 全文 / 404

## レポート

`GET /api/sizing-runs/{run_id}/report` → 200 `text/html; charset=utf-8`
内容: プロジェクト情報、実行メタデータ(execution_modeバッジ)、入力(値+単位)、仮定、式(代入値つき)、
結果(SI、有効4桁)、警告、適用範囲、免責(FR-032)。

## 主翼平面形(Step 4、T-204)

`PUT /api/projects/{project_id}/planform` → 200(revision+1で新規保存)
```json
{
  "sections": [
    {"spanwise_position": {"value": 0, "unit": "m"}, "chord": {"value": 1.2, "unit": "m"},
     "twist_deg": 0, "airfoil": "DAE-11"},
    {"spanwise_position": {"value": 15, "unit": "m"}, "chord": {"value": 0.6, "unit": "m"},
     "twist_deg": -2, "airfoil": "DAE-11"}
  ]
}
```
- 左右対称翼の片翼(y昇順、先頭はy=0)。検証: 半翼幅1.5–22.5m、翼弦0.05–3.0m、ねじり±10度
- 返却: `revision`, `planform`, `derived`(span/area/aspect_ratio/mean_chord/taper_ratio、台形積分)

`GET /api/projects/{project_id}/planform` → 200 最新 / 404(未入力)

## 空力解析(Step 5、T-204。現状はmock固定)

`POST /api/projects/{project_id}/aero-analyses` → 201
- 最新の平面形(AR・翼型名)+要求仕様(e/CD0/CL_max)からリクエストを組み立て、
  XFLR5アダプターを実行。**現状はexecution_mode=mock固定**(揚力線理論の近似。
  XFLR5 real連携はT-202b)。モックであることは`execution.execution_mode`で機械的に判別可能
- 平面形または要求仕様が未入力 → 409
- projectがcalculatedのとき analyzed へ遷移
- 返却: `planform_revision`, `requirement_revision`, `input_hash`, `request`, `outputs`
  (polar[α, CL, CD, Cm, stalled], max_lift_to_drag, warnings), `execution`

`GET /api/projects/{project_id}/aero-analyses` → 200 リスト(降順)
`GET /api/aero-analyses/{run_id}` → 200 / 404

## 質量・重心台帳(Step 9、T-302)

- `POST /api/projects/{id}/mass-items` → 201(name, category, mass, position_x/y/z, source(estimated/measured), owner等)
- `GET /api/projects/{id}/mass-items` / `PUT /api/mass-items/{item_id}` / `DELETE /api/mass-items/{item_id}` → 204
- `GET /api/projects/{id}/mass-properties` → 総質量・重心・慣性モーメント・カテゴリ内訳・目標差(要求仕様があれば)・警告。部品0件は409
- カテゴリ: wing_structure / fuselage_structure / tail_structure / propulsion / cockpit / control / pilot / contest_equipment(A-116)/ other

## 静安定(Step 7、T-303)

- `POST /api/projects/{id}/stability-analyses`(body: horizontal_tail_area, tail_arm, wing_ac_position, tail_aspect_ratio ほか)→ 201
  - 翼幾何=最新平面形、重心=質量台帳から自動取得(未入力は409)。導出文脈もrequestに保存
  - 出力: V_H、揚力傾斜、dε/dα、中立点x_np、静安定余裕SM+警告(SM<0違反、0.05–0.20推奨)
- `GET /api/projects/{id}/stability-analyses`

## 主桁梁解析(Step 8、T-301)

- `POST /api/projects/{id}/spar-analyses` → 201
  - body: half_span, **load_factor(既定値なし)**, total_mass, lift_distribution(elliptic/uniform),
    spar_outer_diameter, spar_wall_thickness, **elastic_modulus / allowable_stress / required_safety_factor(いずれも既定値なし=人間確定)**
  - 出力: 翼根せん断/曲げ/応力、翼端たわみ、安全率、分布(最大21点)+警告(SF不足違反、たわみ比>0.1、薄肉座屈リスク)
- `GET /api/projects/{id}/spar-analyses`

## 設計スイープ(Step 11、T-401 MVP)

- `POST /api/projects/{id}/design-sweeps` → 201(要求仕様が基準。未入力409)
  - body: `{"variables": [{"variable": "wingspan"|"cruise_speed"|"cl_cruise", "minimum", "maximum", "steps"(2–15)}]}`(1–2変数、評価数≤200)
  - 評価は初期サイジングと同一モデル。violation警告のある案は不可行。必要出力最小×L/D最大のパレートフラグ付き候補一覧を返す(必要出力の小さい順)
  - **最適解の自動採用はしない**(候補提示のみ。採用は人間の承認事項: PROJECT_BRIEF §2)
- `GET /api/projects/{id}/design-sweeps`

## 承認・監査(T-304)

- `GET /api/projects/{id}/transitions` → `{current, allowed[], actor_required[]}`(承認UIが使用)
- `GET /api/projects/{id}/approvals` → 状態遷移の監査ログ(新しい順)。自動遷移(サイジング実行によるdraft→calculated等)は`actor=null`で記録される
- POST /transition は従来どおり。成功した遷移はすべてapprovalsに記録される

## 状態遷移(Phase 1はAPI最小限)

`POST /api/projects/{project_id}/transition` → 200 / 409
```json
{"to": "review_required", "actor": "斉藤", "comment": "初期サイジング確認済み"}
```
approved/rejected への遷移は actor 必須。許可遷移は DOMAIN_MODEL.md §3。

## 製造用データ生成ガード(FR-004)

`POST /api/projects/{project_id}/manufacturing-export` → 409(status ≠ approved のとき)
Phase 1 では常に「approved以外は拒否」のガードのみ実装(生成本体はPhase 5)。
