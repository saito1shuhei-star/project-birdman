# ROADMAP — 開発ロードマップ

Phase定義の詳細は PROJECT_BRIEF.md §12。ここでは各Phaseの完了条件(Definition of Done)と依存を定義する。

## Phase 0 — 基盤設計【今回実装】

**DoD**: 設計文書13点が存在 / モノレポ構成 / backend(FastAPI+pytest+ruff)起動 / frontend(Next.js)ビルド可 /
SQLite永続化 / ヘルスチェックAPI / サンプルデータ / docker-compose定義 / CI定義。

## Phase 1 — 初期サイジングMVP【今回実装】

**DoD**: 縦スライス「プロジェクト作成→要求仕様入力(単位付き検証)→初期サイジング→式・仮定表示→保存→HTMLレポート→再現可能→代表値テスト合格」が動作。VALIDATION_PLAN §3 全項目。

## Phase 2 — 解析ソフト連携

- XFLR5アダプター(翼型・翼解析、mock/real区別、失敗時ログ保存)
- XROTORアダプター(プロペラ設計点解析)
- 主翼平面形のパラメトリックモデル(WingPlanform)
- 解析ジョブ管理(非同期実行、状態追跡)・結果比較画面・Alembic導入・Playwright導入
- **依存**: Phase 1。**リスク**: XFLR5のバッチ実行はバージョン依存が強い(xfoil直接利用も検討)

## Phase 3 — 構造・安定性

- 簡易梁モデル(主桁曲げ・せん断・たわみ、式と境界条件の明示)
- 質量・重心管理(部品台帳、推定/実測区別)・静安定余裕・尾翼容積サイジング
- 制約判定・承認ワークフローUI(review_required→approved、承認監査ログ)
- **依存**: Phase 1(質量・重心はPhase 2と並行可)

## Phase 4 — 最適化

- 設計変数・制約・評価関数の分離定義、SciPyによる制約付き最適化
- パレート解の生成と比較、感度分析、不確かさ分析(モンテカルロ)
- 安定性NG案の候補除外
- **依存**: Phase 2(空力評価)、Phase 3(構造制約)

## Phase 5 — CAD・シミュレーション

- CAD用パラメータ出力(CSV/JSON)→ DXF/STEP → Fusion 360スクリプト生成(承認済み設計のみ)
- 飛行シミュレーション(離陸・滑空・旋回)、レポート拡張(PDF/CSV)
- **依存**: Phase 3(承認フロー必須: FR-004)

## 横断事項

- Knowledge機能(設計判断記録)は Phase 3 から段階導入し、Phase 5 で検索・提案へ拡張
- PostgreSQL移行はマルチユーザー運用開始時(Phase 4目安)に判断
- 各Phase完了時に CHANGELOG.md と全設計文書を同期する
