import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def workspace_tempdir():
    root = Path(".tmp_tests").resolve()
    root.mkdir(exist_ok=True)
    path = root / f"tmp-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)
