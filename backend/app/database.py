from collections.abc import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from backend.app.config import DATABASE_URL, ensure_runtime_dirs


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    ensure_runtime_dirs()
    SQLModel.metadata.create_all(engine)
    run_lightweight_migrations()


def reset_database() -> None:
    ensure_runtime_dirs()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def run_lightweight_migrations() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as connection:
        existing = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(finding)")).fetchall()
        }
        if not existing:
            return
        if "source_type" not in existing:
            connection.execute(
                text("ALTER TABLE finding ADD COLUMN source_type VARCHAR DEFAULT 'rule'")
            )
        if "ai_rationale" not in existing:
            connection.execute(
                text("ALTER TABLE finding ADD COLUMN ai_rationale VARCHAR DEFAULT ''")
            )
        connection.execute(
            text(
                "UPDATE finding SET review_status = 'confirmed' "
                "WHERE COALESCE(source_type, 'rule') = 'rule' "
                "AND review_status IN ('pending', '', 'pending_review')"
            )
        )


def get_session() -> Generator[Session, None, None]:
    init_db()
    with Session(engine) as session:
        yield session
