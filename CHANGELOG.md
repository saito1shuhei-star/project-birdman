# CHANGELOG

## [Unreleased] - 2026-07-19(続き)

### Added — T-201 / T-116 / T-202

- **T-201 Alembic導入**: backend/alembic/にベースラインリビジョン(8b9ce2ae4e20: projects/requirement_specs/sizing_runs)を追加。`resolve_database_url()`と接続先を共通化。開発DBは引き続き`create_all`で動作するが、Phase 2以降のスキーマ変更はマイグレーション経由に。スモークテスト追加(alembic upgrade headで空DBに正しくテーブル生成されることを確認)
- **T-116 離陸/風速条件・パイロット年齢**: RequirementSpecInputに`wind_speed_limit`(既定5m/s, A-113)・`flight_altitude_limit`(既定10m, A-114)・`pilot_age`(任意)を追加。現行の定常水平飛行モデルには未使用(記録・レポート表示のみ)。PBMは大会規則の年齢適合判定を行わない(PROJECT_BRIEF §10)。テスト9件追加
- **T-202 XFLR5アダプター(mock先行分)**: `AerodynamicSolverAdapter`の具象`XFLR5Adapter`を実装。`is_available()`はPBM_XFLR5_PATHの実在確認、`execution_mode=mock`は有限翼揚力線理論による近似ポーラ(`pbm.calculation.aero_mock_polar`、数値回帰テスト付き)を返す。`execution_mode=real`は未接続時`SolverUnavailableError`、接続時でも実行連携コード未実装のため`SolverNotImplementedError`を送出し、未実行の解析を実行済みに見せない(CON-003)。**real実行連携・API/UI結線・WingPlanformとの統合は未実装**(TASKS T-202b/T-204)
- 共通ハッシュ計算を`pbm.workflow.hashing.compute_input_hash`へ切り出し、sizing_service/XFLR5Adapterで共用

### Changed — 大会規則(鳥人間コンテストルールブック2025)の反映

- **破壊的変更**: `Category` enum を `distance/time_trial/other` から `glider/human_powered_propeller/other` へ修正(出典: 鳥人間コンテストルールブック2025 全19頁。大会概要により部門は「滑空機部門」「人力プロペラ機部門」の2部門と確定)
- ASSUMPTIONS.md: A-101(翼幅制限)の記述を訂正 — 大会規則上は機体サイズ・重量・形状に**制限なし**(大会規約4条)であり、wingspan_limitは大会規則ではなくチーム独自の製造・輸送上の設計制約であることを明記。A-113(競技中断風速閾値5m/s)・A-114(飛行制限高度10m)を追加
- REQUIREMENTS.md: FR-015(翼幅制限の位置づけ明示)を追加、§1.7に大会規則由来の参考値表(風速・飛行制限高度・プラットホーム仕様・70kmコース・パイロット年齢)を追加
- 安全率・材料強度について大会規則側に数値規定がないことを確認(PBMの「チームが決定する」方針と整合。対応不要)
- テスト・フロントエンドの category 選択肢を新enumへ更新。テスト69件・lint・frontendビルド再確認済み

## [0.1.0] - 2026-07-19

### Added — Phase 0(基盤)+ Phase 1(初期サイジングMVP)

- 設計文書13点(PROJECT_BRIEF, REQUIREMENTS, ARCHITECTURE, DOMAIN_MODEL, DATA_MODEL, API_SPEC, CALCULATION_SPEC, ASSUMPTIONS, VALIDATION_PLAN, ROADMAP, TASKS, README, CHANGELOG)
- backend: 単位安全な物理量モデル(Pint + Pydantic)、初期サイジング計算エンジン(定常水平飛行16式、FormulaRecord・仮定・警告付き)、設計状態機械、SolverExecution(execution_mode: real/mock/imported/analytical_estimate)、SQLite永続化、FastAPI(projects/requirements/sizing-runs/transition/製造ガード/health)、Jinja2 HTMLレポート
- frontend: Next.js + TypeScript 縦スライス(プロジェクト一覧・作成、要求仕様入力、サイジング実行、結果・警告表示、レポートリンク)
- テスト: Quantity単体、状態遷移、数値回帰(手計算RC-1)、再現性、API統合
- インフラ定義: docker-compose.yml、Dockerfile×2、GitHub Actions CI(いずれも定義のみ・実行未検証: TASKS T-112/T-113)
- サンプルデータ: data/samples/sample_requirements.json

### Notes

- 空力・推進の既定係数(CL, CD0, e, η等)はすべて暫定仮定(ASSUMPTIONS A-102〜A-107)。XFLR5/XROTOR連携(Phase 2)で更新予定
