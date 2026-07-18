# ARCHITECTURE — システムアーキテクチャ

## 1. 全体構成(モノレポ)

```
codex/                          # リポジトリルート
├── PROJECT_BRIEF.md ほか設計文書(§14必須ドキュメント)
├── backend/                    # Python バックエンド
│   ├── pyproject.toml
│   ├── src/pbm/
│   │   ├── domain/             # 設計対象と物理量(依存: pint, pydanticのみ)
│   │   ├── calculation/        # 計算式と数値計算(純粋関数。I/O・DB・API非依存)
│   │   ├── workflow/           # 設計工程の状態遷移
│   │   ├── adapters/           # 外部ソフト抽象化(XFLR5/XROTOR/CAD, Phase2+)
│   │   ├── api/                # FastAPI(HTTP境界のみ。計算式を書かない)
│   │   ├── persistence/        # SQLAlchemy + SQLite(将来PostgreSQL)
│   │   └── reports/            # HTMLレポート生成(Jinja2)
│   ├── tests/                  # pytest(単体・統合・数値回帰)
│   └── data/                   # SQLiteファイル等(gitignore)
├── frontend/                   # Next.js + TypeScript
│   ├── app/                    # App Router(一覧・作成・要求入力・結果表示)
│   └── lib/api.ts              # APIクライアント(型付き)
├── data/samples/               # サンプル機体データ
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## 2. 依存方向(内側ほど安定)

```
frontend ──HTTP──▶ api ──▶ workflow ──▶ calculation ──▶ domain
                   │           │
                   ▼           ▼
              persistence   adapters ──▶ 外部ソフト(XFLR5/XROTOR/Fusion360)
                   │
                   ▼
                reports(domainの結果モデルのみ参照)
```

**規則**

- `domain` は他のPBMモジュールに依存しない。物理量(Quantity)、エンティティ、結果モデル、状態を定義
- `calculation` は `domain` のみに依存する純粋関数群。DB・HTTP・ファイルI/Oを行わない
- `api` に計算式を書かない。`api` は検証済み入力を `workflow`/`calculation` へ渡すだけ
- 外部ソフトは必ず `adapters` の共通インターフェース経由。アダプター失敗は結果status/ログに記録し、システム全体を停止させない
- `frontend` に物理計算式を書かない。表示・入力・呼び出しのみ

## 3. 共通インターフェース(adapters/base.py)

```python
class ExecutionMode(StrEnum): real | mock | imported | analytical_estimate
class ResultStatus(StrEnum): ok | failed | partial

class SolverExecution(BaseModel):     # すべての解析・計算実行に付与
    solver_name, solver_version, execution_mode, input_hash,
    started_at, finished_at, exit_code, stdout, stderr,
    raw_output_path, parser_version, result_status

class SolverAdapter(ABC):             # 共通基底
    name / version / is_available() / run(request) -> SolverResult

class AerodynamicSolverAdapter(SolverAdapter): ...   # XFLR5(Phase 2)
class PropellerSolverAdapter(SolverAdapter): ...     # XROTOR(Phase 2)
class CADAdapter(ABC): ...                            # Fusion 360等(Phase 5)
class ReportExporter(ABC): export(result) -> Path     # HTML(Phase 1)/PDF/CSV(Phase 5)
```

Phase 1 の初期サイジングも `SolverExecution`(execution_mode=analytical_estimate)を付与し、
Phase 2 以降の実解析と同じ追跡形式で保存する。**モックと実解析はこのフィールドで機械的に区別される。**

## 4. 単位管理

- 内部標準はSI。`pbm.domain.quantities.Quantity`(value+unit の Pydantic モデル)が唯一の物理量表現
- 単位変換・次元検証は Pint。API境界で `expected_dimension` に対し検証し、SIへ正規化
- 計算関数はSI正規化済み Quantity のみを受け取る。素の float の物理量受け渡しは禁止(無次元係数を除く)
- NaN/±inf は Quantity 構築時に拒否

## 5. トレーサビリティ

SizingRun(および将来のAnalysisRun)は以下を保存する:

- requirement_spec_id + revision(入力の出所)
- 入力スナップショット(値+単位のJSON)と input_hash(正規化JSONのSHA-256)
- 使用した式(FormulaRecord: 記号、式、代入値、結果、出典)
- 仮定(AssumptionRecord: 値、根拠、ASSUMPTIONS.md のID)
- 警告(code, severity, message)
- SolverExecution(§3)と pbm バージョン

同一 input_hash + 同一 pbm バージョン ⇒ 同一結果(数値回帰テストで担保)。

## 6. 状態遷移(workflow/states.py)

```
draft ──▶ calculated ──▶ analyzed ──▶ review_required ──▶ approved
  ▲            │              │               │              │
  └────────────┴──────────────┴───────────────┼──▶ rejected  │
        (入力変更で draft へ戻る)              └──────────────┴──▶ superseded
```

- 遷移は `ALLOWED_TRANSITIONS` 表で定義し、不正遷移は例外
- `approved` 以外から製造用データ生成を要求された場合はエラー(FR-004)
- 承認操作は必ず承認者名を要求する(Phase 3 でUI実装、モデルはPhase 1から)

## 7. 技術選定と理由

| 選定 | 理由 |
|---|---|
| SQLAlchemy 2.0 + SQLite | SQLite→PostgreSQL移行パスを確保。スキーマはJSON列を併用し初期の変更コストを低減 |
| Pint | 事実上標準の単位ライブラリ。次元検証・変換を自前実装しない(NFR-001) |
| Jinja2 | HTMLレポートのテンプレート分離。将来PDF(WeasyPrint等)の土台 |
| ruff | lint+format統合。設定が単純 |
| uvicorn | FastAPI標準ASGIサーバ |
| Next.js App Router | PROJECT_BRIEF指定。SSR不要のためclient components中心の薄い構成 |

## 8. 設定(環境変数)

| 変数 | 既定値 | 用途 |
|---|---|---|
| PBM_DATABASE_URL | sqlite:///./data/pbm.sqlite3 | DB接続 |
| PBM_XFLR5_PATH | (未設定) | XFLR5実行パス(Phase 2)。未設定時はmockのみ |
| PBM_XROTOR_PATH | (未設定) | XROTOR実行パス(Phase 2) |
| PBM_REPORT_DIR | ./data/reports | レポート出力先 |
| NEXT_PUBLIC_API_BASE | http://localhost:8000 | フロントエンドのAPI接続先 |

## 9. エラー処理方針

- ドメイン例外(UnitDimensionError, NonPhysicalValueError, InvalidTransitionError, CalculationError)を定義し、APIで4xx/422へマップ
- 想定外例外は500 + ログ。エラーをcatchして無視しない(NFR-010)
- 計算は「拒否(例外)」と「警告付き成功」を区別する。範囲外だが計算可能 → 警告、非物理(負質量等)→ 拒否
