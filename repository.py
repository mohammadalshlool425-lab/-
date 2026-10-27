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


class OrderInputError(ValueError):
    """Raised when a service or order field cannot be accepted."""


class IdempotencyConflict(ValueError):
    """Raised when a key is reused with a different order payload."""


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
        """Confirm connectivity and the core schema required by the API."""
        try:
            with self.pool.connection() as connection:
                row = connection.execute("""
                    SELECT to_regclass('public.services'),
                           to_regclass('public.orders'),
                           to_regclass('public.audit_events'),
                           NOT EXISTS (
                               SELECT 1
                               FROM (VALUES
                                   ('app_users', 'id'),
                                   ('app_users', 'external_subject'),
                                   ('service_categories', 'id'),
                                   ('service_categories', 'slug'),
                                   ('service_categories', 'name_ar'),
                                   ('service_categories', 'active'),
                                   ('services', 'id'),
                                   ('services', 'category_id'),
                                   ('services', 'slug'),
                                   ('services', 'name_ar'),
                                   ('services', 'name_en'),
                                   ('services', 'minimum_amount_minor'),
                                   ('services', 'currency'),
                                   ('services', 'active'),
                                   ('providers', 'id'),
                                   ('providers', 'business_name'),
                                   ('providers', 'city'),
                                   ('providers', 'verification_status'),
                                   ('providers', 'rating'),
                                   ('providers', 'active'),
                                   ('providers', 'created_at'),
                                   ('provider_services', 'provider_id'),
                                   ('provider_services', 'service_id'),
                                   ('orders', 'id'),
                                   ('orders', 'public_code'),
                                   ('orders', 'customer_id'),
                                   ('orders', 'service_id'),
                                   ('orders', 'status'),
                                   ('orders', 'city'),
                                   ('orders', 'address_ciphertext'),
                                   ('orders', 'address_nonce'),
                                   ('orders', 'address_key_version'),
                                   ('orders', 'request_fingerprint'),
                                   ('orders', 'estimated_amount_minor'),
                                   ('orders', 'final_amount_minor'),
                                   ('orders', 'currency'),
                                   ('orders', 'scheduled_from'),
                                   ('orders', 'scheduled_to'),
                                   ('orders', 'idempotency_key'),
                                   ('orders', 'created_at'),
                                   ('order_events', 'order_id'),
                                   ('order_events', 'event_type'),
                                   ('order_events', 'actor_subject'),
                                   ('order_events', 'payload'),
                                   ('payments', 'order_id'),
                                   ('payments', 'status'),
                                   ('reviews', 'order_id'),
                                   ('reviews', 'rating'),
                                   ('audit_events', 'event_id'),
                                   ('audit_events', 'actor_subject'),
                                   ('audit_events', 'action'),
                                   ('audit_events', 'outcome'),
                                   ('audit_events', 'client_fingerprint'),
                                   ('audit_events', 'request_id'),
                                   ('audit_events', 'metadata'),
                                   ('audit_events', 'created_at')
                               ) AS required(table_name, column_name)
                               WHERE NOT EXISTS (
                                   SELECT 1
                                   FROM information_schema.columns AS columns
                                   WHERE columns.table_schema = 'public'
                                     AND columns.table_name = required.table_name
                                     AND columns.column_name = required.column_name
                               )
                           ) AS schema_contract_ready
                """).fetchone()
            return bool(row and all(row))
        except Exception:
            return False

    def list_services(self) -> list[dict[str, Any]]:
        rows = self._fetchall("""
            SELECT s.id::text, s.slug, s.name_ar, s.name_en,
                   s.minimum_amount_minor, s.currency,
                   c.slug, c.name_ar
            FROM services AS s
            JOIN service_categories AS c ON c.id = s.category_id
            WHERE s.active = TRUE AND c.active = TRUE
            ORDER BY c.slug, s.name_ar
        """)
        return [
            {
                "id": str(row[0]),
                "slug": str(row[1]),
                "name_ar": str(row[2]),
                "name_en": str(row[3]) if row[3] else None,
                "minimum_amount_minor": int(row[4]),
                "currency": str(row[5]),
                "category_slug": str(row[6]),
                "category_name_ar": str(row[7]),
            }
            for row in rows
        ]

    def list_providers(self, service_slug: str, city: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
        if not service_slug:
            raise OrderInputError("service_required")
        limit = max(1, min(int(limit), 50))
        rows = self._fetchall(
            """
            SELECT p.id::text, p.business_name, p.city, p.rating,
                   s.slug, s.name_ar
            FROM providers AS p
            JOIN provider_services AS ps ON ps.provider_id = p.id
            JOIN services AS s ON s.id = ps.service_id
            WHERE p.active = TRUE
              AND p.verification_status = 'verified'
              AND s.active = TRUE
              AND s.slug = %s
              AND p.city = COALESCE(%s, p.city)
            ORDER BY p.rating DESC NULLS LAST, p.created_at ASC
            LIMIT %s
            """,
            (service_slug, city, limit),
        )
        return [
            {
                'id': str(row[0]),
                'business_name': str(row[1]),
                'city': str(row[2]),
                'rating': float(row[3]) if row[3] is not None else None,
                'service_slug': str(row[4]),
                'service_name_ar': str(row[5]),
            }
            for row in rows
        ]

    def create_order(
        self,
        *,
        external_subject: str,
        service_slug: str,
        city: str,
        address_ciphertext: bytes,
        address_nonce: bytes,
        address_key_version: int,
        request_fingerprint: bytes,
        estimated_amount_minor: int,
        scheduled_from,
        scheduled_to,
        idempotency_key: str,
        display_name: str | None = None,
        phone_e164: str | None = None,
        actor_subject: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Create one order and its first event atomically, or return an idempotent replay."""
        if not external_subject or not service_slug or not city or not idempotency_key:
            raise OrderInputError("required_order_field")
        if not isinstance(address_ciphertext, bytes) or not isinstance(address_nonce, bytes):
            raise OrderInputError("encrypted_address_required")
        if not isinstance(request_fingerprint, bytes) or len(request_fingerprint) != 32:
            raise OrderInputError("request_fingerprint_required")
        try:
            estimated_amount_minor = int(estimated_amount_minor)
            address_key_version = int(address_key_version)
        except (TypeError, ValueError) as error:
            raise OrderInputError("invalid_order_amount") from error
        if estimated_amount_minor < 0 or address_key_version < 1:
            raise OrderInputError("invalid_order_value")

        try:
            with self.pool.connection() as connection:
                with connection.transaction():
                    customer_row = connection.execute(
                        """
                        INSERT INTO app_users (external_subject, phone_e164, display_name)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (external_subject) DO UPDATE
                          SET phone_e164 = COALESCE(EXCLUDED.phone_e164, app_users.phone_e164),
                              display_name = COALESCE(EXCLUDED.display_name, app_users.display_name),
                              updated_at = now()
                        RETURNING id
                        """,
                        (external_subject, phone_e164, display_name),
                    ).fetchone()
                    if not customer_row:
                        raise OrderInputError("customer_unavailable")
                    customer_id = customer_row[0]

                    service_row = connection.execute(
                        """
                        SELECT id, minimum_amount_minor, currency
                        FROM services
                        WHERE slug = %s AND active = TRUE
                        """,
                        (service_slug,),
                    ).fetchone()
                    if not service_row:
                        raise OrderInputError("service_not_found")
                    service_id, minimum_amount_minor, currency = service_row
                    if estimated_amount_minor < int(minimum_amount_minor):
                        raise OrderInputError("amount_below_service_minimum")

                    existing = connection.execute(
                        """
                        SELECT id::text, public_code, service_id, status, city,
                               estimated_amount_minor, currency, scheduled_from, scheduled_to,
                               request_fingerprint
                        FROM orders
                        WHERE customer_id = %s AND idempotency_key = %s
                        FOR UPDATE
                        """,
                        (customer_id, idempotency_key),
                    ).fetchone()
                    if existing:
                        self._validate_replay(existing, service_id, city, estimated_amount_minor, currency, scheduled_from, scheduled_to, request_fingerprint)
                        return self._order_payload(existing), True

                    order = connection.execute(
                        """
                        INSERT INTO orders (
                            public_code, customer_id, service_id, status, city,
                            address_ciphertext, address_nonce, address_key_version, request_fingerprint,
                            estimated_amount_minor, currency, scheduled_from,
                            scheduled_to, idempotency_key
                        )
                        VALUES (
                            'EZW-' || upper(encode(gen_random_bytes(5), 'hex')),
                            %s, %s, 'requested', %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s
                        )
                        ON CONFLICT (customer_id, idempotency_key) DO NOTHING
                        RETURNING id::text, public_code, service_id, status, city,
                                  estimated_amount_minor, currency, scheduled_from, scheduled_to
                        """,
                        (
                            customer_id,
                            service_id,
                            city,
                            address_ciphertext,
                            address_nonce,
                            address_key_version,
                            request_fingerprint,
                            estimated_amount_minor,
                            currency,
                            scheduled_from,
                            scheduled_to,
                            idempotency_key,
                        ),
                    ).fetchone()
                    if not order:
                        replay = connection.execute(
                            """
                            SELECT id::text, public_code, service_id, status, city,
                                   estimated_amount_minor, currency, scheduled_from, scheduled_to,
                                   request_fingerprint
                            FROM orders
                            WHERE customer_id = %s AND idempotency_key = %s
                            FOR UPDATE
                            """,
                            (customer_id, idempotency_key),
                        ).fetchone()
                        if not replay:
                            raise OrderInputError("order_not_created")
                        self._validate_replay(replay, service_id, city, estimated_amount_minor, currency, scheduled_from, scheduled_to, request_fingerprint)
                        return self._order_payload(replay), True
                    connection.execute(
                        """
                        INSERT INTO order_events (order_id, event_type, actor_subject, payload)
                        VALUES (%s, 'order.requested', %s, %s::jsonb)
                        """,
                        (order[0], actor_subject or external_subject, json.dumps({'source': 'customer_api'}, separators=(",", ":"))),
                    )
                    return self._order_payload(order), False
        except (OrderInputError, IdempotencyConflict):
            raise
        except Exception as error:
            raise DataStoreError("PostgreSQL order write failed") from error

    @staticmethod
    def _validate_replay(existing, service_id, city, estimated_amount_minor, currency, scheduled_from, scheduled_to, request_fingerprint) -> None:
        if (
            str(existing[2]) != str(service_id)
            or str(existing[4]) != city
            or int(existing[5]) != estimated_amount_minor
            or existing[6] != currency
            or existing[7] != scheduled_from
            or existing[8] != scheduled_to
            or bytes(existing[9] or b'') != request_fingerprint
        ):
            raise IdempotencyConflict("idempotency_key_reused")

    @staticmethod
    def _order_payload(row) -> dict[str, Any]:
        scheduled_from = row[7].isoformat() if hasattr(row[7], 'isoformat') else str(row[7])
        scheduled_to = row[8].isoformat() if hasattr(row[8], 'isoformat') else str(row[8])
        return {
            'id': str(row[0]),
            'public_code': str(row[1]),
            'status': str(row[3]),
            'city': str(row[4]),
            'estimated_amount_minor': int(row[5]),
            'currency': str(row[6]),
            'scheduled_from': scheduled_from,
            'scheduled_to': scheduled_to,
        }

    def customer_orders(self, external_subject: str, limit: int = 50) -> list[dict[str, Any]]:
        if not external_subject:
            raise OrderInputError("customer_required")
        limit = max(1, min(int(limit), 100))
        rows = self._fetchall(
            """
            SELECT o.id::text, o.public_code, s.slug, s.name_ar, o.status,
                   o.city, o.estimated_amount_minor, o.currency,
                   o.scheduled_from, o.scheduled_to, o.created_at
            FROM orders AS o
            JOIN app_users AS u ON u.id = o.customer_id
            JOIN services AS s ON s.id = o.service_id
            WHERE u.external_subject = %s
            ORDER BY o.created_at DESC
            LIMIT %s
            """,
            (external_subject, limit),
        )
        return [
            {
                'id': str(row[0]),
                'public_code': str(row[1]),
                'service_slug': str(row[2]),
                'service_name_ar': str(row[3]),
                'status': str(row[4]),
                'city': str(row[5]),
                'estimated_amount_minor': int(row[6]),
                'currency': str(row[7]),
                'scheduled_from': row[8].isoformat() if hasattr(row[8], 'isoformat') else str(row[8]),
                'scheduled_to': row[9].isoformat() if hasattr(row[9], 'isoformat') else str(row[9]),
                'created_at': row[10].isoformat() if hasattr(row[10], 'isoformat') else str(row[10]),
            }
            for row in rows
        ]

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
