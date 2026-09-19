# /config/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.env import require_env

# e.g. postgresql://user:password@host:5432/homecare - never hardcode it here.
DATABASE_URL = require_env("DATABASE_URL")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)

# Add this function
def get_db():
    """Dependency to get a DB session for each request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()