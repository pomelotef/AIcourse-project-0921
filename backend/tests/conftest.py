import os

os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
import app.security as _security  # noqa: E402

# Cheaper scrypt cost for tests only (hashes record their own parameters, so verify still works).
_security._N = 2**10


@pytest.fixture()
def session_factory():
    # In-memory SQLite shared across connections (StaticPool), with foreign keys enforced.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


class Api:
    """A logged-in browser: its own cookie jar plus helpers that assert status codes."""

    def __init__(self, client: TestClient):
        self.c = client

    def _check(self, r, status):
        assert r.status_code == status, f"{r.request.method} {r.request.url} -> {r.status_code}: {r.text}"
        return r.json()

    def get(self, url, status=200, **kw):
        return self._check(self.c.get(url, **kw), status)

    def post(self, url, json=None, status=None):
        r = self.c.post(url, json=json or {})
        if status is None:
            status = 201 if r.status_code == 201 else 200
        return self._check(r, status)

    def patch(self, url, json, status=200):
        return self._check(self.c.patch(url, json=json), status)

    def delete(self, url, status=200):
        return self._check(self.c.delete(url), status)


@pytest.fixture()
def make_user(session_factory):
    def _make(name: str) -> tuple[Api, dict]:
        client = TestClient(app)
        api = Api(client)
        me = api.post("/api/auth/register", {"email": f"{name}@test.local", "name": name, "password": "password123"},
                      status=201)
        return api, me

    return _make


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def now() -> datetime:
    return datetime.now(timezone.utc)


def days(n: float) -> timedelta:
    return timedelta(days=n)


@pytest.fixture()
def lab(make_user):
    """Advisor + two students sharing one project, plus an outsider with their own project."""
    prof, prof_me = make_user("prof")
    alice, alice_me = make_user("alice")
    bob, bob_me = make_user("bob")
    eve, eve_me = make_user("eve")
    project = prof.post("/api/projects", {"title": "P1"}, status=201)
    pid = project["id"]
    prof.post(f"/api/projects/{pid}/members", {"email": "alice@test.local", "role": "student"}, status=201)
    prof.post(f"/api/projects/{pid}/members", {"email": "bob@test.local", "role": "student"}, status=201)
    other = eve.post("/api/projects", {"title": "Eve's project"}, status=201)
    return {
        "prof": prof, "alice": alice, "bob": bob, "eve": eve,
        "ids": {"prof": prof_me["id"], "alice": alice_me["id"], "bob": bob_me["id"], "eve": eve_me["id"]},
        "pid": pid, "other_pid": other["id"],
    }
