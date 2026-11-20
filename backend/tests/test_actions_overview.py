from datetime import date, timedelta

from app.models import ProgressUpdate

from .conftest import days, now


def test_action_priority_order_and_reasons(lab):
    prof, alice, pid = lab["prof"], lab["alice"], lab["pid"]
    aid = lab["ids"]["alice"]
    today = date.today()
    low = prof.post(f"/api/projects/{pid}/actions", {"title": "low", "assignee_id": aid, "priority": "low"}, status=201)
    prof.post(f"/api/projects/{pid}/actions",
              {"title": "high-late", "assignee_id": aid, "priority": "high",
               "due_date": (today + timedelta(days=9)).isoformat()}, status=201)
    soon = prof.post(f"/api/projects/{pid}/actions",
                     {"title": "high-soon", "assignee_id": aid, "priority": "high",
                      "due_date": (today + timedelta(days=1)).isoformat()}, status=201)
    prof.post(f"/api/projects/{pid}/actions", {"title": "medium", "assignee_id": aid}, status=201)
    titles = [a["title"] for a in alice.get(f"/api/projects/{pid}/actions?state=open")]
    assert titles == ["high-soon", "high-late", "medium", "low"]

    # cancel and reschedule need a reason, and both are kept in history
    alice.patch(f"/api/actions/{low['id']}", {"state": "canceled"}, status=400)
    alice.patch(f"/api/actions/{low['id']}", {"state": "canceled", "reason": "方向改變"})
    alice.patch(f"/api/actions/{soon['id']}", {"due_date": (today + timedelta(days=5)).isoformat()}, status=400)
    alice.patch(f"/api/actions/{soon['id']}",
                {"due_date": (today + timedelta(days=5)).isoformat(), "reason": "等 GPU"})
    summaries = " ".join(e["summary"] for e in alice.get(f"/api/projects/{pid}/timeline?kind=action"))
    assert "方向改變" in summaries and "等 GPU" in summaries
    # canceled is not counted as open, but is still listed
    all_actions = alice.get(f"/api/projects/{pid}/actions")
    assert {a["title"]: a["state"] for a in all_actions}["low"] == "canceled"
    assert "low" not in [a["title"] for a in alice.get("/api/me/home")["my_actions"]]
    # students can only (re)assign to themselves
    alice.patch(f"/api/actions/{soon['id']}", {"assignee_id": lab["ids"]["bob"]}, status=403)
    lab["bob"].patch(f"/api/actions/{soon['id']}", {"state": "done"}, status=403)


def test_overview_attention_rules(lab, session_factory):
    prof, alice, bob, pid = lab["prof"], lab["alice"], lab["bob"], lab["pid"]
    g = prof.post(f"/api/projects/{pid}/goals", {"title": "G", "assignee_id": lab["ids"]["alice"]}, status=201)
    u = alice.post(f"/api/goals/{g['id']}/updates", {"completed": "old work", "publish": True}, status=201)
    db = session_factory()
    db.get(ProgressUpdate, u["id"]).published_at = now() - days(20)
    db.commit()
    prof.post(f"/api/projects/{pid}/actions",
              {"title": "late", "assignee_id": lab["ids"]["alice"],
               "due_date": (date.today() - timedelta(days=3)).isoformat()}, status=201)

    ov = prof.get("/api/me/overview")
    kinds = {(a["kind"], a.get("member", {}).get("name")) for a in ov["attention"]}
    assert ("stale", "alice") in kinds
    assert ("no_record", "bob") in kinds
    assert ("overdue", "alice") in kinds
    rows = {r["name"]: r for r in ov["by_member"]}
    assert rows["alice"]["freshness"] == "stale" and rows["bob"]["freshness"] == "no_record"
    assert ov["by_project"][0]["overdue_action_count"] == 1
    assert "資訊可能過期" in ov["rules"]["description"]
    # a longer cycle changes the rule, it is configurable
    assert {r["name"]: r for r in prof.get("/api/me/overview?stale_days=30")["by_member"]}["alice"]["freshness"] == "fresh"
    # students do not get an advisor overview of this project
    assert alice.get("/api/me/overview")["by_project"] == []
    assert alice.get("/api/me/home")["is_advisor"] is False
    assert prof.get("/api/me/home")["is_advisor"] is True
    _ = bob
