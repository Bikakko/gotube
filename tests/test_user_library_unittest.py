import asyncio
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.api import download_my_video, update_my_video_share
from server.db import Base, User
from server.models import UpdateShareRequest
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

    def _user(self, session, username: str) -> User:
        user = User(username=username, password_hash="x", role="user", is_active=True)
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


if __name__ == "__main__":
    unittest.main()
