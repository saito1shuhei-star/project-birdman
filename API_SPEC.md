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

## 状態遷移(Phase 1はAPI最小限)

`POST /api/projects/{project_id}/transition` → 200 / 409
```json
{"to": "review_required", "actor": "斉藤", "comment": "初期サイジング確認済み"}
```
approved/rejected への遷移は actor 必須。許可遷移は DOMAIN_MODEL.md §3。

## 製造用データ生成ガード(FR-004)

`POST /api/projects/{project_id}/manufacturing-export` → 409(status ≠ approved のとき)
Phase 1 では常に「approved以外は拒否」のガードのみ実装(生成本体はPhase 5)。
