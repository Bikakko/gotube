import asyncio
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.admin_api import get_videos, list_users, update_user
from server.db import Base, MediaAsset, User, UserVideoItem
from server.models import UpdateUserRequest


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

    def _asset(self, session, title: str, file_hash: str, size: int = 128) -> MediaAsset:
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
            created_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
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


if __name__ == "__main__":
    unittest.main()
