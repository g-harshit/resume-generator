"""Test setup: a real Postgres (the `resume_test` database from docker-compose),
one transaction per test, rolled back afterwards.

Settings are set *before* the app is imported, so nothing can bind to the dev
database, call a real AI vendor, or write into the dev upload folder.
"""

import os
import tempfile

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://resume:resume@localhost:5433/resume_test"
)
if not TEST_DATABASE_URL.rsplit("/", 1)[-1].endswith("_test"):
    raise RuntimeError(f"Refusing to run tests against a non-test database: {TEST_DATABASE_URL}")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["AI_PROVIDER"] = "stub"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="rg-test-uploads-")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from app import database  # noqa: E402
from app.ai_providers import stub  # noqa: E402
from app.database import engine, get_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _stub_ai():
    stub.reset()
    yield
    stub.reset()


@pytest.fixture
def connection():
    with engine.connect() as conn:
        transaction = conn.begin()
        yield conn
        transaction.rollback()


def _session(conn) -> Session:
    # Commits inside the code under test become savepoints, so the outer rollback
    # still undoes everything the test did.
    return Session(bind=conn, join_transaction_mode="create_savepoint")


@pytest.fixture
def session(connection):
    """For arranging and asserting. Call `session.expire_all()` before reading
    something a request or background job has changed since."""
    with _session(connection) as s:
        yield s


@pytest.fixture
def client(connection, monkeypatch):
    # A fresh session per request, as in production, so a request never sees a
    # stale copy of a row a background job has since updated.
    def per_request():
        with _session(connection) as s:
            yield s

    app.dependency_overrides[get_session] = per_request
    # Background jobs open their own sessions; keep them inside the test transaction.
    monkeypatch.setattr(database, "session_factory", lambda: _session(connection))
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth(client):
    """Headers for a freshly registered user."""
    r = client.post(
        "/auth/register",
        json={"email": "asha@example.com", "password": "correct horse", "name": "Asha Rao"},
    )
    return {"Authorization": f"Bearer {r.json()['token']}"}
