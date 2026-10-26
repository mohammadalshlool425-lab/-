from pathlib import Path
import unittest


MIGRATIONS = Path(__file__).parent / 'db' / 'migrations'
SCHEMA = MIGRATIONS / '0001_initial.sql'
CATALOG = MIGRATIONS / '0002_seed_service_catalog.sql'


class SchemaSafetyTests(unittest.TestCase):
    def test_initial_schema_exists_without_destructive_operations(self):
        sql = SCHEMA.read_text(encoding='utf-8')
        self.assertTrue(sql.startswith('-- عزوتك'))
        self.assertNotIn('DROP TABLE', sql.upper())
        self.assertNotIn('COMMIT;', sql)

    def test_catalog_seed_is_public_and_idempotent(self):
        sql = CATALOG.read_text(encoding='utf-8')
        self.assertIn("'JOD'", sql)
        self.assertIn("ON CONFLICT (slug) DO UPDATE", sql)
        self.assertIn('cleaning', sql)
        self.assertNotIn('INSERT INTO app_users', sql)
        self.assertNotIn('INSERT INTO orders', sql)
        self.assertNotIn('INSERT INTO payments', sql)
        self.assertNotIn('COMMIT;', sql)

    def test_schema_contains_core_entities_and_safety_constraints(self):
        sql = SCHEMA.read_text(encoding='utf-8')
        for table in ('app_users', 'providers', 'orders', 'order_events', 'payments', 'reviews', 'audit_events'):
            self.assertIn(f'CREATE TABLE IF NOT EXISTS {table}', sql)
        self.assertIn('UNIQUE (customer_id, idempotency_key)', sql)
        self.assertIn("CHECK (currency = 'JOD')", sql)
        self.assertIn('address_ciphertext', sql)
        self.assertIn('REVOKE UPDATE, DELETE ON audit_events FROM PUBLIC', sql)


if __name__ == '__main__':
    unittest.main(verbosity=2)
