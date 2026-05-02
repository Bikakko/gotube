import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VideoLibrarySourceQueryTests(unittest.TestCase):
    def test_admin_media_source_options_do_not_full_load_source_urls(self):
        source = (ROOT / "server/video_library.py").read_text(encoding="utf-8")

        self.assertIn("def _list_available_source_platforms(", source)
        self.assertIn(".with_entities(platform_case)", source)
        self.assertIn(".distinct()", source)
        self.assertNotIn("query.with_entities(MediaAsset.source_url).all()", source)


if __name__ == "__main__":
    unittest.main()
