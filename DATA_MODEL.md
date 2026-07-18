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

### 将来テーブル(予約・未実装)

- analysis_runs(Phase 2: XFLR5/XROTOR。sizing_runsと同構造 + solver列 + raw_output_path)
- wing_planforms(Phase 2)
- mass_items(Phase 3)
- approvals(Phase 3: run_id, actor, action, comment, created_at — 承認監査ログ)
- knowledge_entries(Phase 3+)

## マイグレーション

Phase 0–1 は `Base.metadata.create_all`(新規作成のみ)。スキーマ変更が始まる Phase 2 で Alembic を導入する(TASKS.md T-201)。

## 再現性

- `input_hash` = 正規化(キーソート、区切り統一)した inputs_snapshot JSON の SHA-256
- 同一 input_hash の再実行は新しい sizing_run 行を作る(履歴主義。上書きしない)。同一性は input_hash で判定
