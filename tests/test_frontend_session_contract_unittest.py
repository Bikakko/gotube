import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class FrontendSessionContractTests(unittest.TestCase):
    def test_common_session_helper_owns_download_client_state(self):
        common_js = read_text("www/common.js")

        self.assertIn("window.GoTubeSession", common_js)
        for helper in [
            "getDownloadClientId",
            "resetDownloadClient",
            "markAuthenticatedClient",
            "clearAuthenticatedClient",
            "wasAuthenticatedClient",
            "clearAuthState",
        ]:
            self.assertIn(helper, common_js)

    def test_pages_use_shared_session_helper_for_auth_client_cleanup(self):
        for path in [
            "www/download.js",
            "www/admin/js/auth.js",
            "www/admin/js/users.js",
            "www/common.js",
        ]:
            source = read_text(path)
            self.assertIn("GoTubeSession", source, path)
            if path != "www/common.js":
                self.assertNotIn("gotube_authenticated_client", source, path)

    def test_download_page_loads_common_helpers_before_download_script(self):
        html = read_text("www/download.html")
        common_idx = html.find("/static/common.js")
        download_idx = html.find("/static/download.js")

        self.assertGreaterEqual(common_idx, 0)
        self.assertGreater(download_idx, common_idx)

    def test_guest_completed_task_can_play_without_share_hash(self):
        source = read_text("www/download.js")

        self.assertIn("const canPlayGuestFile", source)
        self.assertIn("if (!t || (!canPlayGuestFile && !canPlaySharedFile)) return;", source)
        self.assertIn("if (canPlayGuestFile)", source)

    def test_download_page_renders_cancelled_status(self):
        source = read_text("www/download.js")

        self.assertIn("cancelled: '已取消'", source)
        self.assertIn("status-cancelled", source)

    def test_logout_checks_active_downloads_before_clearing_session(self):
        source = read_text("www/download.js")

        self.assertIn("getActiveDownloads", source)
        self.assertIn("/api/tasks/active", source)
        self.assertIn("cancelActiveDownloads", source)
        self.assertIn("/api/tasks/cancel-active", source)


if __name__ == "__main__":
    unittest.main()
