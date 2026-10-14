"""The engine lives in backend/db.py (it normalizes the postgresql+psycopg URL).
Re-export it here so the app has one engine, not two."""
from db import Base, SessionLocal, engine  # noqa: F401


def get_session():
    with SessionLocal() as session:
        yield session


"""You had two db.py files with two engines. 
The app/ one used the raw DATABASE_URL and would break on a plain postgresql:// URL. 
MCP tools will use SessionLocal directly, so it must be the correct one."""