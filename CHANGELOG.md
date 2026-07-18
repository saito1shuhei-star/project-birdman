# CHANGELOG

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
