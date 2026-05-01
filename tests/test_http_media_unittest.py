import asyncio
import tempfile
import unittest
from pathlib import Path

from fastapi import Request

from server.http_media import build_video_stream_response


async def _render_response(response, headers: list[tuple[bytes, bytes]] | None = None):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/video",
        "raw_path": b"/video",
        "query_string": b"",
        "headers": headers or [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }
    messages = []

    receive_count = 0

    async def receive():
        nonlocal receive_count
        if receive_count == 0:
            receive_count += 1
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.Future()

    async def send(message):
        messages.append(message)

    await response(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    response_headers = {k.decode("latin1"): v.decode("latin1") for k, v in start.get("headers", [])}
    return start["status"], response_headers, body


def _make_request(range_header: str | None = None) -> Request:
    headers = [(b"host", b"testserver")]
    if range_header is not None:
        headers.append((b"range", range_header.encode("latin1")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/video",
        "raw_path": b"/video",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }
    return Request(scope)


class HttpMediaTests(unittest.TestCase):
    def test_range_request_returns_partial_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.mp4"
            path.write_bytes(b"0123456789")
            request = _make_request("bytes=2-5")

            response = build_video_stream_response(request, path, filename="sample.mp4")
            status, headers, body = asyncio.run(_render_response(response))

            self.assertEqual(status, 206)
            self.assertEqual(headers.get("accept-ranges"), "bytes")
            self.assertEqual(headers.get("content-range"), "bytes 2-5/10")
            self.assertEqual(headers.get("content-length"), "4")
            self.assertEqual(body, b"2345")

    def test_invalid_range_request_returns_416(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.mp4"
            path.write_bytes(b"0123456789")
            request = _make_request("bytes=99-100")

            response = build_video_stream_response(request, path, filename="sample.mp4")
            status, headers, body = asyncio.run(_render_response(response))

            self.assertEqual(status, 416)
            self.assertEqual(headers.get("accept-ranges"), "bytes")
            self.assertEqual(headers.get("content-range"), "bytes */10")
            self.assertEqual(body, b"")

    def test_normal_request_advertises_byte_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.mp4"
            path.write_bytes(b"0123456789")
            request = _make_request()

            response = build_video_stream_response(request, path, filename="sample.mp4")
            status, headers, body = asyncio.run(_render_response(response))

            self.assertEqual(status, 200)
            self.assertEqual(headers.get("accept-ranges"), "bytes")
            self.assertEqual(headers.get("content-length"), "10")
            self.assertEqual(body, b"0123456789")
