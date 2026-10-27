import base64
import hashlib
import unittest
from urllib.parse import parse_qs, urlsplit

from oidc import MemoryStateStore, OIDCClient, OIDCConfig, OIDCError, _roles_from_claims


class OIDCTests(unittest.TestCase):
    def test_authorization_url_uses_pkce_and_one_time_state(self):
        config = OIDCConfig(
            issuer='https://identity.azwatek.jo/realms/ezwatek',
            client_id='ezwatek-web',
            redirect_uri='https://app.azwatek.jo/auth/callback',
            role_map=(('owner', 'ezwatek-owner'),),
        )
        discovery = {
            'issuer': config.issuer,
            'authorization_endpoint': config.issuer + '/protocol/openid-connect/auth',
            'token_endpoint': config.issuer + '/protocol/openid-connect/token',
            'jwks_uri': config.issuer + '/protocol/openid-connect/certs',
            'response_types_supported': ['code'],
        }
        store = MemoryStateStore()
        client = OIDCClient(config, store, fetch_json=lambda url: discovery)
        parsed = urlsplit(client.authorization_url())
        query = parse_qs(parsed.query)
        self.assertEqual(query['client_id'], ['ezwatek-web'])
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertEqual(len(query['state'][0]), 43)
        verifier = store.pop(query['state'][0])['verifier']
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        self.assertEqual(query['code_challenge'], [expected])
        self.assertIsNone(store.pop(query['state'][0]))

    def test_discovery_issuer_mismatch_is_rejected(self):
        config = OIDCConfig(
            issuer='https://identity.azwatek.jo/realms/ezwatek',
            client_id='ezwatek-web',
            redirect_uri='https://app.azwatek.jo/auth/callback',
        )
        client = OIDCClient(config, MemoryStateStore(), fetch_json=lambda url: {
            'issuer': 'https://attacker.example/realms/fake',
            'authorization_endpoint': 'https://attacker.example/auth',
            'token_endpoint': 'https://attacker.example/token',
            'jwks_uri': 'https://attacker.example/jwks',
        })
        with self.assertRaises(OIDCError):
            client.authorization_url()

    def test_roles_are_mapped_from_keycloak_claims(self):
        config = OIDCConfig(
            issuer='https://identity.azwatek.jo/realms/ezwatek',
            client_id='ezwatek-web',
            redirect_uri='https://app.azwatek.jo/auth/callback',
            role_map=(('owner', 'ezwatek-owner'), ('security_auditor', 'security-auditor')),
        )
        roles = _roles_from_claims({
            'groups': ['ezwatek-owner'],
            'realm_access': {'roles': ['security-auditor']},
        }, config)
        self.assertEqual(roles, ('owner', 'security_auditor'))

    def test_malformed_resource_roles_are_ignored_safely(self):
        config = OIDCConfig(
            issuer='https://identity.azwatek.jo/realms/ezwatek',
            client_id='ezwatek-web',
            redirect_uri='https://app.azwatek.jo/auth/callback',
            role_map=(('owner', 'ezwatek-owner'),),
        )
        roles = _roles_from_claims({'resource_access': {'ezwatek-web': {'roles': [{'not': 'a string'}]}}}, config)
        self.assertEqual(roles, ())

    def test_invalid_endpoint_is_rejected(self):
        config = OIDCConfig(
            issuer='http://identity.azwatek.jo/realms/ezwatek',
            client_id='ezwatek-web',
            redirect_uri='https://app.azwatek.jo/auth/callback',
        )
        with self.assertRaises(OIDCError):
            OIDCClient(config, MemoryStateStore()).authorization_url()


if __name__ == '__main__':
    unittest.main(verbosity=2)
