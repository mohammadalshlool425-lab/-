import unittest

from scripts.staging_gate import _json_body, validate_target


class StagingGateTests(unittest.TestCase):
    def test_remote_gate_requires_explicit_https_allowance(self):
        self.assertEqual(
            validate_target('https://staging.azwatek.jo', allow_remote=True),
            'https://staging.azwatek.jo',
        )
        with self.assertRaises(ValueError):
            validate_target('https://staging.azwatek.jo')
        with self.assertRaises(ValueError):
            validate_target('http://staging.azwatek.jo', allow_remote=True)

    def test_target_rejects_credentials_and_paths(self):
        with self.assertRaises(ValueError):
            validate_target('https://user:secret@staging.azwatek.jo', allow_remote=True)
        with self.assertRaises(ValueError):
            validate_target('https://staging.azwatek.jo/app', allow_remote=True)
        self.assertEqual(validate_target('http://127.0.0.1:8000/'), 'http://127.0.0.1:8000')

    def test_json_body_requires_an_object(self):
        self.assertEqual(_json_body(b'{"status":"ready"}')['status'], 'ready')
        with self.assertRaises(ValueError):
            _json_body(b'[]')
        with self.assertRaises(ValueError):
            _json_body(b'not-json')


if __name__ == '__main__':
    unittest.main(verbosity=2)
