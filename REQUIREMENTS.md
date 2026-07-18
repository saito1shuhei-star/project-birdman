# REQUIREMENTS — 要求仕様(Phase 0–1 実装対象を明確化)

上位文書: [PROJECT_BRIEF.md](PROJECT_BRIEF.md)。要求IDは `FR-`(機能)、`NFR-`(非機能)、`CON-`(制約)。
各要求の Phase 列は実装予定フェーズ。**本リリース(Phase 0–1)の合格条件は VALIDATION_PLAN.md に定義。**

## 1. 機能要求

### 1.1 プロジェクト管理

| ID | 要求 | Phase |
|---|---|---|
| FR-001 | ユーザーは機体プロジェクトを作成できる(チーム名、機体名、設計年度、部門、設計責任者、単位系、バージョン、設計目標) | 1 |
| FR-002 | プロジェクトの一覧・詳細を参照できる | 1 |
| FR-003 | プロジェクトはライフサイクル状態(draft/calculated/analyzed/review_required/approved/rejected/superseded)を持つ | 1(状態機械)/3(承認UI) |
| FR-004 | 承認前の設計から最終製造用データを生成できない | 1(ガード実装)/5(CAD出力時に強制) |

### 1.2 要求仕様入力

| ID | 要求 | Phase |
|---|---|---|
| FR-010 | パイロット質量・持続出力・最大出力・目標速度・目標距離・翼幅制限・機体質量目標等を単位付きで入力できる | 1 |
| FR-011 | すべての物理量は値+単位で受理し、API境界で次元を検証する。単位のない物理量は拒否する | 1 |
| FR-012 | 入力は物理妥当範囲で検証され、範囲外は拒否または警告される | 1 |
| FR-013 | 要求仕様はリビジョン管理され、過去リビジョンを参照できる | 1(保存)/2(比較UI) |
| FR-014 | 離陸条件・旋回条件・風速条件・製造制約・材料・安全率・大会規則制約を入力できる | 2–3 |

### 1.3 初期サイジング

| ID | 要求 | Phase |
|---|---|---|
| FR-020 | 全備質量、必要揚力、翼面積、翼面荷重、AR、平均翼弦、失速速度、誘導/有害抗力、必要推力、必要動力、L/D、Re、出力収支を計算する | 1 |
| FR-021 | 計算結果には使用した式・入力値・仮定・出典・警告・適用範囲を付与する | 1 |
| FR-022 | 同一入力に対して結果が再現可能である(入力ハッシュで同一性を判定) | 1 |
| FR-023 | 制約違反・推奨範囲逸脱を警告として表示する(失速余裕、出力超過、AR範囲、Re範囲等) | 1 |
| FR-024 | 計算実行は実行メタデータ(solver_name, execution_mode=analytical_estimate 等)と共に保存される | 1 |

### 1.4 レポート

| ID | 要求 | Phase |
|---|---|---|
| FR-030 | サイジング結果からHTMLレポートを生成できる(入力・仮定・式・結果・警告・単位・実行メタデータを含む) | 1 |
| FR-031 | PDF/CSV出力 | 5 |
| FR-032 | レポートには「本結果は解析的推定であり実機の飛行安全を保証しない」旨を明記する | 1 |

### 1.5 解析ソフト連携(Phase 2以降)

| ID | 要求 | Phase |
|---|---|---|
| FR-040 | XFLR5連携はAerodynamicSolverAdapter経由。入力生成→実行→取得→変換→比較 | 2 |
| FR-041 | XROTOR連携はPropellerSolverAdapter経由 | 2 |
| FR-042 | 解析結果は実行メタデータ(solver_name/version, execution_mode∈{real,mock,imported,analytical_estimate}, input_hash, started_at, finished_at, exit_code, stdout, stderr, raw_output_path, parser_version, result_status)を必ず持つ | 1(モデル定義)/2(実運用) |
| FR-043 | 外部ソフト未インストール時はモックとして明確に区別して動作する | 2 |
| FR-044 | 外部ソフト実行失敗時、ログ(stdout/stderr/raw出力)を保存する | 2 |

### 1.6 主翼・プロペラ・安定性・構造・質量・最適化・CAD・Knowledge・Simulation

Phase 2–5。PROJECT_BRIEF.md Step 4–13 および ROADMAP.md を参照。Phase 1 では実装しないが、
ドメインモデル・データモデルは拡張可能な形で設計する(DOMAIN_MODEL.md)。

## 2. 非機能要求

| ID | 要求 |
|---|---|
| NFR-001 | 内部計算はSI単位系。単位はPintで管理し、次元不一致を検出する |
| NFR-002 | 計算エンジンはFastAPI/Next.js/DB/外部ソフトから独立し、純粋関数中心で単体テスト可能 |
| NFR-003 | 代表的な手計算結果と一致する回帰テストを持つ(VALIDATION_PLAN.md) |
| NFR-004 | 計算結果から入力値・式・仮定・条件・ソフトウェアバージョンまで追跡できる |
| NFR-005 | NaN/無限大/ゼロ除算/非物理値を黙って返さない(例外または警告) |
| NFR-006 | Windowsで動作する(パスは pathlib、外部ソフトパスは環境変数で設定) |
| NFR-007 | 外部解析ソフトがなくても基本機能をテスト・実行できる |
| NFR-008 | 秘密情報をリポジトリに保存しない(環境変数 + .env は gitignore) |
| NFR-009 | AI出力は計算エンジン結果と分離して保存する(将来のAI機能実装時) |
| NFR-010 | エラーはログに記録し、握りつぶさない |

## 3. 制約

| ID | 制約 |
|---|---|
| CON-001 | 技術構成は PROJECT_BRIEF.md §7 に従う(Next.js/TypeScript、FastAPI/Pydantic、SQLite→PostgreSQL) |
| CON-002 | 人間の承認工程(PROJECT_BRIEF.md §2)を省略・自動化しない |
| CON-003 | 解析未実行の結果を実行済みのように表示しない |
| CON-004 | 経験係数・安全率は必ず出典または仮定(ASSUMPTIONS.md)を明記する |
| CON-005 | 実機の飛行安全を保証する表現を使用しない |

## 4. 用語

| 用語 | 定義 |
|---|---|
| 要求仕様 (RequirementSpec) | Step 2 で入力される設計要求一式。リビジョン管理される |
| サイジング実行 (SizingRun) | ある要求仕様リビジョンに対する初期サイジング計算の1回の実行 |
| 実行モード (execution_mode) | real / mock / imported / analytical_estimate。analytical_estimate は解析ソフトを使わない理論式による推定 |
| 入力ハッシュ (input_hash) | 正規化した入力JSONのSHA-256。再現性と同一性判定に使用 |
