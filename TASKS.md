# TASKS — タスク管理

記法: `[ ]`未着手 `[x]`完了 `[~]`部分完了。`←` は依存。

## Phase 0 — 基盤(今回)

- [x] T-001 設計文書13点の作成(PROJECT_BRIEF, REQUIREMENTS, ARCHITECTURE, DOMAIN_MODEL, DATA_MODEL, API_SPEC, CALCULATION_SPEC, ASSUMPTIONS, VALIDATION_PLAN, ROADMAP, TASKS, README, CHANGELOG)
- [x] T-002 backend骨格(pyproject, src/pbm各パッケージ, ruff, pytest)
- [x] T-003 frontend骨格(Next.js + TypeScript)
- [x] T-004 SQLite永続化(SQLAlchemy, create_all)
- [~] T-005 docker-compose.yml と Dockerfile — **定義のみ。本環境にDocker未導入のため未実行検証(A-204)**
- [x] T-006 GitHub Actions CI(2026-07-19 初回実行成功。backend: ruff+pytest / frontend: build。T-113参照)
- [x] T-007 サンプル機体データ(data/samples/)
- [x] T-008 APIヘルスチェック
- [x] T-009 git init と初期コミット

## Phase 1 — 初期サイジングMVP(今回)

- [x] T-101 Quantityモデル(Pint、次元検証、SI正規化、NaN/inf拒否)
- [x] T-102 RequirementSpec(単位付き検証、範囲検証、既定値)
- [x] T-103 初期サイジング計算エンジン(式16本、FormulaRecord、警告)← T-101
- [x] T-104 状態機械(DesignState、遷移表、承認ガード)
- [x] T-105 API(projects / requirements / sizing-runs / transition / 製造ガード)← T-102–104
- [x] T-106 HTMLレポート(Jinja2、免責、execution_modeバッジ)← T-103
- [x] T-107 テスト(単体・数値回帰RC-1・API統合・再現性)
- [x] T-108 Playwright E2E(2026-07-19、T-206として実装完了)
- [x] T-109 フロントエンド縦スライス(一覧/作成/要求入力/実行/結果/レポートリンク)← T-105

## 未完了・次にやること(優先度順)

