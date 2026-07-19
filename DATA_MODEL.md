# DATA_MODEL — データモデル(永続化)

実装: `backend/src/pbm/persistence/`。SQLAlchemy 2.0。開発はSQLite、将来PostgreSQL(NFR互換性のためSQLite固有機能を避ける)。

## 方針

- 物理量はDBに **JSON(value+unit)** で保存する。単位を落とした素のfloat列を作らない
- 検索・結合キーのみ通常列(id, project_id, revision, input_hash, created_at, status)
- スキーマ進化の初期コストを抑えるため、仕様本体・計算結果はJSON列(ドメインモデルのdump)で保持し、
  Pydanticで読み戻し時に検証する。PostgreSQL移行時はJSONB
- 日時はUTC ISO8601

## テーブル

### projects

| 列 | 型 | 制約 |
|---|---|---|
| id | TEXT(UUID) | PK |
| team_name, aircraft_name, design_lead, version, design_goal | TEXT | |
| design_year | INTEGER | |
| category | TEXT | enum値 |
| unit_system | TEXT | 現状 "SI" |
| status | TEXT | DesignState |
| created_at, updated_at | TEXT(UTC ISO8601) | |

### requirement_specs

| 列 | 型 | 制約 |
|---|---|---|
| id | TEXT(UUID) | PK |
| project_id | TEXT | FK projects.id, ON DELETE CASCADE |
| revision | INTEGER | UNIQUE(project_id, revision)。1始まり |
| payload | TEXT(JSON) | RequirementSpec全体(値+単位) |
| created_at | TEXT | |

### sizing_runs

| 列 | 型 | 制約 |
|---|---|---|
| id | TEXT(UUID) | PK |
| project_id | TEXT | FK projects.id, ON DELETE CASCADE |
| requirement_spec_id | TEXT | FK requirement_specs.id |
| input_hash | TEXT | SHA-256 hex。INDEX |
| inputs_snapshot | TEXT(JSON) | 実行時点の入力(リビジョン改変から独立) |
| outputs | TEXT(JSON) | SizingOutput(quantities/formulas/assumptions/warnings) |
| execution | TEXT(JSON) | SolverExecution |
| result_status | TEXT | ok/failed/partial(検索用に列にも複製) |
| created_at | TEXT | |

### wing_planforms(T-204で追加)

| 列 | 型 | 制約 |
|---|---|---|
| id | TEXT(UUID) | PK |
| project_id | TEXT | FK projects.id, ON DELETE CASCADE |
| revision | INTEGER | UNIQUE(project_id, revision)。1始まり |
| payload | TEXT(JSON) | WingPlanformInput(セクション列、値+単位) |
| created_at | TEXT | |

### analysis_runs(T-204で追加。XFLR5/XROTOR等の解析実行)

| 列 | 型 | 制約 |
|---|---|---|
| id | TEXT(UUID) | PK |
| project_id | TEXT | FK projects.id, ON DELETE CASCADE |
| solver_name | TEXT | "XFLR5" / "XROTOR" 等 |
| planform_revision / requirement_revision | INTEGER? | 入力の出所(トレーサビリティ) |
| input_hash | TEXT | SHA-256。INDEX |
| request / outputs / execution | TEXT(JSON) | リクエスト・結果・SolverExecution(mock/realはexecution内で区別) |
| result_status | TEXT | 検索用複製 |
| created_at | TEXT | |

### mass_items(T-302で追加。マイグレーション`bd57b817d300`)

| 列 | 型 | 制約 |
|---|---|---|
| id | TEXT(UUID) | PK |
| project_id | TEXT | FK projects.id, ON DELETE CASCADE |
| name / category | TEXT | 検索用に列化 |
| payload | TEXT(JSON) | MassItemInput全体(質量・座標は値+単位) |
| created_at / updated_at | TEXT | 台帳的性質のため上書き更新可(履歴主義の例外) |

静安定(pbm.static_stability)・梁解析(pbm.spar_beam)の実行結果はanalysis_runsに保存し、
`solver_name`でXFLR5等と区別する(一覧APIはソルバー別にフィルタ)。

### 将来テーブル(予約・未実装)

- approvals(Phase 3: run_id, actor, action, comment, created_at — 承認監査ログ)
- knowledge_entries(Phase 3+)

### スキーマ・データ変更の教訓(2026-07-19)

`Category` enumの値変更時に既存データの移行を怠り、実DBで500エラーが発生した
(テストは毎回新規DBのため検出不可、実機E2Eで検出)。**enum値や検証仕様の変更は、
必ずデータ移行(Alembic)とセットで行うこと。** リビジョン`9706411a806d`が該当移行。
回帰テスト: tests/test_alembic_migration.py::test_category_data_migration_converts_legacy_values

## マイグレーション

Alembic導入済み(2026-07-19、TASKS.md T-201)。`backend/alembic/`にベースラインリビジョン(`8b9ce2ae4e20`: projects/requirement_specs/sizing_runs)を配置。

- 接続先は`pbm.persistence.db.resolve_database_url()`と共通(`env.py`で解決。`PBM_DATABASE_URL`環境変数、未設定時は`backend/data/pbm.sqlite3`)
- `pbm.persistence.db.create_engine_and_sessionmaker()`は開発・テストの利便性のため引き続き`Base.metadata.create_all()`を呼ぶ(冪等なので既存テーブルには影響しない)。**Phase 2以降でテーブル構造を変更する場合は、create_allに頼らずAlembicマイグレーション(`alembic revision --autogenerate`)を作成し、`alembic upgrade head`で適用すること**
- テスト(`tests/test_alembic_migration.py`)で`alembic upgrade head`が空DBに現行スキーマを正しく作成できることを検証
- 実行コマンド: `cd backend && alembic revision --autogenerate -m "<説明>"` → 生成内容を確認 → `alembic upgrade head`

## 再現性

- `input_hash` = 正規化(キーソート、区切り統一)した inputs_snapshot JSON の SHA-256
- 同一 input_hash の再実行は新しい sizing_run 行を作る(履歴主義。上書きしない)。同一性は input_hash で判定
