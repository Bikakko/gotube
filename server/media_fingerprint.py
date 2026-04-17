"""Media fingerprint helpers shared by migrations and library services."""

from pathlib import Path
import zlib


def fingerprint_file(path: Path) -> str:
    """Return a stable content fingerprint including size."""
    checksum = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            checksum = zlib.crc32(chunk, checksum)
    return f"crc32:{checksum & 0xFFFFFFFF:08x}:{path.stat().st_size}"
