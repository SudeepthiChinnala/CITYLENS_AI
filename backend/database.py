from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'citylens.db')

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def ensure_complaint_identity_column():
    """Add nullable ownership only when upgrading an existing complaints table."""
    inspector = inspect(engine)
    if not inspector.has_table('complaints'):
        return
    columns = {column['name'] for column in inspector.get_columns('complaints')}
    if 'citizen_id' not in columns:
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE complaints ADD COLUMN citizen_id VARCHAR'))
