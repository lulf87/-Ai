from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
EXTRACTED_TEXT_DIR = DATA_DIR / "extracted_text"
REPORT_DIR = BASE_DIR / "reports" / "generated"
DATABASE_PATH = DATA_DIR / "app.sqlite3"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"


def ensure_runtime_dirs() -> None:
    for path in (DATA_DIR, UPLOAD_DIR, EXTRACTED_TEXT_DIR, REPORT_DIR):
        path.mkdir(parents=True, exist_ok=True)

