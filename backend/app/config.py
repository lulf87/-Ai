from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
REGULATION_UPLOAD_DIR = DATA_DIR / "regulations"
EXTRACTED_TEXT_DIR = DATA_DIR / "extracted_text"
REPORT_DIR = BASE_DIR / "reports" / "generated"
DATABASE_PATH = Path(os.getenv("REG_REVIEW_DATABASE_PATH", DATA_DIR / "app.sqlite3")).expanduser()
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BASE_DIR / DATABASE_PATH
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"


def ensure_runtime_dirs() -> None:
    for path in (
        DATA_DIR,
        UPLOAD_DIR,
        REGULATION_UPLOAD_DIR,
        EXTRACTED_TEXT_DIR,
        REPORT_DIR,
        DATABASE_PATH.parent,
    ):
        path.mkdir(parents=True, exist_ok=True)
