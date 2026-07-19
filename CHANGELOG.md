# CHANGELOG

## [Unreleased] - 2026-07-19(ルールブック再検証)

### Fixed — 大会規則の認識齟齬の修正

- **条文番号の誤記を訂正**: 飛行制限高度10mの出典を「大会規約1条b」→「**3条b**」へ修正(A-114)。プラットホーム標準数値は2条、飛行準備制限5分は1条e
- ルールブック内部の不整合を発見・記録: 規約3条e罰則2項が「飛行禁止区域7」を参照するが列挙は1〜6のみ(事務局確認事項として記録)

### Added — T-114 単位選択UIの拡充

- 要求仕様フォームの単位選択肢を拡充(質量kg/g/lb、速度m/s・km/h・knot、長さm/cm/mm/ft、密度kg/m³・g/L、高度m/ft)。フロントエンド提供単位の全てが正しい次元でバックエンドに受理されることをパラメトリックテストで担保(UI単位リストとテストの同期を明記)

### Added — T-204 WingPlanform+空力解析API/UI結線

- WingPlanformドメインモデル(左右対称・片翼セクション定義、台形積分による面積/AR/テーパー比導出、手計算リファレンステスト付き)
- wing_planforms / analysis_runs テーブル+Alembicマイグレーション(`aedebbdef4cb`)
- API: PUT/GET `/api/projects/{id}/planform`、POST/GET `/api/projects/{id}/aero-analyses`(XFLR5アダプターmock固定、planform/requirementリビジョンをトレース、状態calculated→analyzed遷移)
- フロントエンド: Step 4平面形エディタ(セクション追加/削除・導出量表示)+Step 5解析結果(モック明示バッジ・(L/D)max・ポーラ表)。実ブラウザE2E確認済み

### Fixed — Category enum変更のデータ移行漏れ(実DB 500エラー)

- 2026-07-19の`Category` enum修正(distance→human_powered_propeller等)で既存DB行の移行を怠り、GET /api/projectsが500になる実バグをE2Eで発見。データ移行`9706411a806d`(distance→human_powered_propeller、time_trial→other)と回帰テストを追加。**教訓: enum値変更は必ずデータ移行とセットで行う**(DATA_MODEL.mdに記録)

### Added — T-203 XROTORアダプター(mock先行分)

- `PropellerSolverAdapter`の具象`XROTORAdapter`と`pbm.calculation.prop_mock_momentum`(作動円板運動量理論)を実装。`execution_mode=mock`は理論上限の理想性能(推力・誘導速度・Froude効率・円板荷重)を返し、**理論上限である旨を常に警告に付与**(MOCK_IDEAL_EFFICIENCY)。realモードはXFLR5と同様に未接続/未実装を明示的にエラー(CON-003)。手計算リファレンスRC-P1(V=7.5m/s, D=3m, P=250W → T≈32.30N, η≈0.9689)、Froude恒等式η=V/(V+v_i)、エネルギー収支T·w=Pの検証テスト25件を追加(全122件)
- ASSUMPTIONS A-120(作動円板近似はモック専用・理論上限)

### Added — 再検証で判明した設計関連規定の反映

- [docs/CONTEST_RULES_2025_NOTES.md](docs/CONTEST_RULES_2025_NOTES.md) を新設(全条文の設計関連事実の要約、PBM反映状況マッピング、著作権注意)
- REQUIREMENTS CON-006〜CON-009: パイロット以外の動力・蓄積エネルギー禁止 / 浮昇補助禁止 / 部品落下・レール・遠隔操縦禁止 / 緊急離脱構造・着水衝撃保護(規約4条d, e)
- ASSUMPTIONS A-115(離陸解析の初期条件: 高さ10m・助走10m・3.5度・自力助走・手すり+750/+900mm)、A-116(オンボードカメラ等の大会搭載機材質量・要確認)
- ROADMAP更新: Phase 2に翼端手すりクリアランス確認、Phase 3に大会搭載機材カテゴリと緊急離脱チェックリスト、Phase 4に所要時間最小化(規約6条g: 同着時は時間で順位)、Phase 5に縮尺1/25三面図生成と70kmコースシミュレーション
- README: ルールブックPDFを公開リポジトリにコミットしない注意(讀賣テレビの著作物、B補則9)

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
