import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

load_dotenv()
db_url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(db_url)

# Inspect the database tables
inspector = inspect(engine)
tables = inspector.get_table_names()

print("Tables currently in database:", tables)