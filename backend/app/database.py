from collections.abc import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from backend.app.config import DATABASE_URL, ensure_runtime_dirs
from backend.app.regulations import seed_preset_regulations


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    ensure_runtime_dirs()
    SQLModel.metadata.create_all(engine)
    run_lightweight_migrations()
    with Session(engine) as session:
        seed_preset_regulations(session)


def reset_database() -> None:
    ensure_runtime_dirs()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def run_lightweight_migrations() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as connection:
        finding_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(finding)")).fetchall()
        }
        if finding_columns and "source_type" not in finding_columns:
            connection.execute(
                text("ALTER TABLE finding ADD COLUMN source_type VARCHAR DEFAULT 'rule'")
            )
        if finding_columns and "ai_rationale" not in finding_columns:
            connection.execute(
                text("ALTER TABLE finding ADD COLUMN ai_rationale VARCHAR DEFAULT ''")
            )
        finding_text_columns = {
            "regulation_title": "VARCHAR DEFAULT ''",
            "regulation_attachment_filename": "VARCHAR DEFAULT ''",
            "regulation_attachment_sha256": "VARCHAR DEFAULT ''",
            "regulation_evidence_locator": "VARCHAR DEFAULT ''",
            "regulation_evidence_quote": "VARCHAR DEFAULT ''",
        }
        for column, definition in finding_text_columns.items():
            if finding_columns and column not in finding_columns:
                connection.execute(text(f"ALTER TABLE finding ADD COLUMN {column} {definition}"))
        if finding_columns and "regulation_attachment_id" not in finding_columns:
            connection.execute(
                text("ALTER TABLE finding ADD COLUMN regulation_attachment_id INTEGER")
            )
        if finding_columns:
            connection.execute(
                text(
                    "UPDATE finding SET review_status = 'confirmed' "
                    "WHERE COALESCE(source_type, 'rule') = 'rule' "
                    "AND review_status IN ('pending', '', 'pending_review')"
                )
            )

        regulation_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(regulationrecord)")).fetchall()
        }
        if not regulation_columns:
            return
        text_columns = {
            "attachment_url": "VARCHAR DEFAULT ''",
            "source_type": "VARCHAR DEFAULT 'manual'",
            "source_content_sha256": "VARCHAR DEFAULT ''",
            "source_note": "VARCHAR DEFAULT ''",
            "device_scope": "VARCHAR DEFAULT ''",
            "stored_path": "VARCHAR DEFAULT ''",
            "text_preview": "VARCHAR DEFAULT ''",
        }
        json_columns = {
            "source_files": "JSON DEFAULT '[]'",
            "coverage_classes": "JSON DEFAULT '[]'",
        }
        integer_columns = {"segment_count": "INTEGER DEFAULT 0"}
        for column, definition in {**text_columns, **json_columns, **integer_columns}.items():
            if column not in regulation_columns:
                connection.execute(
                    text(f"ALTER TABLE regulationrecord ADD COLUMN {column} {definition}")
                )

        segment_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(regulationtextsegment)")).fetchall()
        }
        if segment_columns and "attachment_id" not in segment_columns:
            connection.execute(
                text("ALTER TABLE regulationtextsegment ADD COLUMN attachment_id INTEGER")
            )


def get_session() -> Generator[Session, None, None]:
    init_db()
    with Session(engine) as session:
        yield session
