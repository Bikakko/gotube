import asyncio
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.api import (
    _register_transferred_guest_files,
    download_my_video,
    download_shared_video,
    get_guest_download_count,
    get_my_quota,
    get_my_videos,
    get_shared_video_info,
    update_my_video_share,
)
from server.db import Base, User, UserVideoItem
from server.downloader import DownloadTask
from server.models import UpdateShareRequest
from server.queue_manager import QueueManager
from server.video_library import (
    get_user_video_asset_for_download,
    register_completed_file,
    resolve_share_token,
    set_user_video_share_enabled,
)


class UserLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.download_dir = self.root / "downloads"
        self.download_dir.mkdir()
        self.engine = create_engine(f"sqlite:///{self.root / 'user-library.db'}")
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def _user(self, session, username: str, role: str = "user") -> User:
        user = User(username=username, password_hash="x", role=role, is_active=True)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    def _video_file(self, dirname: str, filename: str, content: bytes = b"video") -> Path:
        video_dir = self.download_dir / dirname
        video_dir.mkdir()
        video_file = video_dir / filename
        video_file.write_bytes(content)
        return video_file

    def _write_meta(self, video_file: Path, *, url: str = "https://example.test/a", title: str = "Alpha") -> None:
        (video_file.parent / "meta.json").write_text(
            (
                '{"title": "%s", "url": "%s", "file_hash": "%s", '
                '"thumbnail": "", "duration": 12}'
            )
            % (title, url, video_file.stem),
            encoding="utf-8",
        )

    def test_user_can_toggle_own_share_and_token_resolution_follows_state(self):
        with self.Session() as session:
            alice = self._user(session, "alice")
            video_file = self._video_file("Alpha_aaaaaaaa", "aaaaaaaa.mp4")
            item = register_completed_file(
                session,
                owner_user_id=alice.id,
                filepath=video_file,
                download_dir=self.download_dir,
                source_url="https://example.test/a",
                title="Alpha",
                file_hash="aaaaaaaa",
            )

            disabled = set_user_video_share_enabled(session, alice, item.id, False)
            session.commit()

            self.assertFalse(disabled["share_enabled"])
            self.assertIsNone(resolve_share_token(session, item.share_token))

            enabled = set_user_video_share_enabled(session, alice, item.id, True)
            session.commit()

            self.assertTrue(enabled["share_enabled"])
            self.assertIsNotNone(resolve_share_token(session, item.share_token))

    def test_user_cannot_toggle_or_download_another_users_item(self):
        with self.Session() as session:
            alice = self._user(session, "alice")
            bob = self._user(session, "bob")
            video_file = self._video_file("Alpha_aaaaaaaa", "aaaaaaaa.mp4")
            item = register_completed_file(
                session,
                owner_user_id=alice.id,
                filepath=video_file,
                download_dir=self.download_dir,
                source_url="https://example.test/a",
                title="Alpha",
                file_hash="aaaaaaaa",
            )

            with self.assertRaises(HTTPException) as toggle_ctx:
                set_user_video_share_enabled(session, bob, item.id, False)
            self.assertEqual(toggle_ctx.exception.status_code, 403)

            with self.assertRaises(HTTPException) as download_ctx:
                get_user_video_asset_for_download(session, bob, item.id)
            self.assertEqual(download_ctx.exception.status_code, 403)

    def test_api_download_and_share_routes_enforce_current_user(self):
        with self.Session() as session:
            alice = self._user(session, "alice")
            bob = self._user(session, "bob")
            video_file = self._video_file("Alpha_aaaaaaaa", "aaaaaaaa.mp4")
            item = register_completed_file(
                session,
                owner_user_id=alice.id,
                filepath=video_file,
                download_dir=self.download_dir,
                source_url="https://example.test/a",
                title="Alpha",
                file_hash="aaaaaaaa",
            )

            response = asyncio.run(download_my_video(item.id, current_user=alice, db=session))
            self.assertEqual(Path(response.path), video_file)

            result = asyncio.run(
                update_my_video_share(
                    item.id,
                    UpdateShareRequest(share_enabled=False),
                    current_user=alice,
                    db=session,
                )
            )
            self.assertFalse(result["share_enabled"])

            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(download_my_video(item.id, current_user=bob, db=session))
            self.assertEqual(ctx.exception.status_code, 403)

    def test_me_library_routes_reject_admin_users(self):
        with self.Session() as session:
            admin = self._user(session, "admin", role="admin")

            with self.assertRaises(HTTPException) as quota_ctx:
                asyncio.run(get_my_quota(current_user=admin, db=session))
            self.assertEqual(quota_ctx.exception.status_code, 403)

            with self.assertRaises(HTTPException) as videos_ctx:
                asyncio.run(get_my_videos(current_user=admin, db=session))
            self.assertEqual(videos_ctx.exception.status_code, 403)

    def test_guest_transfer_registration_creates_user_video_item_and_updates_task(self):
        class FakeTask:
            def __init__(self):
                self.filename = "Alpha_aaaaaaaa/aaaaaaaa.mp4"
                self.user_video_item_id = None
                self.media_asset_id = None
                self.share_token = ""
                self.file_hash = ""

        class FakeQueue:
            def __init__(self, task):
                self.task = task

            def get_client_tasks(self, client_id):
                return [self.task]

        with self.Session() as session:
            alice = self._user(session, "alice")
            video_file = self._video_file("Alpha_aaaaaaaa", "aaaaaaaa.mp4")
            self._write_meta(video_file)
            task = FakeTask()
            result = {
                "transferred_files": ["Alpha_aaaaaaaa/aaaaaaaa.mp4"],
                "updated_tasks": [{"task_id": "t1", "filename": "Alpha_aaaaaaaa/aaaaaaaa.mp4"}],
            }

            updated = _register_transferred_guest_files(
                session,
                current_user=alice,
                transfer_result=result,
                download_dir=self.download_dir,
                qm=FakeQueue(task),
                client_id="client-1",
            )

            self.assertEqual(updated["registered_count"], 1)
            self.assertEqual(session.query(UserVideoItem).count(), 1)
            self.assertIsNotNone(task.user_video_item_id)
            self.assertEqual(task.filename, "Alpha_aaaaaaaa/aaaaaaaa.mp4")
            self.assertEqual(updated["updated_tasks"][0]["user_video_item_id"], task.user_video_item_id)
            self.assertTrue(updated["updated_tasks"][0]["share_token"])

    def test_guest_count_includes_duplicate_placeholder_tasks(self):
        class FakeTask:
            is_guest = True
            session_id = "guest_l2abc123_abcd123"
            filename = "temp_guest/guest_l2abc123_abcd123/DUPLICATE/Alpha_aaaaaaaa/aaaaaaaa.mp4"

        class FakeDownloader:
            def get_guest_download_count(self, session_id):
                return 0

        class FakeQueue:
            downloader = FakeDownloader()

            def get_client_tasks(self, client_id):
                return [FakeTask()]

        result = asyncio.run(
            get_guest_download_count(
                "guest_l2abc123_abcd123",
                client_id="client-1",
                qm=FakeQueue(),
            )
        )

        self.assertEqual(result["count"], 1)

    def test_failed_library_registration_removes_newly_downloaded_file(self):
        class FakeDownloader:
            def __init__(self, download_dir):
                self.download_dir = download_dir
                self.file_cache_invalidated = False
                self.hash_cache_invalidated = False

            def invalidate_file_index_cache(self):
                self.file_cache_invalidated = True

            def invalidate_hash_index(self):
                self.hash_cache_invalidated = True

        video_file = self._video_file("TooLarge_aaaaaaaa", "aaaaaaaa.mp4")
        task = DownloadTask("t1", "https://example.test/a", "client-1")
        task.filepath = str(video_file)
        task.is_duplicate = False
        qm = QueueManager(FakeDownloader(self.download_dir))

        qm._delete_failed_library_download(task)

        self.assertFalse(video_file.exists())
        self.assertFalse(video_file.parent.exists())
        self.assertTrue(qm.downloader.file_cache_invalidated)
        self.assertTrue(qm.downloader.hash_cache_invalidated)

    def test_share_info_and_download_work_with_share_token_and_preserve_extension(self):
        with self.Session() as session:
            alice = self._user(session, "alice")
            video_file = self._video_file("Alpha_aaaaaaaa", "aaaaaaaa.mp4")
            item = register_completed_file(
                session,
                owner_user_id=alice.id,
                filepath=video_file,
                download_dir=self.download_dir,
                source_url="https://example.test/a",
                title="Alpha Title",
                file_hash="aaaaaaaa",
            )

            info = asyncio.run(get_shared_video_info(item.share_token, db=session))
            response = asyncio.run(download_shared_video(item.share_token, db=session))

            self.assertEqual(info["share_token"], item.share_token)
            self.assertEqual(info["title"], "Alpha Title")
            self.assertEqual(Path(response.path), video_file)
            disposition = response.headers["content-disposition"]
            self.assertIn(".mp4", disposition)
            self.assertIn("Alpha", disposition)


if __name__ == "__main__":
    unittest.main()
