import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()
db_url = os.environ["DATABASE_URL"]  # raises KeyError if missing

# Alembic and SQLAlchemy need the driver in the URL prefix
if db_url.startswith("postgres://"):
    database_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://"):
    database_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    database_url = db_url

engine = create_engine(
    database_url,
    pool_size=2,        # connections kept open
    max_overflow=8,     # extra connections allowed under load (2 + 8 = 10 max)
    pool_pre_ping=True, # test a connection before using it
)

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass