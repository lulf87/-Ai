from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import UploadFile

from backend.app.config import REGULATION_UPLOAD_DIR, UPLOAD_DIR


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return suffix if suffix else ".bin"


def save_upload(project_id: int, upload: UploadFile) -> tuple[Path, str]:
    project_dir = UPLOAD_DIR / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    with NamedTemporaryFile(delete=False) as temporary:
        shutil.copyfileobj(upload.file, temporary)
        temp_path = Path(temporary.name)

    digest = sha256_file(temp_path)
    target = project_dir / f"{digest}{safe_suffix(upload.filename or '')}"
    if not target.exists():
        shutil.move(str(temp_path), target)
    else:
        temp_path.unlink(missing_ok=True)
    return target, digest


def save_regulation_upload(upload: UploadFile) -> tuple[Path, str]:
    REGULATION_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with NamedTemporaryFile(delete=False) as temporary:
        shutil.copyfileobj(upload.file, temporary)
        temp_path = Path(temporary.name)

    digest = sha256_file(temp_path)
    target = REGULATION_UPLOAD_DIR / f"{digest}{safe_suffix(upload.filename or '')}"
    if not target.exists():
        shutil.move(str(temp_path), target)
    else:
        temp_path.unlink(missing_ok=True)
    return target, digest


def save_regulation_bytes(filename: str, content: bytes) -> tuple[Path, str]:
    REGULATION_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()
    target = REGULATION_UPLOAD_DIR / f"{digest}{safe_suffix(filename)}"
    if not target.exists():
        target.write_bytes(content)
    return target, digest
