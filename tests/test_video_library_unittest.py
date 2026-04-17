import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from server.db import Base, MediaAsset, MediaSource, User, UserVideoItem
from server.quota import get_effective_quota_bytes, refresh_user_storage_usage
from server.video_library import (
    admin_delete_media_asset,
    create_item_from_existing_source,
    delete_user_video_item,
    get_asset_from_existing_source,
    normalize_source_url,
    register_completed_file,
    resolve_share_token,
)


class VideoLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.download_dir = self.root / "downloads"
        self.download_dir.mkdir()
        self.engine = create_engine(f"sqlite:///{self.root / 'gotube.db'}")
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def _user(self, session, username: str, role: str = "user", quota_mb: int | None = None):
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

    def _video_file(self, dirname: str, filename: str, content: bytes = b"video bytes") -> Path:
        video_dir = self.download_dir / dirname
        video_dir.mkdir()
        video_file = video_dir / filename
        video_file.write_bytes(content)
        return video_file

    def test_quota_counts_user_library_even_when_media_is_shared(self):
        with self.Session() as session:
            alice = self._user(session, "alice", quota_mb=1)
            bob = self._user(session, "bob", quota_mb=1)
            video_file = self._video_file("Example_abcd1234", "abcd1234.mp4", b"same-video")

            first = register_completed_file(
                session,
                owner_user_id=alice.id,
                filepath=video_file,
                download_dir=self.download_dir,
                source_url="https://example.test/a",
                title="Example",
                file_hash="abcd1234",
            )
            second = register_completed_file(
                session,
                owner_user_id=bob.id,
                filepath=video_file,
                download_dir=self.download_dir,
                source_url="https://example.test/a",
                title="Example",
                file_hash="abcd1234",
            )

            self.assertEqual(first.media_asset_id, second.media_asset_id)
            self.assertEqual(session.query(MediaAsset).count(), 1)
            self.assertEqual(session.query(UserVideoItem).count(), 2)
            self.assertEqual(refresh_user_storage_usage(session, alice.id), len(b"same-video"))
            self.assertEqual(refresh_user_storage_usage(session, bob.id), len(b"same-video"))
            self.assertEqual(get_effective_quota_bytes(alice), 1024 * 1024)

    def test_quota_allows_final_video_to_exceed_limit_then_blocks_next_item(self):
        with self.Session() as session:
            alice = self._user(session, "alice", quota_mb=1)
            large_file = self._video_file(
                "Large_abcd1234",
                "abcd1234.mp4",
                b"x" * (1024 * 1024 + 1),
            )

            item = register_completed_file(
                session,
                owner_user_id=alice.id,
                filepath=large_file,
                download_dir=self.download_dir,
                source_url="https://example.test/large",
                title="Large",
                file_hash="abcd1234",
            )

            self.assertIsNotNone(item.id)
            self.assertGreater(refresh_user_storage_usage(session, alice.id), get_effective_quota_bytes(alice))

            next_file = self._video_file("Next_deadbeef", "deadbeef.mp4", b"next")
            with self.assertRaisesRegex(ValueError, "容量不足"):
                register_completed_file(
                    session,
                    owner_user_id=alice.id,
                    filepath=next_file,
                    download_dir=self.download_dir,
                    source_url="https://example.test/next",
                    title="Next",
                    file_hash="deadbeef",
                )

    def test_existing_source_reuse_requires_live_media_file_and_creates_user_item(self):
        with self.Session() as session:
            alice = self._user(session, "alice")
            bob = self._user(session, "bob")
            video_file = self._video_file("Example_abcd1234", "abcd1234.mp4")
            register_completed_file(
                session,
                owner_user_id=alice.id,
                filepath=video_file,
                download_dir=self.download_dir,
                source_url="https://example.test/a",
                title="Example",
                file_hash="abcd1234",
            )

            reused = create_item_from_existing_source(session, bob.id, "https://example.test/a")
            existing_asset = get_asset_from_existing_source(session, "https://example.test/a")

            self.assertIsNotNone(reused)
            self.assertIsNotNone(existing_asset)
            self.assertEqual(session.query(MediaAsset).count(), 1)
            self.assertEqual(session.query(UserVideoItem).filter_by(owner_user_id=bob.id).count(), 1)

            video_file.unlink()
            stale = create_item_from_existing_source(session, bob.id, "https://example.test/a")
            stale_asset = get_asset_from_existing_source(session, "https://example.test/a")
            self.assertIsNone(stale)
            self.assertIsNone(stale_asset)

    def test_source_url_normalization_drops_playback_progress_params(self):
        self.assertEqual(
            normalize_source_url("https://www.youtube.com/watch?v=abc&t=42s"),
            normalize_source_url("https://www.youtube.com/watch?v=abc"),
        )
        self.assertEqual(
            normalize_source_url("https://www.bilibili.com/video/BV123?vd_source=x&p=2"),
            "https://www.bilibili.com/video/BV123?p=2",
        )

    def test_existing_source_reuse_ignores_playback_progress_params(self):
        with self.Session() as session:
            alice = self._user(session, "alice")
            bob = self._user(session, "bob")
            video_file = self._video_file("Example_abcd1234", "abcd1234.mp4")
            register_completed_file(
                session,
                owner_user_id=alice.id,
                filepath=video_file,
                download_dir=self.download_dir,
                source_url="https://www.youtube.com/watch?v=abc",
                title="Example",
                file_hash="abcd1234",
            )

            reused = create_item_from_existing_source(
                session,
                bob.id,
                "https://www.youtube.com/watch?v=abc&t=42s",
            )

            self.assertIsNotNone(reused)
            self.assertEqual(session.query(MediaAsset).count(), 1)
            self.assertEqual(session.query(UserVideoItem).filter_by(owner_user_id=bob.id).count(), 1)

    def test_new_url_is_added_when_download_fingerprints_to_existing_media(self):
        with self.Session() as session:
            alice = self._user(session, "alice")
            bob = self._user(session, "bob")
            first_file = self._video_file("First_abcd1234", "abcd1234.mp4", b"same")
            second_file = self._video_file("Second_deadbeef", "deadbeef.mp4", b"same")

            register_completed_file(
                session,
                owner_user_id=alice.id,
                filepath=first_file,
                download_dir=self.download_dir,
                source_url="https://example.test/first",
                title="First",
                file_hash="abcd1234",
            )
            item = register_completed_file(
                session,
                owner_user_id=bob.id,
                filepath=second_file,
                download_dir=self.download_dir,
                source_url="https://mirror.test/second",
                title="Second",
                file_hash="deadbeef",
            )

            self.assertFalse(second_file.exists())
            self.assertEqual(session.query(MediaAsset).count(), 1)
            self.assertEqual(item.display_title, "Second")
            urls = {row.source_url for row in session.query(MediaSource).all()}
            self.assertEqual(urls, {"https://example.test/first", "https://mirror.test/second"})

    def test_user_delete_only_removes_physical_file_after_last_reference(self):
        with self.Session() as session:
            alice = self._user(session, "alice")
            bob = self._user(session, "bob")
            video_file = self._video_file("Example_abcd1234", "abcd1234.mp4")
            alice_item = register_completed_file(
                session,
                owner_user_id=alice.id,
                filepath=video_file,
                download_dir=self.download_dir,
                source_url="https://example.test/a",
                title="Example",
                file_hash="abcd1234",
            )
            bob_item = register_completed_file(
                session,
                owner_user_id=bob.id,
                filepath=video_file,
                download_dir=self.download_dir,
                source_url="https://example.test/a",
                title="Example",
                file_hash="abcd1234",
            )

            first_delete = delete_user_video_item(session, alice, alice_item.id, self.download_dir)

            self.assertFalse(first_delete["physical_deleted"])
            self.assertTrue(video_file.exists())
            self.assertIsNone(resolve_share_token(session, alice_item.share_token))
            self.assertIsNotNone(resolve_share_token(session, bob_item.share_token))

            second_delete = delete_user_video_item(session, bob, bob_item.id, self.download_dir)

            self.assertTrue(second_delete["physical_deleted"])
            self.assertFalse(video_file.exists())
            self.assertEqual(session.query(MediaAsset).count(), 0)
            self.assertEqual(session.query(MediaSource).count(), 0)

    def test_admin_maintenance_delete_removes_all_items_sources_and_file(self):
        with self.Session() as session:
            admin = self._user(session, "admin", role="admin")
            alice = self._user(session, "alice")
            bob = self._user(session, "bob")
            video_file = self._video_file("Example_abcd1234", "abcd1234.mp4")
            item = register_completed_file(
                session,
                owner_user_id=alice.id,
                filepath=video_file,
                download_dir=self.download_dir,
                source_url="https://example.test/a",
                title="Example",
                file_hash="abcd1234",
            )
            register_completed_file(
                session,
                owner_user_id=bob.id,
                filepath=video_file,
                download_dir=self.download_dir,
                source_url="https://example.test/a",
                title="Example",
                file_hash="abcd1234",
            )

            result = admin_delete_media_asset(session, admin, item.media_asset_id, self.download_dir)

            self.assertEqual(result["affected_items"], 2)
            self.assertFalse(video_file.exists())
            self.assertEqual(session.query(MediaAsset).count(), 0)
            self.assertEqual(session.query(MediaSource).count(), 0)
            self.assertEqual(session.query(UserVideoItem).count(), 0)
            self.assertEqual(refresh_user_storage_usage(session, alice.id), 0)
            self.assertEqual(refresh_user_storage_usage(session, bob.id), 0)


if __name__ == "__main__":
    unittest.main()
