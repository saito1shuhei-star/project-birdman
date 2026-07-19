"""Alembicマイグレーションのスモークテスト(T-201, T-204)。

- `alembic upgrade head` が空のDBに現行スキーマを正しく作成できること
- categoryデータ移行(9706411a806d)が旧enum値を新値へ正しく変換すること
  (実DBで発生した500エラーの回帰テスト。enum変更時はデータ移行を伴うこと)
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

_BACKEND_DIR = Path(__file__).resolve().parents[1]


def _make_config(db_url: str, monkeypatch) -> Config:
    monkeypatch.setenv("PBM_DATABASE_URL", db_url)
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    return cfg


def test_alembic_upgrade_head_creates_expected_tables(tmp_path, monkeypatch):
    db_url = f"sqlite:///{(tmp_path / 'alembic_test.sqlite3').as_posix()}"
    cfg = _make_config(db_url, monkeypatch)

    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    tables = set(inspect(engine).get_table_names())
    assert {
        "projects",
        "requirement_specs",
        "sizing_runs",
        "wing_planforms",
        "analysis_runs",
        "alembic_version",
    } <= tables
    engine.dispose()


def test_category_data_migration_converts_legacy_values(tmp_path, monkeypatch):
    """旧enum値(distance/time_trial)を持つ既存行が新値へ移行される。"""
    db_url = f"sqlite:///{(tmp_path / 'alembic_data_mig.sqlite3').as_posix()}"
    cfg = _make_config(db_url, monkeypatch)

    # データ移行リビジョンの1つ手前まで適用し、旧値の行を挿入する
    command.upgrade(cfg, "aedebbdef4cb")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        for pid, category in (("p1", "distance"), ("p2", "time_trial"), ("p3", "glider")):
            conn.execute(
                text(
                    "INSERT INTO projects (id, team_name, aircraft_name, design_year,"
                    " category, design_lead, unit_system, version, design_goal, status,"
                    " created_at, updated_at) VALUES (:id, 't', 'a', 2026, :cat, 'l',"
                    " 'SI', 'v1', '', 'draft', '2026-01-01T00:00:00+00:00',"
                    " '2026-01-01T00:00:00+00:00')"
                ),
                {"id": pid, "cat": category},
            )
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    with engine.connect() as conn:
        rows = dict(
            conn.execute(text("SELECT id, category FROM projects ORDER BY id")).fetchall()
        )
    engine.dispose()
    assert rows == {
        "p1": "human_powered_propeller",  # distance → 既定部門へ
        "p2": "other",                     # time_trial → 対応なしのためother
        "p3": "glider",                    # 新値はそのまま
    }
