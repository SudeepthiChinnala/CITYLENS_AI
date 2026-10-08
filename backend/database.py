import os
import shutil
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def _get_database_path() -> str:
    env_path = os.getenv('CITYLENS_DB_PATH', '').strip()
    if env_path:
        return env_path
    
    default_db = os.path.join(BASE_DIR, 'citylens.db')
    # Check if running in a read-only environment like Vercel Serverless
    is_vercel = bool(os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'))
    test_file = os.path.join(BASE_DIR, '.write_test')
    is_writable = False
    if not is_vercel:
        try:
            with open(test_file, 'w') as f:
                f.write('ok')
            os.remove(test_file)
            is_writable = True
        except Exception:
            is_writable = False

    if is_writable:
        return default_db
    
    # Fallback to /tmp/citylens.db for serverless environments
    tmp_db = '/tmp/citylens.db'
    if not os.path.exists(tmp_db) and os.path.exists(default_db):
        try:
            shutil.copyfile(default_db, tmp_db)
        except Exception as e:
            print(f"Warning: Failed to copy seed DB to {tmp_db}: {e}")
    return tmp_db

DB_PATH = _get_database_path()

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
    try:
        inspector = inspect(engine)
        if not inspector.has_table('complaints'):
            return
        columns = {column['name'] for column in inspector.get_columns('complaints')}
        if 'citizen_id' not in columns:
            with engine.begin() as connection:
                connection.execute(text('ALTER TABLE complaints ADD COLUMN citizen_id VARCHAR'))
    except Exception as e:
        print(f"Schema inspection notice: {e}")
