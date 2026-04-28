import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect, text

from server.db import Base, User
from server.migrations import run_v4_migrations


class V4MigrationTests(unittest.TestCase):
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

    def test_migration_adds_v4_schema_and_converts_readonly_users(self):
        with self.Session() as session:
            session.add(User(username="viewer", password_hash="x", role="readonly", is_active=True))
            session.commit()

        run_v4_migrations(self.engine, self.download_dir)

        with self.Session() as session:
            viewer = session.query(User).filter_by(username="viewer").one()
            self.assertEqual(viewer.role, "user")
            self.assertEqual(viewer.display_name, "viewer")
            self.assertEqual(viewer.display_name_key, "viewer")
            self.assertEqual(viewer.storage_used_bytes, 0)
            self.assertIsNone(viewer.storage_quota_mb)

            inspector = inspect(self.engine).get_table_names()
            self.assertIn("schema_migrations", inspector)
            self.assertIn("media_assets", inspector)
            self.assertIn("user_video_items", inspector)
            self.assertIn("invite_codes", inspector)
            columns = {column["name"] for column in inspect(self.engine).get_columns("users")}
            self.assertIn("display_name", columns)
            self.assertIn("display_name_key", columns)
            versions = session.execute(text("SELECT version FROM schema_migrations ORDER BY version")).scalars().all()
            self.assertEqual(versions, [4, 5])

    def test_migration_indexes_legacy_videos_once_without_moving_files(self):
        video_dir = self.download_dir / "Example_abcd1234"
        video_dir.mkdir()
        video_file = video_dir / "abcd1234.mp4"
        video_file.write_bytes(b"video bytes")
        (video_dir / "meta.json").write_text(
            json.dumps(
                {
                    "title": "Example",
                    "webpage_url": "https://example.test/video",
                    "duration": 12.5,
                    "thumbnail": "thumb.jpg",
                    "file_hash": "abcd1234",
                }
            ),
            encoding="utf-8",
        )
        (self.download_dir / "temp_guest").mkdir()
        guest_file = self.download_dir / "temp_guest" / "ignored.mp4"
        guest_file.write_bytes(b"guest bytes")

        run_v4_migrations(self.engine, self.download_dir)
        run_v4_migrations(self.engine, self.download_dir)

        with self.Session() as session:
            rows = session.execute(
                text("SELECT fingerprint, file_hash, filepath, title, size_bytes FROM media_assets")
            ).all()
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.file_hash, "abcd1234")
            self.assertEqual(row.title, "Example")
            self.assertEqual(row.size_bytes, len(b"video bytes"))
            self.assertEqual(Path(row.filepath), video_file.resolve())
            self.assertTrue(video_file.exists())
            self.assertTrue(guest_file.exists())

            item_count = session.execute(text("SELECT COUNT(*) FROM user_video_items")).scalar_one()
            self.assertEqual(item_count, 0)

            sources = session.execute(
                text("SELECT source_url, normalized_url, platform FROM media_sources")
            ).all()
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0].source_url, "https://example.test/video")
            self.assertEqual(sources[0].normalized_url, "https://example.test/video")

    def test_migration_backfills_sources_for_existing_v4_assets(self):
        with self.engine.begin() as conn:
            now = "2026-04-17T00:00:00+00:00"
            conn.execute(
                text(
                    """
                    INSERT INTO media_assets (
                        fingerprint, file_hash, filename, filepath, size_bytes, title,
                        thumbnail, duration, source_url, meta_json, created_at, last_seen_at
                    )
                    VALUES (
                        'crc32:00000000:1', 'abcd1234', 'a.mp4', 'a.mp4', 1, 'A',
                        '', NULL, 'https://example.test/video?b=2&a=1', '{}', :now, :now
                    )
                    """
                ),
                {"now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (4, 'v4_media_assets_and_invites', :now)"
                ),
                {"now": now},
            )

        run_v4_migrations(self.engine, self.download_dir)

        with self.Session() as session:
            sources = session.execute(text("SELECT normalized_url FROM media_sources")).all()
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0].normalized_url, "https://example.test/video?a=1&b=2")

    def test_migration_backfills_missing_display_name_for_existing_users(self):
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE users SET display_name = '', display_name_key = ''"))
        with self.Session() as session:
            session.add(User(username="alpha", password_hash="x", role="user", is_active=True))
            session.commit()
            session.execute(text("UPDATE users SET display_name = '', display_name_key = '' WHERE username = 'alpha'"))
            session.commit()

        run_v4_migrations(self.engine, self.download_dir)

        with self.Session() as session:
            user = session.query(User).filter_by(username="alpha").one()
            self.assertEqual(user.display_name, "alpha")
            self.assertEqual(user.display_name_key, "alpha")


if __name__ == "__main__":
    unittest.main()
