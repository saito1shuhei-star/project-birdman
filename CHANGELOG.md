# CHANGELOG

## [Unreleased] - 2026-07-23(レイアウト刷新: 案A+Bハイブリッド)

### Changed — フロントエンドのレイアウトを工程ステッパー+概要ダッシュボードへ刷新

- プロジェクト画面(旧: 1ファイル約1600行の縦長ページ)を、共通シェル(`app/projects/[id]/layout.tsx`)+概要ダッシュボード+8つの工程ページに分割
- **ヘッダーバー**(案B): 機体名・状態バッジ+主要KPI(必要出力・出力余裕・翼面積・機体質量・静安定余裕)を常設表示
- **工程ステッパー**(案A): 左サイドバーに9工程(概要+Step 2/3/4–5/9/7/8/11/13)を配置。各工程に完了`✓`・違反バッジ`!n`・警告バッジ`n`を表示。狭幅では上部横スクロールに切替
- **概要ダッシュボード**(案B): KPIグリッド・「次にやること」誘導・全工程の違反/警告を集約表示・工程状態一覧。承認済み時はレポート導線を必ず表示(未解消の違反があれば注記)
- 共通部品を`lib/project-shell.tsx`(最新状態の一括ロード+工程状態計算)、`lib/ui.tsx`(QuantityField/WarningList/ExecutionBadge)、`lib/steps.ts`へ切り出し
- E2Eをステッパー巡回型に更新(全9工程を横断)。ビルド・E2E・バックエンド266件・lint すべて成功

## [Unreleased] - 2026-07-22(Codex版PBMの統合 第1弾)

### Added — XROTOR実連携・XFLR5ハンドオフ(Codex版 commit 6a9e400 から統合)

