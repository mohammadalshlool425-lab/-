import unittest

from config import validate_production_env


class ProductionConfigTests(unittest.TestCase):
    def test_development_does_not_require_external_services(self):
        self.assertEqual(validate_production_env({'APP_ENV': 'development'}), [])

    def test_production_fails_closed_without_oidc_and_external_stores(self):
        issues = validate_production_env({'APP_ENV': 'production', 'ENABLE_HSTS': '1'})
        self.assertIn('IAM_MODE must be oidc in production; local IAM is not an accepted production identity provider', issues)
        self.assertIn('SESSION_STORE must be redis in production', issues)
        self.assertIn('DATABASE_URL must target a non-placeholder PostgreSQL endpoint in production', issues)

    def test_valid_production_configuration_passes_without_exposing_values(self):
        env = {
            'APP_ENV': 'production',
            'ENABLE_HSTS': '1',
            'IAM_MODE': 'oidc',
            'PUBLIC_ORIGIN': 'https://app.azwatek.jo',
            'OIDC_ISSUER_URL': 'https://identity.azwatek.jo/realms/azwatek',
            'OIDC_CLIENT_ID': 'azwatek-web',
            'OIDC_ROLE_MAP': 'customer=ezwatek-customer,owner=ezwatek-owner,ops_manager=ezwatek-ops,security_auditor=ezwatek-security,support_lead=ezwatek-support',
            'OIDC_REQUIRED_AMR': 'webauthn,fido2,otp',
            'OIDC_REDIRECT_URI': 'https://app.azwatek.jo/auth/callback',
            'SESSION_STORE': 'redis',
            'RATE_LIMIT_STORE': 'redis',
            'REDIS_URL': 'rediss://redis.internal:6380/0',
            'DATA_BACKEND': 'postgres',
            'DATABASE_URL': 'postgresql://runtime:secret@postgres.internal:5432/azwatek?sslmode=verify-full',
            'WAF_MODE': 'managed',
            'ORDER_ADDRESS_ENCRYPTION_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
        }
        self.assertEqual(validate_production_env(env), [])

    def test_production_requires_a_valid_address_encryption_key(self):
        issues = validate_production_env({
            'APP_ENV': 'production',
            'ENABLE_HSTS': '1',
            'IAM_MODE': 'oidc',
            'PUBLIC_ORIGIN': 'https://app.azwatek.jo',
            'OIDC_ISSUER_URL': 'https://identity.azwatek.jo/realms/azwatek',
            'OIDC_CLIENT_ID': 'azwatek-web',
            'OIDC_REQUIRED_AMR': 'webauthn,fido2,otp',
            'OIDC_REDIRECT_URI': 'https://app.azwatek.jo/auth/callback',
            'SESSION_STORE': 'redis',
            'RATE_LIMIT_STORE': 'redis',
            'REDIS_URL': 'rediss://redis.internal:6380/0',
            'DATA_BACKEND': 'postgres',
            'DATABASE_URL': 'postgresql://runtime:secret@postgres.internal:5432/azwatek',
            'WAF_MODE': 'managed',
        })
        self.assertIn('ORDER_ADDRESS_ENCRYPTION_KEY must be a base64url-encoded 32-byte key', issues)

    def test_oidc_scopes_cannot_disable_openid(self):
        env = {
            'APP_ENV': 'production',
            'ENABLE_HSTS': '1',
            'IAM_MODE': 'oidc',
            'PUBLIC_ORIGIN': 'https://app.azwatek.jo',
            'OIDC_ISSUER_URL': 'https://identity.azwatek.jo/realms/azwatek',
            'OIDC_CLIENT_ID': 'azwatek-web',
            'OIDC_REQUIRED_AMR': 'webauthn,fido2,otp',
            'OIDC_SCOPES': 'profile email groups',
            'OIDC_REDIRECT_URI': 'https://app.azwatek.jo/auth/callback',
            'SESSION_STORE': 'redis',
            'RATE_LIMIT_STORE': 'redis',
            'REDIS_URL': 'rediss://redis.internal:6380/0',
            'DATA_BACKEND': 'postgres',
            'DATABASE_URL': 'postgresql://runtime:secret@postgres.internal:5432/azwatek',
            'WAF_MODE': 'managed',
            'ORDER_ADDRESS_ENCRYPTION_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
        }
        self.assertIn('OIDC_SCOPES must include openid when explicitly configured', validate_production_env(env))

    def test_invalid_oidc_role_map_is_rejected(self):
        issues = validate_production_env({'APP_ENV': 'production', 'OIDC_ROLE_MAP': 'not-a-role=group'})
        self.assertIn('OIDC_ROLE_MAP contains an invalid application-role mapping', issues)

    def test_production_requires_explicit_role_map_and_postgres_tls(self):
        issues = validate_production_env({
            'APP_ENV': 'production',
            'OIDC_ROLE_MAP': '',
            'DATABASE_URL': 'postgresql://runtime@postgres.internal:5432/ezwatek',
        })
        self.assertIn('OIDC_ROLE_MAP must be explicitly configured in production', issues)
        self.assertIn('DATABASE_URL or PGSSLMODE must require PostgreSQL TLS (require, verify-ca, or verify-full)', issues)

    def test_duplicate_oidc_application_roles_are_rejected(self):
        issues = validate_production_env({'APP_ENV': 'production', 'OIDC_ROLE_MAP': 'owner=group-a,owner=group-b'})
        self.assertIn('OIDC_ROLE_MAP contains duplicate application roles', issues)

    def test_redirect_must_belong_to_public_origin(self):
        env = {
            'APP_ENV': 'production',
            'ENABLE_HSTS': '1',
            'IAM_MODE': 'oidc',
            'PUBLIC_ORIGIN': 'https://app.azwatek.jo',
            'OIDC_ISSUER_URL': 'https://identity.azwatek.jo/realms/azwatek',
            'OIDC_CLIENT_ID': 'azwatek-web',
            'OIDC_REDIRECT_URI': 'https://other.azwatek.jo/auth/callback',
            'SESSION_STORE': 'redis',
            'RATE_LIMIT_STORE': 'redis',
            'REDIS_URL': 'rediss://redis.internal:6380/0',
            'DATA_BACKEND': 'postgres',
            'DATABASE_URL': 'postgresql://runtime:secret@postgres.internal:5432/azwatek',
            'WAF_MODE': 'managed',
        }
        self.assertIn('OIDC_REDIRECT_URI must belong to PUBLIC_ORIGIN', validate_production_env(env))


if __name__ == '__main__':
    unittest.main(verbosity=2)
