"""Small PostgreSQL repository for production admin and audit reads.

The HTTP preview does not import or instantiate this adapter. Production starts
it only when DATA_BACKEND=postgres and a real DATABASE_URL is configured.
"""

from __future__ import annotations

import json
import os
from typing import Any


class DataStoreError(RuntimeError):
    """Raised when the production data store is unavailable or invalid."""


class PostgresRepository:
    def __init__(self, database_url: str, min_size: int = 1, max_size: int = 10, pool=None):
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise DataStoreError("DATABASE_URL must be PostgreSQL")
        self._owns_pool = pool is None
        if pool is not None:
            self.pool = pool
            return
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as error:
            raise DataStoreError("Install requirements-production.txt for PostgreSQL") from error
        try:
            self.pool = ConnectionPool(
                conninfo=database_url,
                min_size=min_size,
                max_size=max_size,
                timeout=5,
                open=True,
            )
            self.pool.wait()
        except Exception as error:
            raise DataStoreError("PostgreSQL connection pool could not be opened") from error

    @classmethod
    def from_environment(cls) -> "PostgresRepository":
        database_url = os.environ.get("DATABASE_URL", "").strip()
        if not database_url:
            raise DataStoreError("DATABASE_URL is required")
        try:
            min_size = max(1, int(os.environ.get("DB_POOL_MIN", "1")))
            max_size = max(min_size, int(os.environ.get("DB_POOL_MAX", "10")))
        except ValueError as error:
            raise DataStoreError("DB_POOL_MIN and DB_POOL_MAX must be integers") from error
        return cls(database_url, min_size=min_size, max_size=max_size)

    def close(self) -> None:
        if self._owns_pool:
            self.pool.close()

    def ready(self) -> bool:
        try:
            with self.pool.connection() as connection:
                connection.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def admin_overview(self) -> dict[str, Any]:
        sql = """
            SELECT
                COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE),
                COALESCE(SUM(COALESCE(final_amount_minor, estimated_amount_minor)) FILTER (WHERE created_at >= CURRENT_DATE), 0),
                (SELECT COUNT(*) FROM providers WHERE active = TRUE AND verification_status = 'verified'),
                (SELECT COALESCE(AVG(rating), 0) FROM reviews)
            FROM orders
        """
        row = self._fetchone(sql)
        return {
            "orders_today": int(row[0] or 0),
            "service_volume_jod": int(row[1] or 0) / 100,
            "active_providers": int(row[2] or 0),
            "customer_satisfaction": round(float(row[3] or 0), 2),
        }

    def admin_security(self) -> dict[str, Any]:
        row = self._fetchone("""
            SELECT COUNT(*)
            FROM audit_events
            WHERE outcome IN ('denied', 'failure')
              AND created_at >= now() - interval '24 hours'
        """)
        return {
            "risk_score": None,
            "mfa_coverage": None,
            "blocked_attempts": int(row[0] or 0),
            "critical_vulnerabilities": None,
            "backup_age_minutes": None,
        }

    def recent_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        rows = self._fetchall("""
            SELECT event_id, EXTRACT(EPOCH FROM created_at)::bigint, action,
                   actor_subject, outcome, client_fingerprint, request_id, metadata
            FROM audit_events
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        events = []
        for event_id, timestamp, action, actor, outcome, fingerprint, request_id, metadata in rows:
            events.append({
                "event_id": str(event_id),
                "timestamp": int(timestamp),
                "action": str(action),
                "actor": str(actor) if actor else None,
                "success": outcome == "success",
                "client_fingerprint": str(fingerprint) if fingerprint else None,
                "request_id": str(request_id) if request_id else None,
                "details": metadata if isinstance(metadata, dict) else {},
            })
        return events

    def append_audit(self, event: dict[str, Any]) -> None:
        outcome = "success" if event.get("success") else "failure"
        self._execute(
            """
            INSERT INTO audit_events
                (event_id, actor_subject, action, outcome, client_fingerprint, request_id, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                event.get("event_id"),
                event.get("actor"),
                event.get("action"),
                outcome,
                event.get("client_fingerprint"),
                event.get("request_id"),
                json.dumps(event.get("details") or {}, ensure_ascii=False, separators=(",", ":")),
            ),
        )

    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()):
        try:
            with self.pool.connection() as connection:
                return connection.execute(sql, params).fetchone()
        except Exception as error:
            raise DataStoreError("PostgreSQL query failed") from error

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()):
        try:
            with self.pool.connection() as connection:
                return connection.execute(sql, params).fetchall()
        except Exception as error:
            raise DataStoreError("PostgreSQL query failed") from error

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        try:
            with self.pool.connection() as connection:
                connection.execute(sql, params)
        except Exception as error:
            raise DataStoreError("PostgreSQL write failed") from error
