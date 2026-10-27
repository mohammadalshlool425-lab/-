from datetime import datetime, timedelta, timezone
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
        self.assertIn('"version":"0.15.0"', response.read().decode('utf-8'))
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')
        self.assertEqual(response.headers['Cache-Control'], 'no-store, max-age=0')
        self.assertTrue(response.headers['X-Request-ID'])

    def test_readiness_endpoint_checks_assets(self):
        response = self.fetch('/ready')
        self.assertEqual(response.status, 200)
        self.assertIn('"status":"ready"', response.read().decode('utf-8'))

    def test_production_readiness_fails_without_external_dependencies(self):
        original_env = os.environ.get('APP_ENV')
        try:
            os.environ['APP_ENV'] = 'production'
            with self.assertRaises(HTTPError) as caught:
                self.fetch('/ready')
            self.assertEqual(caught.exception.code, 503)
            body = caught.exception.read().decode('utf-8')
            self.assertIn('"identity_provider":false', body)
        finally:
            if original_env is None:
                os.environ.pop('APP_ENV', None)
            else:
                os.environ['APP_ENV'] = original_env

    def test_service_catalog_is_readable_without_authentication(self):
        response = self.fetch('/api/services')
        payload = response.read().decode('utf-8')
        self.assertEqual(response.status, 200)
        self.assertIn('cleaning', payload)
        self.assertEqual(response.headers['Cache-Control'], 'public, max-age=60')
        self.assertNotIn('Pragma', response.headers)

    def test_provider_directory_is_not_fabricated_in_development(self):
        response = self.fetch('/api/providers?service_slug=cleaning&city=amman')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.read().decode('utf-8'), '{"providers":[]}')

    def test_auth_status_does_not_create_a_session(self):
        response = self.fetch('/api/auth/status')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.read().decode('utf-8'), '{"authenticated":false,"auth_mode":"local-preview"}')

    def test_order_request_fingerprint_is_stable_but_payload_bound(self):
        original_key = os.environ.get('ORDER_ADDRESS_ENCRYPTION_KEY')
        try:
            os.environ['ORDER_ADDRESS_ENCRYPTION_KEY'] = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
            start = datetime.now(timezone.utc) + timedelta(days=1)
            body = {
                'service_slug': 'cleaning',
                'city': 'amman',
                'address': 'شارع الجامعة، بناية ١٢',
                'estimated_amount_minor': 1500,
                'scheduled_from': start.isoformat(),
                'scheduled_to': (start + timedelta(hours=2)).isoformat(),
            }
            first = app._parse_order_request(body, 'request-key-123456')
            second = app._parse_order_request(dict(body), 'request-key-123456')
            changed = dict(body, address='شارع مختلف، بناية ١٣')
            third = app._parse_order_request(changed, 'request-key-123456')
            self.assertEqual(first['request_fingerprint'], second['request_fingerprint'])
            self.assertNotEqual(first['request_fingerprint'], third['request_fingerprint'])
            self.assertEqual(len(first['request_fingerprint']), 32)
        finally:
            if original_key is None:
                os.environ.pop('ORDER_ADDRESS_ENCRYPTION_KEY', None)
            else:
                os.environ['ORDER_ADDRESS_ENCRYPTION_KEY'] = original_key

    def test_customer_orders_require_authentication(self):
        with self.assertRaises(HTTPError) as caught:
            self.fetch('/api/orders')
        self.assertEqual(caught.exception.code, 401)
        request = Request(self.base_url + '/api/orders', data=b'', method='POST')
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=3)
        self.assertEqual(caught.exception.code, 401)

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
        with self.assertRaises(HTTPError) as caught:
            self.fetch('/', method='PATCH')
        self.assertEqual(caught.exception.code, 405)
        self.assertEqual(caught.exception.headers['X-Content-Type-Options'], 'nosniff')

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
            rendered_without_samples = app.remove_marked_blocks(rendered, app.CUSTOMER_SAMPLE_ORDERS_START, app.CUSTOMER_SAMPLE_ORDERS_END)
            self.assertNotIn('<article class="order-row"><div class="provider-avatar">ي</div>', rendered_without_samples)
            rendered_without_notifications = app.remove_marked_blocks(app.HTML, app.PREVIEW_NOTIFICATIONS_START, app.PREVIEW_NOTIFICATIONS_END)
            self.assertNotIn('الفني بالطريق إليك', rendered_without_notifications)
            rendered_without_payment = app.remove_marked_blocks(app.HTML, app.PREVIEW_PAYMENT_START, app.PREVIEW_PAYMENT_END)
            self.assertNotIn('••••  4821', rendered_without_payment)
            rendered_without_home_samples = app.remove_marked_blocks(app.HTML, app.PREVIEW_CURRENT_ORDER_START, app.PREVIEW_CURRENT_ORDER_END)
            self.assertNotIn('طلبك الحالي', rendered_without_home_samples)
            rendered_without_providers = app.remove_marked_blocks(app.HTML, app.PREVIEW_PROVIDERS_START, app.PREVIEW_PROVIDERS_END)
            self.assertNotIn('<button class="provider-card" type="button" data-book="تنظيف وتعقيم">', rendered_without_providers)
            self.assertNotIn('ليان أحمد', app.HTML)
            self.assertNotIn('079 123 4567', app.HTML)
            self.assertNotIn('nav-count">2', app.HTML)
            production_admin = app.remove_marked_blocks(app.HTML, app.ADMIN_PREVIEW_DATA_START, app.ADMIN_PREVIEW_DATA_END)
            self.assertNotIn('بيانات المعاينة', production_admin)
            self.assertIn('id="adminLiveState"', production_admin)
            os.environ['ADMIN_UI_ENABLED'] = '1'
            production_response = self.fetch('/')
            production_body = production_response.read().decode('utf-8')
            self.assertNotIn('١,٢٨٤', production_body)
            self.assertIn('id="adminLiveState"', production_body)
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
