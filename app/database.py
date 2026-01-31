
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging

from app.models import Base
from app.settings import Settings

logger = logging.getLogger(__name__)


def get_database_url(settings: Settings) -> str:
    url = settings.database_url
    
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    
    return url


def create_db_engine(settings: Settings):
    database_url = get_database_url(settings)
    
    logger.info(f"Creating database engine...")
    
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Test connection health before using
        pool_recycle=3600,   # Recycle connections after 1 hour
        echo=False,          # Set to True for SQL query logging (debugging)
    )
    
    return engine


def init_database(settings: Settings):
    engine = create_db_engine(settings)
    
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
    
    engine.dispose()


def get_session_maker(settings: Settings) -> sessionmaker:
    engine = create_db_engine(settings)
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    return SessionLocal


async def get_db(settings: Settings):
    SessionLocal = get_session_maker(settings)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()