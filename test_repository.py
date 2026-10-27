import unittest
from datetime import datetime, timezone

from repository import PostgresRepository


class FakeResult:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class FakeConnection:
    def __init__(self, schema_ready=True):
        self.queries = []
        self.schema_ready = schema_ready

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def transaction(self):
        return self

    def execute(self, sql, params=()):
        self.queries.append((sql, params))
        if 'to_regclass' in sql:
            return FakeResult(
                ('services', 'orders', 'audit_events', True)
                if self.schema_ready
                else (None, 'orders', 'audit_events', False)
            )
        if 'INSERT INTO app_users' in sql:
            return FakeResult(('customer-1',))
        if 'SELECT id, minimum_amount_minor' in sql:
            return FakeResult(('service-1', 1000, 'JOD'))
        if 'INSERT INTO orders' in sql:
            start = datetime(2026, 10, 27, 10, tzinfo=timezone.utc)
            end = datetime(2026, 10, 27, 11, tzinfo=timezone.utc)
            return FakeResult(('order-1', 'EZW-ABC123', 'service-1', 'requested', 'amman', 1500, 'JOD', start, end))
        if 'WHERE customer_id' in sql and 'idempotency_key' in sql:
            return FakeResult(None)
        if 'FROM providers AS p' in sql:
            return FakeResult(many=[('provider-1', 'الفني الماهر', 'amman', 4.8, 'cleaning', 'تنظيف وتعقيم')])
        if 'FROM services' in sql:
            return FakeResult(many=[('service-1', 'cleaning', 'تنظيف وتعقيم', 'Cleaning', 1200, 'JOD', 'home', 'المنزل')])
        if 'FROM orders' in sql:
            return FakeResult((12, 3450, 7, 4.75))
        if 'FROM audit_events' in sql and 'COUNT' in sql:
            return FakeResult((3,))
        if 'FROM audit_events' in sql:
            return FakeResult(many=[('event-1', 1700000000, 'auth.login', 'admin', 'success', 'fingerprint', 'request-1', {'reason': 'ok'})])
        return FakeResult((1,))


class FakePool:
    def __init__(self, schema_ready=True):
        self.connection_instance = FakeConnection(schema_ready=schema_ready)

    def connection(self):
        return self.connection_instance

    def close(self):
        pass


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.pool = FakePool()
        self.repository = PostgresRepository('postgresql://runtime@localhost/db', pool=self.pool)

    def test_readiness_requires_core_schema_and_required_columns(self):
        self.assertTrue(self.repository.ready())
        readiness_sql, _ = self.pool.connection_instance.queries[0]
        self.assertIn('information_schema.columns', readiness_sql)
        self.assertIn("'request_fingerprint'", readiness_sql)
        incomplete = PostgresRepository('postgresql://runtime@localhost/db', pool=FakePool(schema_ready=False))
        self.assertFalse(incomplete.ready())

    def test_services_are_read_from_database_rows(self):
        services = self.repository.list_services()
        self.assertEqual(services[0]['slug'], 'cleaning')
        self.assertEqual(services[0]['minimum_amount_minor'], 1200)

    def test_verified_providers_are_filtered_by_service_and_city(self):
        providers = self.repository.list_providers('cleaning', 'amman')
        self.assertEqual(providers[0]['business_name'], 'الفني الماهر')
        self.assertEqual(providers[0]['rating'], 4.8)
        sql, params = self.pool.connection_instance.queries[-1]
        self.assertIn("verification_status = 'verified'", sql)
        self.assertEqual(params, ('cleaning', 'amman', 12))

    def test_order_creation_is_atomic_and_returns_public_code(self):
        start = datetime(2026, 10, 27, 10, tzinfo=timezone.utc)
        end = datetime(2026, 10, 27, 11, tzinfo=timezone.utc)
        order, replayed = self.repository.create_order(
            external_subject='oidc-subject-1',
            service_slug='cleaning',
            city='amman',
            address_ciphertext=b'encrypted',
            address_nonce=b'012345678901',
            address_key_version=1,
            request_fingerprint=b'fingerprint-12345678901234567890',
            estimated_amount_minor=1500,
            scheduled_from=start,
            scheduled_to=end,
            idempotency_key='request-key-123456',
        )
        self.assertFalse(replayed)
        self.assertEqual(order['public_code'], 'EZW-ABC123')
        self.assertEqual(order['currency'], 'JOD')
        self.assertTrue(any('INSERT INTO order_events' in sql for sql, _ in self.pool.connection_instance.queries))
        order_sql, order_params = next((sql, params) for sql, params in self.pool.connection_instance.queries if 'INSERT INTO orders' in sql)
        self.assertIn('ON CONFLICT (customer_id, idempotency_key) DO NOTHING', order_sql)
        self.assertIn('request_fingerprint', order_sql)
        self.assertEqual(order_sql.count('%s'), len(order_params))

    def test_admin_overview_is_read_from_database_row(self):
        self.assertEqual(self.repository.admin_overview(), {
            'orders_today': 12,
            'service_volume_jod': 34.5,
            'active_providers': 7,
            'customer_satisfaction': 4.75,
        })

    def test_security_and_audit_reads_are_database_backed(self):
        self.assertEqual(self.repository.admin_security()['blocked_attempts'], 3)
        events = self.repository.recent_audit()
        self.assertEqual(events[0]['action'], 'auth.login')
        self.assertEqual(events[0]['request_id'], 'request-1')
        self.assertEqual(events[0]['details'], {'reason': 'ok'})

    def test_audit_write_uses_parameterized_query(self):
        self.repository.append_audit({
            'event_id': 'event-2',
            'actor': 'admin',
            'action': 'admin.access',
            'success': False,
            'client_fingerprint': 'fingerprint',
            'details': {'resource': '/api/admin/audit'},
        })
        sql, params = self.pool.connection_instance.queries[-1]
        self.assertIn('INSERT INTO audit_events', sql)
        self.assertEqual(params[1], 'admin')
        self.assertNotIn('admin.access', sql)


if __name__ == '__main__':
    unittest.main(verbosity=2)
