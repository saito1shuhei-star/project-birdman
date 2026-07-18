"""DB接続とセッション管理。

接続先は環境変数 PBM_DATABASE_URL(既定: backend/data/pbm.sqlite3)。
テストは create_engine_and_sessionmaker に一時DBのURLを渡して分離する。
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from pbm.persistence.models import Base

_BACKEND_DIR = Path(__file__).resolve().parents[3]  # …/backend


def default_database_url() -> str:
    db_path = _BACKEND_DIR / "data" / "pbm.sqlite3"
    return f"sqlite:///{db_path.as_posix()}"


def resolve_database_url(explicit: str | None = None) -> str:
    return explicit or os.environ.get("PBM_DATABASE_URL") or default_database_url()


def create_engine_and_sessionmaker(
    database_url: str | None = None,
) -> tuple[Engine, sessionmaker[Session]]:
    url = resolve_database_url(database_url)
    if url.startswith("sqlite:///"):
        db_file = url.removeprefix("sqlite:///")
        if db_file and db_file != ":memory:":
            Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if "sqlite" in url else {}
    engine = create_engine(url, connect_args=connect_args)
    if "sqlite" in url:
        # SQLiteはFK制約が既定で無効のため接続毎に有効化(ON DELETE CASCADEに必要)
        @event.listens_for(engine, "connect")
        def _enable_sqlite_fk(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