- [x] T-110 **大会規則の正式値を反映**(2026-07-19、「鳥人間コンテストルールブック2025」全19頁確認・反映済み。部門区分を glider/human_powered_propeller に修正、翼幅制限は大会規則ではないことを訂正、風速5m/s・飛行制限高度10m等をASSUMPTIONS A-113/A-114・REQUIREMENTS §1.7に記録。安全率・強度は大会規則側に数値規定なしを確認)
- [ ] T-111 過去機体1機分の実データでRC-1以外の妥当性確認(VALIDATION_PLAN §4)— ユーザー確認済み: 現時点では実測データなし。データ入手後に着手
- [ ] T-112 docker compose up の実機検証(Docker導入後)← T-005
- [x] T-113 GitHubリモート作成とCI初回実行(2026-07-19。公開リポジトリ https://github.com/saito1shuhei-star/project-birdman を作成しpush。CI初回実行success(34秒)。以後、push毎にruff+pytest+frontend buildが自動実行される)
- [x] T-114 フロントエンドの要求仕様フォームの単位選択拡充(2026-07-19。質量kg/g/lb、速度m/s・km/h・knot、長さm/cm/mm/ft、密度kg/m³・g/L、高度m/ft。提供単位が次元込みでバックエンド受理されることをテストで担保)
- [x] T-115 requirements/historyの差分表示(2026-07-19。プロジェクト画面に変更履歴セクション(rev一覧+前リビジョンとの項目別差分「旧 → 新」)を追加。FR-013完了)

## Phase 2 以降(ROADMAP.md参照)

- [x] T-116 離陸条件・風速条件・パイロット年齢要件をRequirementSpecInputへ実装(2026-07-19。wind_speed_limit既定5m/s・flight_altitude_limit既定10m・pilot_age(任意、大会規則適合判定はしない)。現行の初期サイジング計算には未使用・記録とレポート表示のみ。テスト9件追加)
- [x] T-201 Alembic導入(2026-07-19。backend/alembic/、ベースラインリビジョン8b9ce2ae4e20。db.pyのcreate_allは開発利便性のため継続、Phase2以降のスキーマ変更はマイグレーション経由に。スモークテスト追加)
- [~] T-202 XFLR5アダプター mock先行分(2026-07-19。`pbm.adapters.xflr5.XFLR5Adapter`、`pbm.calculation.aero_mock_polar`(有限翼揚力線理論の近似ポーラ、数値回帰テスト付き)、`is_available()`でPBM_XFLR5_PATH検査。**real実行連携・API/UI結線・WingPlanform結合は未実装**(下記T-202b/T-203/T-204で継続)
- [x] T-202b XFLR5連携完成(2026-07-22、Codex版から統合。XFLR5はコマンド実行非対応(公式Ticket #57)のため、入力ZIPハンドオフ(POST /xflr5-handoffs)+GUI手動実行+結果表取込(POST /xflr5-imports、execution_mode=imported)を正式経路として実装。alpha/CL/CD/Cm必須・派生値追加なし)
- [~] T-203 XROTORアダプター mock先行分(2026-07-19。`pbm.adapters.xrotor.XROTORAdapter`、`pbm.calculation.prop_mock_momentum`(運動量理論=理論上限、手計算リファレンスRC-P1・Froude恒等式・エネルギー収支テスト付き)。**real実行連携は未実装**(T-203b)
- [x] T-203b XROTOR実連携(2026-07-22、Codex版から統合。XROTOR 7.55のARBI/AERO/OPERスクリプト生成(pbm/domain/xrotor_case.py)、隔離サブプロセス実行+全証跡保持(run_script)、公式サマリ取込(POST /xrotor-imports)。要PBM_XROTOR_PATH+PBM_XROTOR_VERSION。**実機XROTORでの実行検証は未実施**(実行ファイル設置後に要確認))
- [x] T-204 WingPlanformモデルとUI、XFLR5解析のAPI/UI結線(2026-07-19。WingPlanform(台形積分・手計算検証付き)、wing_planforms/analysis_runsテーブル+マイグレーション、PUT/GET planform・POST aero-analyses API(mock固定・状態calculated→analyzed遷移)、フロントエンドStep4/5セクション(平面形エディタ・導出量・ポーラ表・モック明示)。実ブラウザE2E確認済み。**過程でCategory enum変更のデータ移行漏れによる500エラーを発見し、データ移行`9706411a806d`+回帰テストで修正**)
- [ ] T-205 解析ジョブ管理(非同期化)
- [x] T-206 Playwright導入(2026-07-19。@playwright/test+chromium、playwright.config.tsでbackend(uvicorn・一時DB)+frontend(next start)を自動起動、ゴールデンパスE2E(プロジェクト→要求→サイジング→平面形→空力→質量台帳→静安定→梁解析)合格。CIにe2eジョブ追加。T-108も完了)
- [x] T-301 簡易梁モデル(2026-07-19。片持ち梁・円管断面・楕円/一様分布。せん断/曲げ/応力/たわみ/安全率。**荷重倍数・E・許容応力・要求安全率は人間入力必須(既定値なし)**。解析解リファレンスRC-B1・等分布たわみ解析解との一致テスト付き。座屈・ねじり・疲労は対象外)
- [x] T-302 質量台帳(2026-07-19。MassItem CRUD+mass_itemsテーブル(マイグレーションbd57b817d300)+質量特性計算(総質量/重心/慣性/内訳/目標差、RC-M1手計算検証)。「大会搭載機材」カテゴリ(A-116)含む。UI実装済み)
- [x] T-303 静安定余裕(2026-07-19。V_H/中立点/SM計算(RC-S1手計算検証)。翼幾何=平面形、重心=質量台帳から自動取得し、導出文脈もanalysis_runsに保存。SM 0.05–0.20推奨(A-133)。胴体・プロペラ寄与は含まない(A-131))
- [x] T-304 承認UI+監査ログ(2026-07-19。approvalsテーブル(マイグレーションdf0509daf2b8)、全状態遷移を監査記録(自動遷移はactor=NULL)、GET /transitions(許可遷移)・GET /approvals(履歴)、承認UI(actor/comment入力・許可遷移ボタン・履歴表示)。E2Eで承認フロー検証済み)
- [x] T-320 レポートへのStep 4–9統合(2026-07-19。平面形・空力(mock明示)・質量特性・静安定・梁解析・承認履歴を「プロジェクト現況」節としてHTMLレポートに追加。**レポート生成時点の最新データでありサイジング実行時点と異なり得る旨を明示**)
- [x] T-311 梁モデル拡張(2026-07-19。線形テーパー円管(翼端径・肉厚を任意指定、最大応力位置を全ステーション探索)、局所座屈スクリーニング(古典式σ_cr=E·t/(r·√(3(1−ν²)))、比>0.5で警告。A-144/A-145)。一定断面の回帰テストで既存結果不変を確認)
- [~] T-401 最適化基盤MVP(2026-07-19。設計変数(翼幅/巡航速度/CL)のグリッドスイープ、violation警告=不可行の制約判定、必要出力最小×L/D最大の2目的パレート抽出、API+UI。**最適解の自動採用はしない**。SciPyによる連続最適化・感度分析・不確かさ分析は未実装 → T-402)
- [ ] T-402 連続最適化(SciPy)・感度分析・不確かさ分析(モンテカルロ)← T-401
- [ ] T-501 CADパラメータ出力(approvedガード連動)/ T-502 PDF・CSVレポート

## Codex版PBMの統合(docs/INTEGRATION_PLAN.md参照。統合元パスは同計画書に記載)

- [ ] T-510 質量台帳の変更履歴+target種別(統合元: mass_properties_persistence.py)— 優先度高
- [ ] T-511 気象アダプター(Open-Meteo/NASA POWER/NOAA/気象庁アメダス)+観測地点選択(external_data.py, weather_sites.py)— 優先度高
- [ ] T-512 フライト条件判断の記録(風速の瞬間値/時間平均区別、チーム判断と実行委員会決定の分離)(flight_conditions.py)— 優先度高
- [ ] T-513 大会運用一式(規則チェックリスト・役割・機体チェック履歴・提出物版管理・当日指示・禁止区域地図・規則原本版管理)(api.py)— 優先度高
- [ ] T-514 認証(利用者ID+秘密鍵)・ロール・全操作履歴(auth.py, roles.py)— Web公開の前提
- [ ] T-515 機体ジオメトリ一元管理(胴体・尾翼・プロペラ、履歴付き)(aircraft_geometry.py)
- [ ] T-516 Fusionハンドオフ(CSV/ZIP+人による確認記録。**FR-004: approvedのみ**)(fusion_handoff.py)
- [ ] T-517 XROTOR設計点比較画面(xrotor_comparison*.py)
- [ ] T-518 Excel解析テンプレート出力(excel_adapter.py)
