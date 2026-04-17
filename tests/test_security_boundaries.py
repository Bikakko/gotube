from pathlib import Path

import pytest
from fastapi import HTTPException

from server.path_utils import resolve_inside
from server.security import validate_guest_session_id, validate_hash_id


def test_validate_guest_session_id_accepts_browser_generated_format():
    assert validate_guest_session_id("guest_l2abc123_abcd123") == "guest_l2abc123_abcd123"


@pytest.mark.parametrize(
    "session_id",
    [
        "",
        "guest",
        "guest_abc",
        "../guest_l2abc123_abcd123",
        "guest_l2abc123_../../x",
        "guest_l2abc123_abcd/ef",
        "guest_l2abc123_abcd\\ef",
    ],
)
def test_validate_guest_session_id_rejects_path_like_values(session_id):
    with pytest.raises(HTTPException):
        validate_guest_session_id(session_id)


def test_validate_hash_id_requires_full_crc32_hex():
    assert validate_hash_id("ABCDEF12") == "abcdef12"


@pytest.mark.parametrize("hash_id", ["", "a", "abcdef1", "abcdef123", "zzzzzzzz", "../abcd1234"])
def test_validate_hash_id_rejects_short_or_non_hex_values(hash_id):
    with pytest.raises(HTTPException):
        validate_hash_id(hash_id)


def test_resolve_inside_returns_child_path(tmp_path: Path):
    assert resolve_inside(tmp_path, "guest_l2abc123_abcd123").parent == tmp_path.resolve()


def test_resolve_inside_rejects_parent_traversal(tmp_path: Path):
    with pytest.raises(HTTPException):
        resolve_inside(tmp_path, "..", "outside")
