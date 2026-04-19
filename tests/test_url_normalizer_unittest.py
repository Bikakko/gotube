import unittest
import tempfile
from pathlib import Path

from server.downloader import Downloader
from server.queue_manager import QueueManager
from server.url_normalizer import normalize_media_url
from server.video_library import normalize_source_url


class UrlNormalizerTests(unittest.TestCase):
    def test_youtube_watch_url_removes_progress_and_tracking(self):
        normalized = normalize_media_url("https://www.youtube.com/watch?v=abc123&t=30s&utm_source=x")

        self.assertEqual(normalized.canonical_url, "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(normalized.platform, "youtube")
        self.assertEqual(normalized.media_key, "youtube:abc123")

    def test_youtube_short_url_normalizes_to_watch_url(self):
        normalized = normalize_media_url("https://youtu.be/abc123?si=share&t=42")

        self.assertEqual(normalized.canonical_url, "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(normalized.media_key, "youtube:abc123")

    def test_bilibili_url_removes_tracking_query(self):
        normalized = normalize_media_url(
            "https://www.bilibili.com/video/BV14t4y1A7Tu/?spm_id_from=333.337.search-card.all.click"
        )

        self.assertEqual(normalized.canonical_url, "https://www.bilibili.com/video/BV14t4y1A7Tu")
        self.assertEqual(normalized.platform, "bilibili")
        self.assertEqual(normalized.media_key, "bilibili:BV14t4y1A7Tu")

    def test_bilibili_keeps_page_query_but_drops_tracking(self):
        normalized = normalize_media_url("https://www.bilibili.com/video/BV123?vd_source=x&p=2")

        self.assertEqual(normalized.canonical_url, "https://www.bilibili.com/video/BV123?p=2")
        self.assertEqual(normalized.media_key, "bilibili:BV123:p=2")

    def test_x_status_url_normalizes_domain(self):
        normalized = normalize_media_url("https://twitter.com/user/status/2042105224727269424?s=20")

        self.assertEqual(normalized.canonical_url, "https://x.com/i/status/2042105224727269424")
        self.assertEqual(normalized.platform, "twitter")
        self.assertEqual(normalized.media_key, "twitter:2042105224727269424")

    def test_existing_video_library_normalize_source_url_uses_canonical_url(self):
        self.assertEqual(
            normalize_source_url("https://youtu.be/abc123?si=share&t=42"),
            "https://www.youtube.com/watch?v=abc123",
        )
        self.assertEqual(
            normalize_source_url("https://twitter.com/user/status/2042105224727269424?s=20"),
            "https://x.com/i/status/2042105224727269424",
        )

    def test_unknown_url_drops_common_tracking_params(self):
        normalized = normalize_media_url("https://example.test/watch?id=1&utm_source=x&t=10&b=2")

        self.assertEqual(normalized.canonical_url, "https://example.test/watch?b=2&id=1")
        self.assertEqual(normalized.platform, "example.test")
        self.assertEqual(normalized.media_key, "url:https://example.test/watch?b=2&id=1")

    def test_queue_duplicate_check_uses_canonical_source_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = Downloader(download_dir=Path(tmp) / "downloads")
            manager = QueueManager(downloader)
            first_url = "https://youtu.be/abc123?si=share"
            second_url = "https://www.youtube.com/watch?v=abc123&t=42"
            task = downloader.create_task(first_url, "client-1")
            task.source_url = normalize_media_url(first_url).canonical_url

            found = manager._find_task_by_url("client-1", normalize_media_url(second_url).canonical_url)

            self.assertIs(found, task)


if __name__ == "__main__":
    unittest.main()
