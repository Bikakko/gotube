import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class AdminModalsFrontendTests(unittest.TestCase):
    def test_share_copy_uses_share_token_and_fallback_copy(self):
        source = read_text("www/admin/js/modals.js")

        self.assertIn("video.share_token || video.file_hash", source)
        self.assertIn("navigator.clipboard && typeof navigator.clipboard.writeText === 'function'", source)
        self.assertIn("document.execCommand('copy')", source)
        self.assertIn("复制失败，请手动复制链接", source)

    def test_player_modal_exposes_loop_toggle(self):
        source = read_text("www/admin/js/modals.js")
        css = read_text("www/admin/css/admin.css")

        self.assertIn("loop: true", source)
        self.assertIn("videoEl.loop = true", source)
        self.assertNotIn("player-loop-toggle", source)
        self.assertNotIn(".player-loop-toggle.active", css)
        self.assertNotIn(".player-modal-actions", css)

    def test_admin_video_cards_render_duration_badge(self):
        render_js = read_text("www/admin/js/render.js")
        css = read_text("www/admin/css/admin.css")

        self.assertIn("formatDurationLabel", render_js)
        self.assertIn("video-duration-badge", render_js)
        self.assertIn(".video-duration-badge", css)

    def test_watch_page_defaults_to_loop_playback(self):
        watch_html = read_text("www/watch.html")

        self.assertIn("controls autoplay loop", watch_html)


if __name__ == "__main__":
    unittest.main()
