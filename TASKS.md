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
- [ ] T-202b XFLR5 real実行連携(実際のXFLR5起動・結果パース)。実機XFLR5での検証が必要 ← T-202
- [~] T-203 XROTORアダプター mock先行分(2026-07-19。`pbm.adapters.xrotor.XROTORAdapter`、`pbm.calculation.prop_mock_momentum`(運動量理論=理論上限、手計算リファレンスRC-P1・Froude恒等式・エネルギー収支テスト付き)。**real実行連携は未実装**(T-203b)
- [ ] T-203b XROTOR real実行連携(実際のXROTOR起動・結果パース)。実機XROTORでの検証が必要 ← T-203
- [x] T-204 WingPlanformモデルとUI、XFLR5解析のAPI/UI結線(2026-07-19。WingPlanform(台形積分・手計算検証付き)、wing_planforms/analysis_runsテーブル+マイグレーション、PUT/GET planform・POST aero-analyses API(mock固定・状態calculated→analyzed遷移)、フロントエンドStep4/5セクション(平面形エディタ・導出量・ポーラ表・モック明示)。実ブラウザE2E確認済み。**過程でCategory enum変更のデータ移行漏れによる500エラーを発見し、データ移行`9706411a806d`+回帰テストで修正**)
- [ ] T-205 解析ジョブ管理(非同期化)
- [x] T-206 Playwright導入(2026-07-19。@playwright/test+chromium、playwright.config.tsでbackend(uvicorn・一時DB)+frontend(next start)を自動起動、ゴールデンパスE2E(プロジェクト→要求→サイジング→平面形→空力→質量台帳→静安定→梁解析)合格。CIにe2eジョブ追加。T-108も完了)
- [x] T-301 簡易梁モデル(2026-07-19。片持ち梁・円管断面・楕円/一様分布。せん断/曲げ/応力/たわみ/安全率。**荷重倍数・E・許容応力・要求安全率は人間入力必須(既定値なし)**。解析解リファレンスRC-B1・等分布たわみ解析解との一致テスト付き。座屈・ねじり・疲労は対象外)
- [x] T-302 質量台帳(2026-07-19。MassItem CRUD+mass_itemsテーブル(マイグレーションbd57b817d300)+質量特性計算(総質量/重心/慣性/内訳/目標差、RC-M1手計算検証)。「大会搭載機材」カテゴリ(A-116)含む。UI実装済み)
- [x] T-303 静安定余裕(2026-07-19。V_H/中立点/SM計算(RC-S1手計算検証)。翼幾何=平面形、重心=質量台帳から自動取得し、導出文脈もanalysis_runsに保存。SM 0.05–0.20推奨(A-133)。胴体・プロペラ寄与は含まない(A-131))
- [ ] T-304 承認UI+監査ログ(approvalsテーブル)
- [ ] T-401 最適化基盤 / T-402 パレート比較
- [ ] T-501 CADパラメータ出力(approvedガード連動)/ T-502 PDF・CSVレポート
