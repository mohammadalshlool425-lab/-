import unittest

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
    def __init__(self):
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=()):
        self.queries.append((sql, params))
        if 'FROM orders' in sql:
            return FakeResult((12, 3450, 7, 4.75))
        if 'FROM audit_events' in sql and 'COUNT' in sql:
            return FakeResult((3,))
        if 'FROM audit_events' in sql:
            return FakeResult(many=[('event-1', 1700000000, 'auth.login', 'admin', 'success', 'fingerprint', {'reason': 'ok'})])
        return FakeResult((1,))


class FakePool:
    def __init__(self):
        self.connection_instance = FakeConnection()

    def connection(self):
        return self.connection_instance

    def close(self):
        pass


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.pool = FakePool()
        self.repository = PostgresRepository('postgresql://runtime@localhost/db', pool=self.pool)

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
