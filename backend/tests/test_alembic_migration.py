"""Alembicマイグレーションのスモークテスト(T-201)。

`alembic upgrade head` が空のDBに対して現行スキーマ(projects/requirement_specs/
sizing_runs)を正しく作成できることを確認する。DATA_MODEL.md参照。
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

_BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_alembic_upgrade_head_creates_expected_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "alembic_test.sqlite3"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("PBM_DATABASE_URL", db_url)

    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))

    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    tables = set(inspect(engine).get_table_names())
    assert {"projects", "requirement_specs", "sizing_runs", "alembic_version"} <= tables
    engine.dispose()
