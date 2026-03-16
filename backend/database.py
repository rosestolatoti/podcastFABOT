from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
import os
import logging
from pathlib import Path
from backend.config import settings

logger = logging.getLogger(__name__)

Path(settings.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.DATABASE_PATH}",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from backend import models
    Base.metadata.create_all(bind=engine)
    logger.info(f"Banco de dados inicializado em: {settings.DATABASE_PATH}")
