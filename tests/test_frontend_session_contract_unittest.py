import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class FrontendSessionContractTests(unittest.TestCase):
    def test_common_session_helper_owns_download_client_state(self):
        common_js = read_text("www/shared/common.js")

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
        self.assertIn("attachVideoKeyboardControls", common_js)
        self.assertIn("event.key === ' ' || event.code === 'Space'", common_js)
        self.assertIn("wheelTarget.addEventListener('wheel', wheelHandler, { passive: false });", common_js)
        self.assertIn("event.repeat", common_js)
        self.assertIn("showVolumeHud", common_js)
        self.assertIn("video.tabIndex = 0;", common_js)

    def test_pages_use_shared_session_helper_for_auth_client_cleanup(self):
        module_source = read_text("www/shared/common.module.js")
        self.assertIn("export const session", module_source)
        self.assertIn("markAuthenticatedClient", module_source)
        self.assertIn("clearAuthState", module_source)

        for path in [
            "www/admin/js/auth.js",
            "www/admin/js/users.js",
            "www/shared/common.js",
        ]:
            source = read_text(path)
            self.assertIn("GoTubeSession", source, path)
            if path != "www/shared/common.js":
                self.assertNotIn("gotube_authenticated_client", source, path)

        download_source = read_text("www/download/page.js")
        self.assertIn('from "/static/shared/common.module.js"', download_source)
        self.assertIn("session.clearAuthState", download_source)
        self.assertNotIn("gotube_authenticated_client", download_source)

    def test_download_page_loads_common_helpers_before_download_script(self):
        html = read_text("www/download/index.html")
        self.assertIn('/static/download/page.css?v={{ASSET_VERSION}}', html)
        self.assertIn('type="module" src="/static/download/page.js?v={{ASSET_VERSION}}"', html)
        self.assertNotIn("/static/shared/common.js", html)

    def test_guest_completed_task_can_play_without_share_hash(self):
        source = read_text("www/download/page.js")

        self.assertIn("const canPlayGuestFile", source)
        self.assertIn("if (!t || (!canPlayGuestFile && !canPlaySharedFile)) return;", source)
        self.assertIn("if (canPlayGuestFile)", source)

    def test_download_page_treats_admin_as_library_user(self):
        source = read_text("www/download/page.js")

        self.assertIn("function isLibraryUser()", source)
        self.assertIn("return isLoggedIn && currentUser && (currentUser.role === 'user' || currentUser.role === 'admin');", source)
        self.assertIn("if (!isLibraryUser()) {", source)
        self.assertIn("section.hidden = !isLibraryUser();", source)

    def test_download_page_archives_completed_library_tasks_but_keeps_guest_cards(self):
        source = read_text("www/download/page.js")

        self.assertIn("function shouldArchiveTaskCard(task)", source)
        self.assertIn("&& isLibraryUser()", source)
        self.assertIn("(task.status === 'completed' || task.status === 'duplicate')", source)
        self.assertIn("&& task.user_video_item_id", source)
        self.assertIn("delete tasks[task.task_id];", source)
        self.assertIn("tasks[task.task_id] = task;", source)

    def test_download_page_renders_cancelled_status(self):
        source = read_text("www/download/page.js")

        self.assertIn("status-cancelled", source)

    def test_download_input_is_marked_as_non_auth_field(self):
        html = read_text("www/download/index.html")

        self.assertIn('id="download-form"', html)
        self.assertIn('id="url-input"', html)
        self.assertIn('name="download_url"', html)
        self.assertIn('autocomplete="off"', html)
        self.assertIn('inputmode="url"', html)
        self.assertIn('spellcheck="false"', html)

    def test_logout_checks_active_downloads_before_clearing_session(self):
        source = read_text("www/download/page.js")

        self.assertIn("getActiveDownloads", source)
        self.assertIn("/api/tasks/active", source)
        self.assertIn("cancelActiveDownloads", source)
        self.assertIn("/api/tasks/cancel-active", source)

    def test_logout_active_download_prompt_allows_staying_logged_in(self):
        source = read_text("www/download/page.js")

        self.assertIn("confirmLogoutWithActiveDownloads", source)
        self.assertIn("logoutAction === 'stay'", source)

    def test_download_page_exposes_profile_and_password_controls(self):
        html = read_text("www/download/index.html")
        source = read_text("www/download/page.js")

        self.assertIn('id="profile-btn"', html)
        self.assertIn('id="password-btn"', html)
        self.assertIn('id="register-display-name"', html)
        self.assertIn("function formatIdentityText(user)", source)
        self.assertIn("display_name: displayName", source)
        self.assertIn("formatIdentityText(currentUser)", source)
        self.assertIn("promptUpdateDisplayName", source)
        self.assertIn("promptChangePassword", source)

    def test_download_page_exposes_actionable_error_model(self):
        html = read_text("www/download/index.html")
        source = read_text("www/download/page.js")

        self.assertIn('id="actionable-error"', html)
        self.assertIn('id="actionable-error-actions"', html)
        self.assertIn("function showActionableError(", source)
        self.assertIn("function clearActionableError()", source)
        self.assertIn("renderActionableErrorActions(", source)

    def test_download_page_routes_key_failures_to_actionable_error_model(self):
        source = read_text("www/download/page.js")

        self.assertIn("showLoginError(err.message ||", source)
        self.assertIn("showActionableError({", source)
        self.assertIn("context: 'submit'", source)
        self.assertIn("context: 'library'", source)
        self.assertIn("onClick: handleLogin", source)
        self.assertIn("onClick: submit", source)
        self.assertIn("onClick: loadMyLibrary", source)

    def test_download_page_uses_shared_video_keyboard_controls_for_modal_player(self):
        source = read_text("www/download/page.js")

        self.assertIn('attachVideoKeyboardControls, resolveHiddenPath, session } from "/static/shared/common.module.js"', source)
        self.assertIn("let modalVideoKeyboardCleanup = null;", source)
        self.assertIn("modalVideoKeyboardCleanup?.();", source)
        self.assertIn("attachVideoKeyboardControls(video", source)
        self.assertIn("attachVideoKeyboardControls(elem", source)
        self.assertIn("wheelTarget: $('#modal-body') || $('#modal-video') || video", source)
        self.assertIn("wheelTarget: $('#modal-body') || $('#modal-video') || elem", source)
        self.assertIn("feedbackTarget: $('#modal-body') || $('#modal-video') || video.parentElement || video", source)
        self.assertIn("feedbackTarget: $('#modal-body') || $('#modal-video') || elem.parentElement || elem", source)



if __name__ == "__main__":
    unittest.main()
