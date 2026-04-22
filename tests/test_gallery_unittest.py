import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from server import gallery


class GalleryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.gallery_dir = self.root / "gallery"
        self.gallery_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _album(self, slug: str, *files: str) -> Path:
        album = self.gallery_dir / slug
        album.mkdir()
        for name in files:
            (album / name).write_bytes(b"image-bytes")
        return album

    def test_list_albums_only_returns_first_level_directories_with_images(self):
        self._album("memes", "001.jpg", "002.png")
        empty = self.gallery_dir / "empty"
        empty.mkdir()
        nested_parent = self._album("nested", "cover.jpg")
        (nested_parent / "child").mkdir()
        (nested_parent / "child" / "deep.jpg").write_bytes(b"x")

        albums = gallery.list_albums(self.gallery_dir)

        self.assertEqual([album["slug"] for album in albums], ["memes", "nested"])
        nested = next(album for album in albums if album["slug"] == "nested")
        self.assertEqual(nested["image_count"], 1)

    def test_list_albums_ignores_non_image_files(self):
        self._album("stickers", "001.txt", "002.md", "003.webp")

        albums = gallery.list_albums(self.gallery_dir)

        self.assertEqual(len(albums), 1)
        self.assertEqual(albums[0]["image_count"], 1)
        self.assertEqual(albums[0]["cover_name"], "003.webp")

    def test_get_album_images_returns_sorted_whitelisted_images(self):
        self._album("reactions", "b.png", "a.jpg", "note.txt", "c.gif")

        album = gallery.get_album(self.gallery_dir, "reactions")

        self.assertEqual([image["name"] for image in album["images"]], ["a.jpg", "b.png", "c.gif"])

    def test_invalid_slug_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            gallery.get_album(self.gallery_dir, "../secret")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_invalid_image_name_is_rejected(self):
        self._album("memes", "001.jpg")
        with self.assertRaises(HTTPException) as ctx:
            gallery.resolve_image_path(self.gallery_dir, "memes", "../001.jpg")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_unknown_album_or_file_returns_not_found(self):
        self._album("memes", "001.jpg")

        with self.assertRaises(HTTPException) as album_ctx:
            gallery.get_album(self.gallery_dir, "missing")
        self.assertEqual(album_ctx.exception.status_code, 404)

        with self.assertRaises(HTTPException) as file_ctx:
            gallery.resolve_image_path(self.gallery_dir, "memes", "missing.jpg")
        self.assertEqual(file_ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
