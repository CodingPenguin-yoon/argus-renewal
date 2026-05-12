from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


MODULE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = MODULE_DIR.parents[1]
MIGRATIONS_DIR = MODULE_DIR / "migrations"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_db_path(db_path: str) -> Path:
    path = Path(db_path)
    if path.is_absolute():
        return path
    return BACKEND_DIR / path


def _ensure_migration_tracking_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def run_migrations(connection: sqlite3.Connection) -> None:
    _ensure_migration_tracking_table(connection)

    applied_versions = {
        row["version"]
        for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }

    for migration_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = migration_file.name
        if version in applied_versions:
            continue

        connection.executescript(migration_file.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, utcnow_iso()),
        )

    connection.commit()


@contextmanager
def get_connection(db_path: str) -> Iterator[sqlite3.Connection]:
    resolved_path = resolve_db_path(db_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(resolved_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        run_migrations(connection)
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
