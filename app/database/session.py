"""
Database session management supporting offline local SQLite and online backend sync.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.db_models import Base

engine = create_engine(
    settings.SQLITE_DB_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.SQLITE_DB_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Columns added to `performances` after the initial schema shipped. SQLite has no online
# migration tooling wired up here, so we add any missing columns idempotently on startup.
# (Existing rows keep 0.0 until the recompute utility / next assessment rebuilds them.)
_PERFORMANCE_ADDED_COLUMNS = {
    "flexibility_score": "FLOAT NOT NULL DEFAULT 0.0",
    "body_composition_score": "FLOAT NOT NULL DEFAULT 0.0",
}


def _run_lightweight_migrations():
    """Add newly-introduced columns to existing tables without dropping data."""
    inspector = inspect(engine)
    if "performances" not in inspector.get_table_names():
        return  # create_all() will build it with the current schema
    existing = {col["name"] for col in inspector.get_columns("performances")}
    with engine.begin() as conn:
        for name, ddl in _PERFORMANCE_ADDED_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE performances ADD COLUMN {name} {ddl}"))


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
