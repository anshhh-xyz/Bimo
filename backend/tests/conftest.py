from dotenv import load_dotenv
load_dotenv()
import os 
os.environ["PUBLIC_MODE"] = "0"   
# tests must never run with the public guard on
#load_dotenv() would otherwise pull PUBLIC_MODE=1 from your .env into the tests and make every REST test return 404.
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db import get_session
from app.models import Base, User, Project, ProjectMember


@pytest.fixture
def session():
    engine = create_engine(os.environ["DATABASE_URL_TEST"])
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        s.add_all([User(id=i, email=f"user{i}@test.dev",
                        display_name=f"user{i}") for i in (1, 2, 3, 4)])
        s.add(Project(id=1, name="demo"))
        s.flush()
        s.add_all([ProjectMember(project_id=1, user_id=1, role="owner"),
                   ProjectMember(project_id=1, user_id=2, role="editor"),
                   ProjectMember(project_id=1, user_id=3, role="viewer")])
        s.commit()
        yield s
    engine.dispose()


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def H(uid: int, surface: str = "code"):
    return {"X-User-Id": str(uid), "X-Surface": surface}