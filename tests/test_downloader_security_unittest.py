import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.downloader import Downloader, is_safe_thumbnail_url


class DownloaderSecurityTests(unittest.TestCase):
    def test_safe_thumbnail_url_rejects_local_and_private_hosts(self):
        blocked = [
            "http://127.0.0.1/thumb.jpg",
            "http://localhost/thumb.jpg",
            "http://10.0.0.5/thumb.jpg",
            "http://192.168.1.8/thumb.jpg",
            "http://172.16.1.5/thumb.jpg",
            "file:///tmp/thumb.jpg",
        ]
        for url in blocked:
            self.assertFalse(is_safe_thumbnail_url(url), url)

    def test_safe_thumbnail_url_allows_public_https_hosts(self):
        self.assertTrue(is_safe_thumbnail_url("https://8.8.8.8/thumb.jpg"))

    def test_find_hash_file_uses_in_memory_prefix_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media_dir = root / "Sample_deadbeef"
            media_dir.mkdir()
            media_file = media_dir / "deadbeef.mp4"
            media_file.write_bytes(b"video")

            with (
                patch.object(Downloader, "_check_dependencies", lambda self: None),
                patch.object(Downloader, "_cleanup_orphaned_temp_files", lambda self: None),
                patch.object(Downloader, "cleanup_expired_guest_sessions", lambda self, max_age_hours=24.0: None),
            ):
                downloader = Downloader(download_dir=root)

            self.assertEqual(downloader.find_hash_file("deadbeef"), media_file)
            self.assertEqual(downloader.find_hash_file("dead"), media_file)


if __name__ == "__main__":
    unittest.main()
