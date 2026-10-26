import os
import re
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

import app


class AppSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), app.AppHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def fetch(self, path='/', method='GET'):
        request = Request(self.base_url + path, method=method)
        return urlopen(request, timeout=3)

    def test_html_has_nonce_bound_to_csp(self):
        response = self.fetch('/')
        body = response.read().decode('utf-8')
        csp = response.headers['Content-Security-Policy']
        html_nonce = re.search(r'<style nonce="([^"]+)"', body).group(1)
        csp_nonce = re.search(r"script-src 'nonce-([^']+)'", csp).group(1)
        self.assertEqual(html_nonce, csp_nonce)
        self.assertIn('manifest-src \'self\'', csp)
        self.assertIn('id="admin-view"', body)

    def test_security_headers_are_present(self):
        response = self.fetch('/health')
        self.assertEqual(response.status, 200)
        self.assertIn('"version":"0.12.0"', response.read().decode('utf-8'))
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')
        self.assertEqual(response.headers['Cache-Control'], 'no-store, max-age=0')
        self.assertTrue(response.headers['X-Request-ID'])

    def test_readiness_endpoint_checks_assets(self):
        response = self.fetch('/ready')
        self.assertEqual(response.status, 200)
        self.assertIn('"status":"ready"', response.read().decode('utf-8'))

    def test_service_catalog_is_readable_without_authentication(self):
        response = self.fetch('/api/services')
        payload = response.read().decode('utf-8')
        self.assertEqual(response.status, 200)
        self.assertIn('cleaning', payload)
        self.assertEqual(response.headers['Cache-Control'], 'public, max-age=60')

    def test_auth_status_does_not_create_a_session(self):
        response = self.fetch('/api/auth/status')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.read().decode('utf-8'), '{"authenticated":false}')

    def test_admin_api_requires_a_session(self):
        with self.assertRaises(HTTPError) as caught:
            self.fetch('/api/admin/overview')
        self.assertEqual(caught.exception.code, 401)

    def test_login_requires_json_and_configured_identity(self):
        request = Request(self.base_url + '/api/auth/login', data=b'{}', method='POST', headers={'Content-Type': 'application/json'})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=3)
        self.assertEqual(caught.exception.code, 401)
        self.assertIn('invalid_credentials', caught.exception.read().decode('utf-8'))

    def test_oidc_mode_never_falls_back_to_local_login(self):
        original_mode = os.environ.get('IAM_MODE')
        try:
            os.environ['IAM_MODE'] = 'oidc'
            request = Request(self.base_url + '/api/auth/login', data=b'{}', method='POST', headers={'Content-Type': 'application/json'})
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=3)
            self.assertEqual(caught.exception.code, 503)
            self.assertIn('identity_provider_unavailable', caught.exception.read().decode('utf-8'))
        finally:
            if original_mode is None:
                os.environ.pop('IAM_MODE', None)
            else:
                os.environ['IAM_MODE'] = original_mode

    def test_public_assets_are_allowlisted(self):
        manifest = self.fetch('/manifest.webmanifest').read().decode('utf-8')
        favicon = self.fetch('/favicon.svg').read().decode('utf-8')
        robots = self.fetch('/robots.txt').read().decode('utf-8')
        self.assertIn('عزوتك', manifest)
        self.assertIn('<svg', favicon)
        self.assertIn('Disallow: /', robots)

    def test_unknown_routes_do_not_fall_through(self):
        with self.assertRaises(HTTPError) as caught:
            self.fetch('/does-not-exist')
        self.assertEqual(caught.exception.code, 404)
        self.assertEqual(caught.exception.headers['X-Content-Type-Options'], 'nosniff')

    def test_state_changing_methods_are_closed(self):
        with self.assertRaises(HTTPError) as caught:
            self.fetch('/', method='POST')
        self.assertEqual(caught.exception.code, 405)
        self.assertEqual(caught.exception.headers['Allow'], 'GET, HEAD, OPTIONS')

    def test_production_can_remove_public_admin_markup(self):
        original_env = os.environ.get('APP_ENV')
        original_flag = os.environ.get('ADMIN_UI_ENABLED')
        try:
            os.environ['APP_ENV'] = 'production'
            os.environ.pop('ADMIN_UI_ENABLED', None)
            rendered = app.remove_marked_blocks(app.HTML, app.ADMIN_UI_START, app.ADMIN_UI_END)
            self.assertNotIn('id="admin-view"', rendered)
            self.assertNotIn('لوحة المدير العام', rendered)
            rendered_without_preview = app.remove_marked_blocks(app.HTML, app.PREVIEW_NOTICE_START, app.PREVIEW_NOTICE_END)
            self.assertNotIn('وضع المعاينة:', rendered_without_preview)
        finally:
            if original_env is None:
                os.environ.pop('APP_ENV', None)
            else:
                os.environ['APP_ENV'] = original_env
            if original_flag is None:
                os.environ.pop('ADMIN_UI_ENABLED', None)
            else:
                os.environ['ADMIN_UI_ENABLED'] = original_flag


if __name__ == '__main__':
    unittest.main(verbosity=2)
