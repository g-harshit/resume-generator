"""Test setup: a real Postgres (the `resume_test` database from docker-compose),
one transaction per test, rolled back afterwards.

The URL is set *before* the app is imported, so nothing can bind to the dev database.
"""

import os

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://resume:resume@localhost:5433/resume_test"
)
if not TEST_DATABASE_URL.rsplit("/", 1)[-1].endswith("_test"):
    raise RuntimeError(f"Refusing to run tests against a non-test database: {TEST_DATABASE_URL}")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from app.database import engine, get_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield


@pytest.fixture
def session():
    with engine.connect() as connection:
        transaction = connection.begin()
        # Commits inside the code under test become savepoints, so the outer
        # rollback still undoes everything the test did.
        with Session(bind=connection, join_transaction_mode="create_savepoint") as s:
            yield s
        transaction.rollback()


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
