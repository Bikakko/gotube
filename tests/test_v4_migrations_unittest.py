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
            self.assertEqual(viewer.storage_used_bytes, 0)
            self.assertIsNone(viewer.storage_quota_mb)

            inspector = inspect(self.engine).get_table_names()
            self.assertIn("schema_migrations", inspector)
            self.assertIn("media_assets", inspector)
            self.assertIn("user_video_items", inspector)
            self.assertIn("invite_codes", inspector)

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


if __name__ == "__main__":
    unittest.main()
