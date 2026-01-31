
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging

from app.models import Base
from app.settings import Settings

logger = logging.getLogger(__name__)

# Helper to adjust database URL if needed
def get_database_url(settings: Settings) -> str:
    url = settings.database_url
    
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    
    return url

# Create SQLAlchemy engine with connection pooling
def create_db_engine(settings: Settings):
    database_url = get_database_url(settings)
    
    logger.info("Creating database engine...")
    
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

# Initialize database and create tables
def init_database(settings: Settings):
    engine = create_db_engine(settings)
    
    logger.info("Initializing database tables")
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Test the connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        engine.dispose()

# Get a sessionmaker for database sessions
def get_session_maker(settings: Settings) -> sessionmaker:
    engine = create_db_engine(settings)
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    return SessionLocal

# Dependency to get DB session
async def get_db(settings: Settings):
    SessionLocal = get_session_maker(settings)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()