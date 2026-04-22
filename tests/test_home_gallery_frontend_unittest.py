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
        self.assertIn('href="/go"', html)
        self.assertNotIn("GOTUBE_HIDDEN_PATH", html)

    def test_home_page_loads_gallery_assets(self):
        html = read_text("www/index.html")

        self.assertIn("/static/index.css", html)
        self.assertIn("/static/index.js", html)

    def test_index_styles_use_soft_rounded_album_cards(self):
        css = read_text("www/index.css")

        self.assertIn("minmax(150px, 220px)", css)
        self.assertIn("border-radius: 42px", css)
        self.assertIn("aspect-ratio: 6 / 4", css)
        self.assertIn("backdrop-filter: blur(14px)", css)
        self.assertIn("inset: -22px", css)

    def test_modal_shell_hides_visible_title_copy_and_count(self):
        html = read_text("www/index.html")
        css = read_text("www/index.css")

        self.assertNotIn("Album View", html)
        self.assertNotIn("gallery-modal-title", html)
        self.assertNotIn("gallery-modal-count", html)
        self.assertIn(".gallery-modal-panel::before", css)
        self.assertIn("border-radius: 42px", css)
        self.assertIn("backdrop-filter: blur(16px)", css)

    def test_home_page_uses_dense_star_layer_soft_flows_and_clouds(self):
        html = read_text("www/index.html")
        css = read_text("www/index.css")

        self.assertGreaterEqual(html.count("<span></span>"), 28)
        self.assertIn("page-flow page-flow-d", html)
        self.assertIn('class="page-clouds"', html)
        self.assertIn("@keyframes cloud-a", css)
        self.assertIn("@keyframes cloud-d", css)
        self.assertIn("@keyframes flow-d", css)
        self.assertNotIn("page-shimmer", html)

    def test_index_script_drives_gallery_and_modal_navigation(self):
        source = read_text("www/index.js")
        common = read_text("www/common.js")
        download = read_text("www/download.js")

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

        self.assertNotIn("album-count", source)
        self.assertNotIn("gallery-modal-count", source)
        self.assertNotIn("album-title", source)
        self.assertNotIn("7777", source)
        self.assertNotIn("7777", common)
        self.assertNotIn("7777", download)


if __name__ == "__main__":
    unittest.main()
