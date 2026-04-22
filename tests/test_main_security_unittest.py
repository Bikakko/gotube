import asyncio
import unittest

from server.main import app


async def asgi_get(path: str, headers: list[tuple[bytes, bytes]] | None = None):
    scope = {
        'type': 'http',
        'asgi': {'version': '3.0'},
        'http_version': '1.1',
        'method': 'GET',
        'scheme': 'http',
        'path': path,
        'raw_path': path.encode('utf-8'),
        'query_string': b'',
        'headers': headers or [(b'host', b'testserver')],
        'client': ('127.0.0.1', 12345),
        'server': ('testserver', 80),
        'root_path': '',
    }
    messages = []

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    start = next(m for m in messages if m['type'] == 'http.response.start')
    body = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
    response_headers = {k.decode('latin1'): v.decode('latin1') for k, v in start.get('headers', [])}
    return start['status'], response_headers, body


class MainSecurityRoutesTests(unittest.TestCase):
    def test_sensitive_probe_paths_return_not_found(self):
        for path in [
            '/.git/config',
            '/.env',
            '/.svn/entries',
            '/wp-login.php',
            '/composer.json',
            '/backup.zip',
        ]:
            status, _headers, _body = asyncio.run(asgi_get(path))
            self.assertEqual(status, 404, path)

    def test_unknown_path_returns_not_found_instead_of_watch_page(self):
        status, _headers, _body = asyncio.run(asgi_get('/definitely-not-a-real-page'))
        self.assertEqual(status, 404)

    def test_real_static_asset_still_serves_normally(self):
        status, headers, body = asyncio.run(asgi_get('/download.js'))
        self.assertEqual(status, 200)
        self.assertIn('javascript', headers.get('content-type', ''))
        self.assertTrue(body)

    def test_security_headers_present_on_html_response(self):
        status, headers, _body = asyncio.run(asgi_get('/'))
        self.assertEqual(status, 200)
        self.assertEqual(headers.get('x-content-type-options'), 'nosniff')
        self.assertEqual(headers.get('referrer-policy'), 'same-origin')
        self.assertEqual(headers.get('x-frame-options'), 'DENY')
        self.assertIn('default-src', headers.get('content-security-policy', ''))


if __name__ == '__main__':
    unittest.main()
