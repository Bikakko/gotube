import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.main import app


async def asgi_get(path: str, headers: list[tuple[bytes, bytes]] | None = None):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers or [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    response_headers = {k.decode("latin1"): v.decode("latin1") for k, v in start.get("headers", [])}
    return start["status"], response_headers, body


class GalleryApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.gallery_dir = self.root / "gallery"
        self.gallery_dir.mkdir()
        album = self.gallery_dir / "memes"
        album.mkdir()
        (album / "001.jpg").write_bytes(b"jpeg")
        (album / "002.webp").write_bytes(b"webp")

    def tearDown(self):
        self.tmp.cleanup()

    def test_album_list_endpoint_returns_cards(self):
        with patch("server.gallery.GALLERY_DIR", self.gallery_dir):
            status, headers, body = asyncio.run(asgi_get("/api/gallery/albums"))

        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        self.assertIn(b'"slug":"memes"', body)
        self.assertIn(b'"image_count":2', body)

    def test_album_detail_endpoint_returns_images(self):
        with patch("server.gallery.GALLERY_DIR", self.gallery_dir):
            status, headers, body = asyncio.run(asgi_get("/api/gallery/albums/memes"))

        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        self.assertIn(b'"name":"001.jpg"', body)
        self.assertIn(b'"name":"002.webp"', body)

    def test_image_endpoint_returns_file_content(self):
        with patch("server.gallery.GALLERY_DIR", self.gallery_dir):
            status, headers, body = asyncio.run(asgi_get("/api/gallery/image/memes/001.jpg"))

        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b"jpeg"))
        self.assertIn("image/", headers.get("content-type", ""))

    def test_gallery_endpoints_reject_invalid_or_missing_paths(self):
        with patch("server.gallery.GALLERY_DIR", self.gallery_dir):
            invalid_status, _, _body = asyncio.run(asgi_get("/api/gallery/albums/../secret"))
            missing_status, _, _body = asyncio.run(asgi_get("/api/gallery/image/memes/missing.jpg"))

        self.assertEqual(invalid_status, 404)
        self.assertEqual(missing_status, 404)


if __name__ == "__main__":
    unittest.main()
