#!/usr/bin/env python3
"""Apply PostgreSQL migrations with an advisory lock and checksum protection."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import os
import re
import sys


MIGRATION_RE = re.compile(r"^(?P<version>[0-9]{4})_(?P<name>[a-z0-9_]+)\.sql$")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIGRATIONS_DIR = ROOT / "db" / "migrations"


def migration_files(directory: Path) -> list[tuple[int, str, Path]]:
    files = []
    for path in directory.iterdir():
        match = MIGRATION_RE.fullmatch(path.name)
        if match:
            files.append((int(match.group("version")), match.group("name"), path))
    files.sort(key=lambda item: item[0])
    versions = [version for version, _, _ in files]
    if len(versions) != len(set(versions)):
        raise RuntimeError("duplicate migration version")
    return files


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply(database_url: str, directory: Path, dry_run: bool = False) -> int:
    files = migration_files(directory)
    if dry_run:
        for version, name, path in files:
            print(f"{version:04d} {name} {checksum(path)}")
        return 0
    if not database_url.startswith(("postgresql://", "postgres://")):
        print("DATABASE_URL must be a PostgreSQL URL", file=sys.stderr)
        return 2
    try:
        import psycopg
    except ImportError:
        print("Install requirements-production.txt before running migrations", file=sys.stderr)
        return 2

    try:
        with psycopg.connect(database_url) as connection:
            connection.execute("SELECT pg_advisory_lock(hashtextextended('ezwatek:migrations', 0))")
            try:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version integer PRIMARY KEY,
                        name text NOT NULL,
                        checksum text NOT NULL,
                        applied_at timestamptz NOT NULL DEFAULT now()
                    )
                """)
                applied = {
                    int(version): (str(name), str(file_checksum))
                    for version, name, file_checksum in connection.execute(
                        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
                    ).fetchall()
                }
                for version, name, path in files:
                    file_checksum = checksum(path)
                    existing = applied.get(version)
                    if existing:
                        if existing != (name, file_checksum):
                            raise RuntimeError(f"migration checksum mismatch: {path.name}")
                        print(f"already applied {path.name}")
                        continue
                    sql = path.read_text(encoding="utf-8")
                    with connection.transaction():
                        connection.execute(sql)
                        connection.execute(
                            "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                            (version, name, file_checksum),
                        )
                    print(f"applied {path.name}")
            finally:
                connection.execute("SELECT pg_advisory_unlock(hashtextextended('ezwatek:migrations', 0))")
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("migration failed; inspect the database transaction logs", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""), help="PostgreSQL URL; prefer DATABASE_URL from a secret manager")
    parser.add_argument("--migrations-dir", type=Path, default=DEFAULT_MIGRATIONS_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.migrations_dir.is_dir():
        print("migration directory does not exist", file=sys.stderr)
        return 2
    return apply(args.database_url, args.migrations_dir, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
