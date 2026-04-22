import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class HomeGalleryFrontendTests(unittest.TestCase):
    def test_home_page_uses_gallery_shell_and_hides_business_words(self):
        html = read_text("www/index.html")

        self.assertIn('id="gallery-app"', html)
        self.assertIn('id="albums-grid"', html)
        self.assertIn('id="gallery-modal"', html)
        self.assertNotIn("Share the tiny bright moments", html)
        self.assertNotIn("拾光相册", html)
        self.assertNotIn("下载页", html)
        self.assertNotIn("管理后台", html)
        self.assertNotIn("视频库", html)

    def test_home_page_contains_secret_entry_placeholder(self):
        html = read_text("www/index.html")

        self.assertIn('id="secret-entry"', html)
        self.assertIn('id="secret-entry-image"', html)

    def test_home_page_loads_gallery_assets(self):
        html = read_text("www/index.html")

        self.assertIn("/static/index.css", html)
        self.assertIn("/static/index.js", html)

    def test_index_styles_use_compact_album_cards(self):
        css = read_text("www/index.css")

        self.assertIn("minmax(160px, 220px)", css)
        self.assertNotIn("minmax(240px, 1fr)", css)

    def test_modal_shell_hides_visible_title_copy(self):
        html = read_text("www/index.html")
        css = read_text("www/index.css")

        self.assertNotIn("Album View", html)
        self.assertNotIn('id="gallery-modal-title"', html)
        self.assertIn('id="gallery-modal-count"', html)
        self.assertIn("font-size: 11px", css)
        self.assertIn("color: rgba(191, 219, 254, 0.54)", css)

    def test_home_page_uses_dense_star_layer(self):
        html = read_text("www/index.html")
        css = read_text("www/index.css")

        self.assertGreaterEqual(html.count("<span></span>"), 18)
        self.assertIn("@keyframes star-drift", css)
        self.assertIn("nth-child(18)", css)

    def test_index_script_drives_gallery_and_modal_navigation(self):
        source = read_text("www/index.js")

        for marker in [
            "loadAlbums",
            "/api/gallery/albums",
            "openAlbum",
            "renderAlbumCards",
            "renderModalImage",
            "showNextImage",
            "showPrevImage",
            "keydown",
            "Escape",
        ]:
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
