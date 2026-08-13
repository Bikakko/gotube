"""Media fingerprint helpers shared by migrations and library services."""

from pathlib import Path
import hashlib


def fingerprint_file(path: Path) -> str:
    """Return a stable SHA-256 content fingerprint including size.

    Uses the first 128 bits (32 hex chars) of SHA-256, which is strong enough
    for dedup while fitting the media_assets.fingerprint VARCHAR(64) column.
    """
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()[:32]}:{path.stat().st_size}"
