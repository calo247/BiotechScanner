"""Database connection and session management."""

import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv

from .models import Base

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/catalyst.db')

# Create engine with SQLite-specific optimizations
if DATABASE_URL.startswith('sqlite'):
    # For SQLite, use StaticPool to maintain a single connection
    # This helps with concurrent access issues
    engine = create_engine(
        DATABASE_URL,
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
        echo=False  # Set to True for SQL query debugging
    )
else:
    # For other databases (future PostgreSQL migration)
    engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize the database by creating all tables."""
    # Create data directory if it doesn't exist
    if DATABASE_URL.startswith('sqlite'):
        os.makedirs('data', exist_ok=True)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at: {DATABASE_URL}")


def drop_all_tables():
    """Drop all tables. Use with caution!"""
    Base.metadata.drop_all(bind=engine)
    print("All tables dropped.")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Ensures proper cleanup of sessions.
    
    Usage:
        with get_db() as db:
            # Use db session here
            companies = db.query(Company).all()
    """
    db = SessionLocal()
    try:
        yield db
        # Don't auto-commit here - let the caller decide when to commit
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Get a database session.
    Remember to close it when done!
    
    Usage:
        db = get_db_session()
        try:
            # Use db here
        finally:
            db.close()
    """
    return SessionLocal()