- 統合方針を決定: **GitHub版(本リポジトリ)を本流**とし、Codex版の機能を段階統合([docs/INTEGRATION_PLAN.md](docs/INTEGRATION_PLAN.md)。データ移行は不要=Codex版に実データ0件を確認)
- **XROTOR 7.55実連携**: 単位付き構造化ケース(ARBI任意形状+AERO 13係数+運転点)からのスクリプト生成、隔離サブプロセス実行(シェル不使用・パス脱出検証・タイムアウト)、入力/stdout/stderr/生成ファイルの全証跡保存(BinaryArtifact: base64+SHA-256)、公式サマリ取込(不完全なら拒否=捏造しない)。API: /xrotor-scripts, /xrotor-runs, /xrotor-imports。環境変数PBM_XROTOR_VERSIONを追加
- **XFLR5ハンドオフ**: コマンド実行非対応(公式Ticket #57)を踏まえ、入力ZIP(manifest+README+翼型座標、「解析結果ではない」明示)→GUI手動実行→結果表取込(alpha/CL/CD/Cm必須、execution_mode=imported、派生値追加なし)を正式経路として実装。API: /xflr5-handoffs, /xflr5-imports
- 角度単位検証(ensure_angle/ensure_inverse_angle)をquantitiesへ追加(pintでは角度が無次元のため単位名で判定)
- SolverUnavailableError→409 / SolverNotImplementedError→501 のAPIハンドラを追加
- [docs/REFERENCES.md](docs/REFERENCES.md): 気象API・XROTOR/XFLR5/Fusion・NIST等の情報源一覧を統合
- 残りの統合対象(気象・認証・大会運用・ジオメトリ・Fusion等)をT-510〜T-518として登録
- テスト34件追加(スクリプト生成のSI変換手計算検証・サマリ/表パーサ・API統合。計266件)

## [Unreleased] - 2026-07-19(T-304・レポート統合・梁拡張・T-401)

### Added — T-304 承認ワークフロー+監査ログ

- approvalsテーブル(マイグレーション`df0509daf2b8`)。手動・自動を問わず**すべての状態遷移を監査記録**(自動遷移はactor=NULL)。`GET /transitions`(許可遷移)・`GET /approvals`(履歴)を新設し、承認UI(判断者名・コメント入力、許可遷移ボタン、履歴表示)を実装。E2Eでanalyzed→review_required→approvedのフローを検証

### Added — サイジングレポートへのStep 4–9統合

- HTMLレポートに「プロジェクト現況」節を追加: 平面形導出量・空力解析(mock明示)・質量特性(台帳)・静安定・梁解析・承認履歴。**レポート生成時点の最新データでありサイジング実行時点と異なり得る旨を明記**

### Added — 梁モデル拡張(テーパー桁・座屈スクリーニング)

- 線形テーパー円管(翼端外径・肉厚を任意指定)。応力は全ステーション探索(max_bending_stress / max_stress_position)、たわみは変断面EIで数値積分。一定断面の結果は従来と同一(回帰テストで担保)
- 局所座屈スクリーニング: 古典弾性座屈 σ_cr=E·t/(r·√(3(1−ν²)))(Timoshenko & Gere)に対する応力比を全ステーションで評価し、>0.5で警告(A-144: NASA SP-8007のノックダウン0.2–0.7を考慮した保守的スクリーニング。成立性判定は詳細解析・要素試験が必要)。ν=0.3等方近似(A-145、CFRP異方性は未対応)

### Added — T-401 最適化基盤MVP(設計スイープ+パレート)

- 設計変数(翼幅・巡航速度・CL)のグリッドスイープ(1–2変数、評価≤200)。評価は初期サイジングと同一モデル・同一警告。violation警告=不可行の制約判定、必要出力最小×L/D最大の2目的パレート抽出(支配関係の標準定義、単体テスト付き)。**最適解の自動採用はしない**(候補提示のみ、A-150)。API+UI実装、E2Eに組込み

## [Unreleased] - 2026-07-19(Phase 3前半+E2E)

### Added — T-302 質量・重心台帳(Step 9)

- MassItemドメインモデル(機体座標系A-135、点質量近似A-136)、mass_itemsテーブル+マイグレーション`bd57b817d300`、CRUD API、質量特性計算(総質量/重心/慣性モーメント/カテゴリ内訳/機体質量目標との差、RC-M1手計算検証)。「大会搭載機材」カテゴリ(A-116)・推定/実測区別・目標超過違反警告付き。フロントエンドに台帳UI

### Added — T-303 静安定余裕(Step 7)

- 尾翼容積・中立点・静安定余裕の計算エンジン(Nelson標準式、RC-S1手計算検証、SM推奨0.05–0.20=A-133)。翼幾何は平面形・重心は質量台帳から自動取得し、導出文脈ごとanalysis_runsへ保存(トレーサビリティ)。胴体・プロペラ寄与は含まない簡易推定(A-131)であることを明示

### Added — T-301 簡易梁モデル(Step 8)

- 主桁の片持ち梁解析(円管断面、楕円/一様分布、せん断/曲げ/応力/たわみ/安全率、境界条件・式・単位を明示)。**荷重倍数・ヤング率・許容応力・要求安全率は既定値なしの人間入力必須**(PROJECT_BRIEF §2, §10)。解析解リファレンスRC-B1(楕円根元モーメント4Ls/3π等)・等分布たわみw·s⁴/(8EI)との数値一致テスト。座屈・ねじり・疲労はMVP対象外(警告で通知)

### Added — T-206 Playwright E2E(T-108完了)

- @playwright/test+chromium導入。playwright.config.tsがbackend(venv uvicorn・一時DB)+frontend(next start)を自動起動し、ゴールデンパス(プロジェクト作成→要求仕様→サイジング→平面形→空力→質量台帳→静安定→梁解析)を実ブラウザで検証。CIにe2eジョブ追加(失敗時トレースをアーティファクト保存)

## [Unreleased] - 2026-07-19(ルールブック再検証)

### Fixed — 大会規則の認識齟齬の修正

- **条文番号の誤記を訂正**: 飛行制限高度10mの出典を「大会規約1条b」→「**3条b**」へ修正(A-114)。プラットホーム標準数値は2条、飛行準備制限5分は1条e
- ルールブック内部の不整合を発見・記録: 規約3条e罰則2項が「飛行禁止区域7」を参照するが列挙は1〜6のみ(事務局確認事項として記録)

### Added — T-115 要求仕様の変更履歴・差分表示

- プロジェクト画面に変更履歴セクションを追加(リビジョン一覧+前リビジョンとの項目別差分「旧 → 新」表示。設計変更の追跡: PROJECT_BRIEF目的「設計変更による影響を追跡できない」への対応の第一歩)

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
