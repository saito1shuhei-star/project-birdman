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
- [ ] T-108 Playwright E2E(Phase 2で導入)
- [x] T-109 フロントエンド縦スライス(一覧/作成/要求入力/実行/結果/レポートリンク)← T-105

## 未完了・次にやること(優先度順)

- [x] T-110 **大会規則の正式値を反映**(2026-07-19、「鳥人間コンテストルールブック2025」全19頁確認・反映済み。部門区分を glider/human_powered_propeller に修正、翼幅制限は大会規則ではないことを訂正、風速5m/s・飛行制限高度10m等をASSUMPTIONS A-113/A-114・REQUIREMENTS §1.7に記録。安全率・強度は大会規則側に数値規定なしを確認)
- [ ] T-111 過去機体1機分の実データでRC-1以外の妥当性確認(VALIDATION_PLAN §4)— ユーザー確認済み: 現時点では実測データなし。データ入手後に着手
- [ ] T-112 docker compose up の実機検証(Docker導入後)← T-005
- [x] T-113 GitHubリモート作成とCI初回実行(2026-07-19。公開リポジトリ https://github.com/saito1shuhei-star/project-birdman を作成しpush。CI初回実行success(34秒)。以後、push毎にruff+pytest+frontend buildが自動実行される)
- [ ] T-114 フロントエンドの要求仕様フォームに全項目の単位選択UI(現状は代表単位固定)
- [ ] T-115 requirements/historyの差分表示(FR-013後半)

## Phase 2 以降(ROADMAP.md参照)

- [x] T-116 離陸条件・風速条件・パイロット年齢要件をRequirementSpecInputへ実装(2026-07-19。wind_speed_limit既定5m/s・flight_altitude_limit既定10m・pilot_age(任意、大会規則適合判定はしない)。現行の初期サイジング計算には未使用・記録とレポート表示のみ。テスト9件追加)
- [x] T-201 Alembic導入(2026-07-19。backend/alembic/、ベースラインリビジョン8b9ce2ae4e20。db.pyのcreate_allは開発利便性のため継続、Phase2以降のスキーマ変更はマイグレーション経由に。スモークテスト追加)
- [~] T-202 XFLR5アダプター mock先行分(2026-07-19。`pbm.adapters.xflr5.XFLR5Adapter`、`pbm.calculation.aero_mock_polar`(有限翼揚力線理論の近似ポーラ、数値回帰テスト付き)、`is_available()`でPBM_XFLR5_PATH検査。**real実行連携・API/UI結線・WingPlanform結合は未実装**(下記T-202b/T-203/T-204で継続)
- [ ] T-202b XFLR5 real実行連携(実際のXFLR5起動・結果パース)。実機XFLR5での検証が必要 ← T-202
- [ ] T-203 XROTORアダプター(同様にmock先行)
- [ ] T-204 WingPlanformモデルとUI、XFLR5解析のAPI/UI結線(Step 5画面)← T-202
- [ ] T-205 解析ジョブ管理(非同期化)
- [ ] T-206 Playwright導入(T-108)
- [ ] T-301 簡易梁モデル / T-302 質量台帳 / T-303 静安定余裕 / T-304 承認UI+監査ログ
- [ ] T-401 最適化基盤 / T-402 パレート比較
- [ ] T-501 CADパラメータ出力(approvedガード連動)/ T-502 PDF・CSVレポート
