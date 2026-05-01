from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import quote

import anyio
from fastapi import Request
from fastapi.responses import FileResponse, Response, StreamingResponse


def _content_disposition(disposition_type: str, filename: str) -> str:
    cleaned = "".join(ch for ch in str(filename or "download") if ch not in "\r\n")
    fallback = "".join(
        ch if 32 <= ord(ch) < 127 and ch not in {'"', "\\", ";"} else "_"
        for ch in cleaned
    ).strip(" .")
    if not fallback:
        fallback = "download"
    encoded = quote(cleaned or fallback, safe="")
    return f'{disposition_type}; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'


def _parse_range_header(range_header: str, file_size: int) -> tuple[int, int] | None:
    if not range_header.startswith("bytes="):
        return None
    range_spec = range_header[6:].strip()
    if "," in range_spec:
        return None
    start_text, _, end_text = range_spec.partition("-")
    if not start_text and not end_text:
        return None

    try:
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else file_size - 1
        else:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                return None
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
    except ValueError:
        return None

    if start < 0 or end < start or start >= file_size:
        return None
    end = min(end, file_size - 1)
    return start, end


async def _iter_file_range(path: Path, start: int, end: int, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
    remaining = end - start + 1
    async with await anyio.open_file(path, mode="rb") as file:
        await file.seek(start)
        while remaining > 0:
            chunk = await file.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def build_video_stream_response(
    request: Request,
    path: Path,
    *,
    filename: str,
    media_type: str = "video/mp4",
) -> Response:
    file_size = path.stat().st_size
    common_headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": _content_disposition("inline", filename),
    }
    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(path, media_type=media_type, headers=common_headers)

    byte_range = _parse_range_header(range_header, file_size)
    if byte_range is None:
        return Response(
            status_code=416,
            headers={
                **common_headers,
                "Content-Range": f"bytes */{file_size}",
            },
        )

    start, end = byte_range
    content_length = end - start + 1
    return StreamingResponse(
        _iter_file_range(path, start, end),
        status_code=206,
        media_type=media_type,
        headers={
            **common_headers,
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
        },
    )
