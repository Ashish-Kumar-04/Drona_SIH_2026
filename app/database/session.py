"""
Database session management supporting offline local SQLite and online backend sync.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.db_models import Base

engine = create_engine(
    settings.SQLITE_DB_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.SQLITE_DB_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
