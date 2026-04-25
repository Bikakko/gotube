import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class AdminMediaFrontendTests(unittest.TestCase):
    def test_render_js_uses_information_card_structure(self):
        render_js = read_text("www/admin/js/render.js")
        data_js = read_text("www/admin/js/data.js")

        self.assertIn("className: 'filters filters-toolbar'", render_js)
        self.assertIn("className: 'filter-cluster filter-cluster-primary'", render_js)
        self.assertIn("className: 'filter-cluster filter-cluster-secondary'", render_js)
        self.assertIn("className: 'video-summary-row'", render_js)
        self.assertIn("video-secondary-actions", render_js)
        self.assertIn("className: `video-select-toggle ${isSelected ? 'selected' : ''}`", render_js)
        self.assertIn("textContent: isSelected ? '已选中' : '选择'", render_js)
        self.assertIn("window.showPlayerModal(video)", render_js)
        self.assertNotIn("textContent: '播放'", render_js)
        self.assertIn("media_asset_ids", data_js)
        self.assertIn("state.videos.filter(v => state.selectedVideos.has(v.filename))", data_js)

    def test_admin_css_styles_media_toolbar_and_info_cards(self):
        css = read_text("www/admin/css/admin.css")

        self.assertIn(".filters-toolbar {", css)
        self.assertIn(".filter-cluster {", css)
        self.assertIn(".video-summary-row {", css)
        self.assertIn(".video-select-toggle {", css)
        self.assertIn(".video-select-toggle.selected {", css)
        self.assertIn("background: rgba(248, 81, 73, 0.22);", css)
        self.assertIn("border-color: rgba(248, 81, 73, 0.55);", css)
        self.assertIn(".video-card:hover .video-thumb img {", css)


if __name__ == "__main__":
    unittest.main()
