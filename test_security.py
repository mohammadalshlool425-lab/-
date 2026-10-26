import base64
import os
import unittest

from security import IAMService, Identity, SessionStore, can, generate_totp_secret, hash_password, totp_code, verify_password, verify_totp


class SecurityPrimitiveTests(unittest.TestCase):
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
