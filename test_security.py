import base64
import os
import unittest

from security import AuditLog, IAMService, Identity, RedisSessionStore, SessionStore, can, generate_totp_secret, hash_password, totp_code, verify_password, verify_totp


class FakeRedis:
    def __init__(self):
        self.values = {}

    def setex(self, key, ttl, value):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        self.values.pop(key, None)


class SecurityPrimitiveTests(unittest.TestCase):
    def test_redis_sessions_round_trip_and_revoke(self):
        store = RedisSessionStore(client=FakeRedis(), ttl_seconds=60)
        identity = Identity('owner', ('owner',))
        session = store.create(identity, now=100)
        restored = store.get(session.token, now=101)
        self.assertEqual(restored.identity.username, 'owner')
        self.assertEqual(restored.csrf_token, session.csrf_token)
        store.revoke(session.token)
        self.assertIsNone(store.get(session.token, now=101))

    def test_audit_log_redacts_client_identity_and_bounds_details(self):
        audit = AuditLog(max_events=2)
        audit.record('test.event', actor='admin', client_ip='10.0.0.1')
        audit.record('test.event.second', client_ip='10.0.0.2', details={'secret': 'a\\nb' * 100})
        audit.record('test.event.third', client_ip='10.0.0.3')
        events = audit.recent()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['action'], 'test.event.third')
        self.assertNotIn('10.0.0.3', str(events[0]))
        self.assertLessEqual(len(events[1]['details']['secret']), 160)
        self.assertNotIn('\\n', events[1]['details']['secret'])

    def test_scrypt_password_records_are_salted_and_verifiable(self):
        first = hash_password('correct horse battery staple')
        second = hash_password('correct horse battery staple')
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password('correct horse battery staple', first))
        self.assertFalse(verify_password('wrong password', first))
        self.assertFalse(verify_password('correct horse battery staple', 'invalid-record'))

    def test_totp_matches_rfc6238_sha1_vector(self):
        secret = base64.b32encode(b'12345678901234567890').decode().rstrip('=')
        self.assertEqual(totp_code(secret, timestamp=59), '287082')
        self.assertTrue(verify_totp(secret, '287082', timestamp=59, window=0))
        self.assertFalse(verify_totp(secret, '287083', timestamp=59, window=0))

    def test_totp_secrets_are_random(self):
        self.assertNotEqual(generate_totp_secret(), generate_totp_secret())

    def test_unknown_session_store_fails_closed(self):
        original = os.environ.get('SESSION_STORE')
        try:
            os.environ['SESSION_STORE'] = 'unknown'
            with self.assertRaises(RuntimeError):
                IAMService()
        finally:
            if original is None:
                os.environ.pop('SESSION_STORE', None)
            else:
                os.environ['SESSION_STORE'] = original

    def test_invalid_role_configuration_fails_closed(self):
        secret = generate_totp_secret()
        original = {key: os.environ.get(key) for key in ('IAM_ADMIN_USERNAME', 'IAM_ADMIN_PASSWORD_HASH', 'IAM_MFA_TOTP_SECRET', 'IAM_ADMIN_ROLES')}
        try:
            os.environ['IAM_ADMIN_USERNAME'] = 'admin'
            os.environ['IAM_ADMIN_PASSWORD_HASH'] = hash_password('correct horse battery staple')
            os.environ['IAM_MFA_TOTP_SECRET'] = secret
            os.environ['IAM_ADMIN_ROLES'] = 'not-a-real-role'
            session, reason = IAMService().login('admin', 'correct horse battery staple', totp_code(secret), 'invalid-role-client')
            self.assertIsNone(session)
            self.assertEqual(reason, 'invalid_credentials')
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_rbac_is_permission_based(self):
        owner = Identity('owner', ('owner',))
        auditor = Identity('auditor', ('security_auditor',))
        self.assertTrue(can(owner, 'providers:approve'))
        self.assertFalse(can(auditor, 'providers:approve'))
        self.assertTrue(can(auditor, 'security:read'))

    def test_iam_login_requires_password_and_totp(self):
        secret = generate_totp_secret()
        original = {key: os.environ.get(key) for key in ('IAM_ADMIN_USERNAME', 'IAM_ADMIN_PASSWORD_HASH', 'IAM_MFA_TOTP_SECRET', 'IAM_ADMIN_ROLES')}
        try:
            os.environ['IAM_ADMIN_USERNAME'] = 'admin'
            os.environ['IAM_ADMIN_PASSWORD_HASH'] = hash_password('correct horse battery staple')
            os.environ['IAM_MFA_TOTP_SECRET'] = secret
            os.environ['IAM_ADMIN_ROLES'] = 'owner'
            service = IAMService()
            session, reason = service.login('admin', 'correct horse battery staple', totp_code(secret), 'test-client')
            self.assertEqual(reason, 'ok')
            self.assertIsNotNone(session)
            self.assertTrue(can(session.identity, 'security:read'))
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_sessions_expire_and_cookie_has_secure_attributes(self):
        store = SessionStore(ttl_seconds=60)
        identity = Identity('owner', ('owner',))
        session = store.create(identity, now=100)
        secure_cookie = IAMService.session_cookie(session, secure=True)
        self.assertIn('HttpOnly', secure_cookie)
        self.assertIn('Secure', secure_cookie)
        self.assertIn('SameSite=Strict', secure_cookie)
        self.assertIs(store.get(session.token, now=101), session)
        self.assertIsNone(store.get(session.token, now=161))


if __name__ == '__main__':
    unittest.main(verbosity=2)
