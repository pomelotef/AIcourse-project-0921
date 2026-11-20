from fastapi.testclient import TestClient

from app.main import app

from .conftest import Api


def test_register_login_logout(session_factory):
    api = Api(TestClient(app))
    api.get("/api/auth/me", status=401)
    me = api.post("/api/auth/register", {"email": "A@Test.local", "name": "A", "password": "password123"}, status=201)
    assert me["email"] == "a@test.local"
    assert api.get("/api/auth/me")["id"] == me["id"]
    api.post("/api/auth/logout", status=200)
    api.get("/api/auth/me", status=401)
    api.post("/api/auth/login", {"email": "a@test.local", "password": "wrong-pass"}, status=401)
    api.post("/api/auth/login", {"email": "a@test.local", "password": "password123"}, status=200)
    api.get("/api/auth/me")


def test_register_validation(session_factory):
    api = Api(TestClient(app))
    api.post("/api/auth/register", {"email": "x@test.local", "name": "X", "password": "short"}, status=422)
    api.post("/api/auth/register", {"email": "x@test.local", "name": "X", "password": "password123"}, status=201)
    api2 = Api(TestClient(app))
    api2.post("/api/auth/register", {"email": "x@test.local", "name": "Y", "password": "password123"}, status=409)


def test_password_not_stored_in_clear(session_factory):
    api = Api(TestClient(app))
    api.post("/api/auth/register", {"email": "p@test.local", "name": "P", "password": "password123"}, status=201)
    from app.models import User

    db = session_factory()
    user = db.query(User).one()
    assert "password123" not in user.password_hash
    assert user.password_hash.startswith("scrypt$")


def test_membership_and_roles(lab):
    prof, alice, eve = lab["prof"], lab["alice"], lab["eve"]
    pid = lab["pid"]
    project = alice.get(f"/api/projects/{pid}")
    assert project["my_role"] == "student"
    assert {m["name"] for m in project["members"]} == {"prof", "alice", "bob"}
    # outsiders cannot see the project at all
    eve.get(f"/api/projects/{pid}", status=404)
    assert [p["title"] for p in eve.get("/api/projects")] == ["Eve's project"]
    # students cannot manage members
    alice.post(f"/api/projects/{pid}/members", {"email": "eve@test.local"}, status=403)
    prof.post(f"/api/projects/{pid}/members", {"email": "nobody@test.local"}, status=404)
    prof.post(f"/api/projects/{pid}/members", {"email": "alice@test.local"}, status=409)
    # last advisor cannot be removed or demoted
    prof.delete(f"/api/projects/{pid}/members/{lab['ids']['prof']}", status=400)
    prof.patch(f"/api/projects/{pid}/members/{lab['ids']['prof']}", {"role": "student"}, status=400)

