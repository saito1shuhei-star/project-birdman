# Project BirdMan (PBM)

鳥人間コンテスト出場チームのための、人力飛行機設計支援プラットフォーム。
**Design(設計を支援する)/ Knowledge(知識を継承する)/ Simulation(挑戦を後押しする)**

最上位仕様: [PROJECT_BRIEF.md](PROJECT_BRIEF.md) / ロードマップ: [ROADMAP.md](ROADMAP.md) / タスク: [TASKS.md](TASKS.md)

> ⚠️ PBMの計算結果は設計検討のための推定であり、**実機の飛行安全を保証しません**。
> 材料・安全率・製造・飛行試験の判断は必ず人間(チーム)が行ってください。

## 現在の実装状態

Phase 0–4の主要工程が動作します。工程ステッパー+概要ダッシュボードのUIで、
要求仕様 → 初期サイジング → 主翼平面形・空力解析(モック/XFLR5取込)→ 質量・重心 →
静安定 → 主桁の梁解析 → 設計スイープ(パレート)→ 承認・設計レポート、までを一貫して扱えます。
外部ソフト連携はXROTOR実連携(要実行ファイル)とXFLR5手動ハンドオフを実装済み(docs/INTEGRATION_PLAN.md)。

## セットアップ(Windows)

前提: Python 3.12+, Node.js 20+。リポジトリがOneDrive配下の場合、venvはリポジトリ外を推奨(ASSUMPTIONS A-201)。

### バックエンド

```powershell
python -m venv $env:USERPROFILE\.venvs\pbm
& $env:USERPROFILE\.venvs\pbm\Scripts\pip install -e ".\backend[dev]"
& $env:USERPROFILE\.venvs\pbm\Scripts\uvicorn pbm.api.main:app --reload --port 8000
# http://localhost:8000/docs でOpenAPI UI
```

### データベースマイグレーション(Alembic)

```powershell
cd backend
& $env:USERPROFILE\.venvs\pbm\Scripts\alembic upgrade head   # 既存DBを最新スキーマへ
& $env:USERPROFILE\.venvs\pbm\Scripts\alembic revision --autogenerate -m "説明"  # スキーマ変更後に生成
```

`create_engine_and_sessionmaker()`は開発・テスト用に`create_all`も呼ぶため、初回起動は`alembic upgrade head`を省略しても動作するが、Phase 2以降のスキーマ変更はAlembicマイグレーション経由で行うこと(DATA_MODEL.md参照)。

### テスト・lint

```powershell
& $env:USERPROFILE\.venvs\pbm\Scripts\python -m pytest backend/tests -q
& $env:USERPROFILE\.venvs\pbm\Scripts\python -m ruff check backend
```

### フロントエンド

```powershell
cd frontend
npm install
npm run dev
# http://localhost:3000(APIは NEXT_PUBLIC_API_BASE、既定 http://localhost:8000)
```

### Docker(定義のみ・未検証: TASKS T-112)

```bash
docker compose up --build
```

## リポジトリ構成

```
backend/   FastAPI + 計算エンジン(src/pbm/{domain,calculation,workflow,adapters,api,persistence,reports})
frontend/  Next.js + TypeScript
data/samples/  サンプル機体データ
*.md       設計文書(PROJECT_BRIEF.md が最上位)
```

設計文書: [REQUIREMENTS](REQUIREMENTS.md) · [ARCHITECTURE](ARCHITECTURE.md) · [DOMAIN_MODEL](DOMAIN_MODEL.md) ·
[DATA_MODEL](DATA_MODEL.md) · [API_SPEC](API_SPEC.md) · [CALCULATION_SPEC](CALCULATION_SPEC.md) ·
[ASSUMPTIONS](ASSUMPTIONS.md) · [VALIDATION_PLAN](VALIDATION_PLAN.md) · [CHANGELOG](CHANGELOG.md) ·
[大会規則ノート2025](docs/CONTEST_RULES_2025_NOTES.md)

> 📕 大会ルールブック本体は讀賣テレビの著作物のため、**PDFをこのリポジトリにコミットしないこと**
> (要約ノート [docs/CONTEST_RULES_2025_NOTES.md](docs/CONTEST_RULES_2025_NOTES.md) を参照)。

## 開発ルール(抜粋)

- 計算式はUIやAPI層に書かない(`pbm/calculation` のみ)
- 物理量は必ず値+単位(`{"value": 60, "unit": "kg"}`)。内部はSI統一(Pint)
- 係数・仮定は [ASSUMPTIONS.md](ASSUMPTIONS.md) にID付きで記録し、結果に添付する
- モック解析と実解析は execution_mode で機械的に区別する
- 数値回帰テスト(手計算リファレンス)を壊す変更は仕様書改訂とセットでのみ行う
