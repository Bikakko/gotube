import asyncio
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.admin_api import get_user_library, get_videos, list_users, update_user
from server.db import Base, MediaAsset, MediaSource, User, UserVideoItem
from server.models import UpdateUserRequest

ROOT = Path(__file__).resolve().parents[1]


class AdminManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.engine = create_engine(f"sqlite:///{self.root / 'admin.db'}")
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def _user(self, session, username: str, role: str = "user", quota_mb: int | None = None) -> User:
        user = User(
            username=username,
            password_hash="x",
            role=role,
            is_active=True,
            storage_quota_mb=quota_mb,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    def _asset(
        self,
        session,
        title: str,
        file_hash: str,
        size: int = 128,
        created_at: datetime | None = None,
    ) -> MediaAsset:
        created_at = created_at or datetime.now(UTC)
        asset = MediaAsset(
            fingerprint=f"fp-{file_hash}",
            file_hash=file_hash,
            filename=f"{title}_{file_hash}/{file_hash}.mp4",
            filepath=str(self.root / f"{file_hash}.mp4"),
            size_bytes=size,
            title=title,
            thumbnail="",
            duration=12.0,
            source_url=f"https://example.test/{file_hash}",
            meta_json="{}",
            created_at=created_at,
            last_seen_at=created_at,
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        return asset

    def _item(self, session, owner: User, asset: MediaAsset) -> UserVideoItem:
        item = UserVideoItem(
            owner_user_id=owner.id,
            media_asset_id=asset.id,
            display_title=asset.title,
            share_token=f"share-{owner.username}-{asset.file_hash}",
            share_enabled=True,
            saved_at=datetime.now(UTC),
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return item

    def _source(self, session, asset: MediaAsset, url: str) -> MediaSource:
        source = MediaSource(
            media_asset_id=asset.id,
            source_url=url,
            normalized_url=url,
            platform="test",
            platform_video_id="",
        )
        session.add(source)
        session.commit()
        session.refresh(source)
        return source

    def test_list_users_includes_library_usage_summary(self):
        with self.Session() as session:
            admin = self._user(session, "admin", role="admin")
            alice = self._user(session, "alice", quota_mb=10)
            asset = self._asset(session, "Alpha", "aaaaaaaa", size=512)
            self._item(session, alice, asset)
            alice.storage_used_bytes = 512
            session.commit()

            users = asyncio.run(list_users(admin=admin, db=session))

            alice_row = next(row for row in users if row["username"] == "alice")
            admin_row = next(row for row in users if row["username"] == "admin")
            self.assertEqual(alice_row["storage_quota_mb"], 10)
            self.assertEqual(alice_row["storage_used_bytes"], 512)
            self.assertEqual(alice_row["video_count"], 1)
            self.assertFalse(alice_row["is_system_account"])
            self.assertTrue(admin_row["is_system_account"])

    def test_update_user_allows_regular_user_quota_but_protects_admin(self):
        with self.Session() as session:
            admin = self._user(session, "admin", role="admin")
            alice = self._user(session, "alice", quota_mb=10)

            result = asyncio.run(
                update_user(
                    alice.id,
                    UpdateUserRequest(storage_quota_mb=25),
                    admin=admin,
                    db=session,
                )
            )

            self.assertEqual(result["storage_quota_mb"], 25)
            self.assertEqual(session.get(User, alice.id).storage_quota_mb, 25)

            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(
                    update_user(
                        admin.id,
                        UpdateUserRequest(storage_quota_mb=25),
                        admin=admin,
                        db=session,
                    )
                )
            self.assertEqual(ctx.exception.status_code, 403)

    def test_get_videos_supports_owner_and_legacy_filters(self):
        with self.Session() as session:
            admin = self._user(session, "admin", role="admin")
            alice = self._user(session, "alice")
            bob = self._user(session, "bob")
            alice_asset = self._asset(session, "Alpha", "aaaaaaaa")
            bob_asset = self._asset(session, "Beta", "bbbbbbbb")
            legacy_asset = self._asset(session, "Legacy", "cccccccc")
            self._item(session, alice, alice_asset)
            self._item(session, bob, bob_asset)

            all_result = asyncio.run(get_videos(page=1, per_page=20, admin=admin, db=session))
            owner_result = asyncio.run(
                get_videos(page=1, per_page=20, owner_user_id=alice.id, admin=admin, db=session)
            )
            legacy_result = asyncio.run(
                get_videos(page=1, per_page=20, owner="legacy", admin=admin, db=session)
            )

            all_titles = {row["title"] for row in all_result["videos"]}
            self.assertEqual(all_titles, {"Alpha", "Beta", "Legacy"})
            alpha = next(row for row in all_result["videos"] if row["title"] == "Alpha")
            legacy = next(row for row in all_result["videos"] if row["title"] == "Legacy")
            self.assertEqual(alpha["owner_username"], "alice")
            self.assertEqual(alpha["reference_count"], 1)
            self.assertFalse(alpha["is_legacy"])
            self.assertIsNone(legacy["owner_user_id"])
            self.assertTrue(legacy["is_legacy"])
            self.assertEqual(legacy["media_asset_id"], legacy_asset.id)
            self.assertEqual([row["title"] for row in owner_result["videos"]], ["Alpha"])
            self.assertEqual([row["title"] for row in legacy_result["videos"]], ["Legacy"])

    def test_get_videos_groups_shared_media_asset_once(self):
        with self.Session() as session:
            admin = self._user(session, "admin", role="admin")
            alice = self._user(session, "alice")
            bob = self._user(session, "bob")
            shared_asset = self._asset(session, "Shared", "dddddddd")
            self._item(session, alice, shared_asset)
            self._item(session, bob, shared_asset)
            self._source(session, shared_asset, "https://example.test/shared/1")
            self._source(session, shared_asset, "https://example.test/shared/2")

            result = asyncio.run(get_videos(page=1, per_page=20, admin=admin, db=session))

            self.assertEqual(result["total"], 1)
            row = result["videos"][0]
            self.assertEqual(row["media_asset_id"], shared_asset.id)
            self.assertEqual(row["owner_count"], 2)
            self.assertEqual(row["reference_count"], 2)
            self.assertEqual(row["owner_username"], "2 个用户")
            self.assertCountEqual(
                [owner["username"] for owner in row["owners"]],
                ["alice", "bob"],
            )
            self.assertEqual(row["source_count"], 2)
            self.assertCountEqual(
                row["source_urls"],
                ["https://example.test/shared/1", "https://example.test/shared/2"],
            )

    def test_get_videos_time_filter_handles_iso_created_at_strings(self):
        with self.Session() as session:
            admin = self._user(session, "admin", role="admin")
            today_asset = self._asset(session, "Today", "eeeeeeee")
            old_asset = self._asset(
                session,
                "Old",
                "ffffffff",
                created_at=datetime.now(UTC) - timedelta(days=90),
            )

            earlier_result = asyncio.run(
                get_videos(time="earlier", page=1, per_page=20, admin=admin, db=session)
            )
            today_result = asyncio.run(
                get_videos(time="today", page=1, per_page=20, admin=admin, db=session)
            )

            self.assertEqual([row["media_asset_id"] for row in earlier_result["videos"]], [old_asset.id])
            self.assertEqual([row["media_asset_id"] for row in today_result["videos"]], [today_asset.id])

    def test_admin_html_contains_top_navigation_slots(self):
        html = (ROOT / "www/admin/admin.html").read_text(encoding="utf-8")

        for nav_key in ["overview", "media", "users", "invites", "system"]:
            self.assertIn(f'data-admin-nav="{nav_key}"', html)

        for view_id in [
            "overview-view-container",
            "video-view-container",
            "user-view-container",
            "invite-view-container",
            "system-view-container",
        ]:
            self.assertIn(f'id="{view_id}"', html)

    def test_admin_state_defaults_to_overview_navigation(self):
        source = (ROOT / "www/admin/js/state.js").read_text(encoding="utf-8")

        self.assertIn("nav:", source)
        self.assertIn("current: 'overview'", source)
        self.assertNotIn("currentView:", source)

    def test_admin_shell_scripts_use_overview_entry(self):
        admin_js = (ROOT / "www/admin/js/admin.js").read_text(encoding="utf-8")
        events_js = (ROOT / "www/admin/js/events.js").read_text(encoding="utf-8")
        render_js = (ROOT / "www/admin/js/render.js").read_text(encoding="utf-8")
        users_js = (ROOT / "www/admin/js/users.js").read_text(encoding="utf-8")

        self.assertIn("bindAdminShellEvents", admin_js)
        self.assertIn("switchAdminView('overview')", admin_js)
        self.assertIn("[data-admin-nav]", events_js)
        self.assertNotIn("state.currentView", render_js)
        self.assertNotIn("state.currentView", users_js)

    def test_media_view_scripts_expose_asset_details_entry(self):
        render_js = (ROOT / "www/admin/js/render.js").read_text(encoding="utf-8")
        modals_js = (ROOT / "www/admin/js/modals.js").read_text(encoding="utf-8")
        admin_css = (ROOT / "www/admin/css/admin.css").read_text(encoding="utf-8")

        self.assertIn("showMediaDetailsModal", render_js)
        self.assertIn("source_count", render_js)
        self.assertIn("owner_count", render_js)
        self.assertIn("showMediaDetailsModal", modals_js)
        self.assertIn("loop: true", modals_js)
        self.assertIn("video.share_token || video.file_hash", modals_js)
        self.assertIn("navigator.clipboard && typeof navigator.clipboard.writeText === 'function'", modals_js)
        self.assertIn(".detail-hero {", admin_css)

    def test_get_user_library_returns_user_scoped_items(self):
        with self.Session() as session:
            admin = self._user(session, "admin", role="admin")
            alice = self._user(session, "alice")
            bob = self._user(session, "bob")
            alice_asset = self._asset(session, "Alpha", "aaaaaaaa")
            bob_asset = self._asset(session, "Beta", "bbbbbbbb")
            self._item(session, alice, alice_asset)
            self._item(session, bob, bob_asset)

            result = asyncio.run(get_user_library(alice.id, admin=admin, db=session))

            self.assertEqual(result["user"]["username"], "alice")
            self.assertEqual(len(result["items"]), 1)
            self.assertEqual(result["items"][0]["owner_user_id"], alice.id)
            self.assertEqual(result["items"][0]["title"], "Alpha")

    def test_user_view_scripts_expose_library_entry(self):
        users_js = (ROOT / "www/admin/js/users.js").read_text(encoding="utf-8")
        data_js = (ROOT / "www/admin/js/data.js").read_text(encoding="utf-8")
        render_js = (ROOT / "www/admin/js/render.js").read_text(encoding="utf-8")
        modals_js = (ROOT / "www/admin/js/modals.js").read_text(encoding="utf-8")

        self.assertIn("showUserLibraryModal", users_js)
        self.assertIn("loadUserLibrary", users_js)
        self.assertIn("/users/${userId}/library", data_js)
        self.assertIn("owner-search-input", render_js)
        self.assertIn("page-size-select", render_js)
        self.assertIn("showAllOwners", modals_js)
        self.assertIn("user-search-input", users_js)
        self.assertIn("filterUsers", users_js)
        self.assertIn("selectionStart", users_js)
        self.assertIn("focus()", users_js)

    def test_invite_view_scripts_use_top_nav_state(self):
        invites_js = (ROOT / "www/admin/js/invites.js").read_text(encoding="utf-8")

        self.assertIn("state.nav.current === 'invites'", invites_js)
        self.assertIn("switchAdminView('invites')", invites_js)
        self.assertIn("loadInvites(true)", invites_js)

    def test_system_view_scripts_expose_runtime_health_and_cookie_status(self):
        system_js = (ROOT / "www/admin/js/system.js").read_text(encoding="utf-8")
        data_js = (ROOT / "www/admin/js/data.js").read_text(encoding="utf-8")
        render_js = (ROOT / "www/admin/js/render.js").read_text(encoding="utf-8")
        admin_html = (ROOT / "www/admin/admin.html").read_text(encoding="utf-8")

        self.assertIn("loadSystemPage", system_js)
        self.assertIn("renderRuntimeHealth", system_js)
        self.assertIn("/runtime/health", data_js)
        self.assertIn("/cookies/status", data_js)
        self.assertIn("system-runtime-slot", render_js)
        self.assertIn("system-cookie-slot", render_js)
        self.assertIn("/static/admin/js/system.js", admin_html)


if __name__ == "__main__":
    unittest.main()
