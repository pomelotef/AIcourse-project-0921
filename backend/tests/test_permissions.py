"""Direct API calls must not cross projects, escalate, reveal private records or link illegally."""

from .conftest import iso, now


def _goal(api, pid, **kw):
    body = {"title": kw.pop("title", "G"), **kw}
    return api.post(f"/api/projects/{pid}/goals", body, status=201)


def test_outsider_cannot_read_or_write_anything(lab):
    prof, eve, pid = lab["prof"], lab["eve"], lab["pid"]
    g = _goal(prof, pid, assignee_id=lab["ids"]["alice"])
    m = prof.post(f"/api/projects/{pid}/meetings", {"title": "M", "occurred_at": iso(now())}, status=201)
    a = prof.post(f"/api/projects/{pid}/actions", {"title": "A", "assignee_id": lab["ids"]["alice"]}, status=201)
    b = prof.post(f"/api/goals/{g['id']}/blockers", {"title": "B"}, status=201)

    for url in (
        f"/api/projects/{pid}/goals", f"/api/goals/{g['id']}", f"/api/goals/{g['id']}/updates",
        f"/api/projects/{pid}/meetings", f"/api/meetings/{m['id']}", f"/api/meetings/{m['id']}/brief",
        f"/api/projects/{pid}/actions", f"/api/projects/{pid}/timeline", f"/api/projects/{pid}/notes",
    ):
        eve.get(url, status=404)
    eve.post(f"/api/goals/{g['id']}/updates", {"completed": "x", "publish": True}, status=404)
    eve.post(f"/api/meetings/{m['id']}/outcomes", {"decision": "x"}, status=404)
    eve.patch(f"/api/actions/{a['id']}", {"state": "done"}, status=404)
    eve.patch(f"/api/blockers/{b['id']}", {"state": "resolved"}, status=404)
    eve.patch(f"/api/goals/{g['id']}", {"title": "hacked"}, status=404)
    eve.post("/api/links", {"target_type": "goal", "target_id": g["id"], "url": "https://x.y"}, status=404)
    # Eve's overview does not include P1
    assert [p["title"] for p in eve.get("/api/me/overview")["by_project"]] == ["Eve's project"]


def test_cross_project_ids_are_rejected(lab):
    prof, eve, pid, other = lab["prof"], lab["eve"], lab["pid"], lab["other_pid"]
    eve_goal = _goal(eve, other)
    eve_meeting = eve.post(f"/api/projects/{other}/meetings", {"title": "EM", "occurred_at": iso(now())}, status=201)
    # Linking P1 records to another project's goal/meeting/parent must fail
    prof.post(f"/api/projects/{pid}/goals", {"title": "x", "parent_id": eve_goal["id"]}, status=400)
    prof.post(f"/api/projects/{pid}/actions",
              {"title": "x", "assignee_id": lab["ids"]["alice"], "goal_id": eve_goal["id"]}, status=400)
    prof.post(f"/api/projects/{pid}/actions",
              {"title": "x", "assignee_id": lab["ids"]["alice"], "source_meeting_id": eve_meeting["id"]}, status=400)
    # Assigning to a non-member fails
    prof.post(f"/api/projects/{pid}/actions", {"title": "x", "assignee_id": lab["ids"]["eve"]}, status=400)
    prof.post(f"/api/projects/{pid}/goals", {"title": "x", "assignee_id": lab["ids"]["eve"]}, status=400)
    m = prof.post(f"/api/projects/{pid}/meetings", {"title": "M", "occurred_at": iso(now())}, status=201)
    prof.post(f"/api/meetings/{m['id']}/outcomes", {"decision": "d", "goal_id": eve_goal["id"]}, status=400)
    prof.post(f"/api/projects/{pid}/meetings",
              {"title": "M2", "occurred_at": iso(now()), "participant_ids": [lab["ids"]["eve"]]}, status=400)
    # Referencing another project's blocker from an update fails
    eve_blocker = eve.post(f"/api/goals/{eve_goal['id']}/blockers", {"title": "eb"}, status=201)
    g = _goal(prof, pid, assignee_id=lab["ids"]["alice"])
    lab["alice"].post(f"/api/goals/{g['id']}/updates",
                      {"completed": "x", "referenced_blocker_ids": [eve_blocker["id"]]}, status=400)


def test_students_cannot_escalate(lab):
    alice, pid = lab["alice"], lab["pid"]
    alice.patch(f"/api/projects/{pid}", {"title": "x"}, status=403)
    alice.patch(f"/api/projects/{pid}/members/{lab['ids']['alice']}", {"role": "advisor"}, status=403)
    alice.post(f"/api/projects/{pid}/goals", {"title": "x", "assignee_id": lab["ids"]["bob"]}, status=403)
    alice.post(f"/api/projects/{pid}/actions", {"title": "x", "assignee_id": lab["ids"]["bob"]}, status=403)
    m = alice.post(f"/api/projects/{pid}/meetings", {"title": "M", "occurred_at": iso(now())}, status=201)
    o = alice.post(f"/api/meetings/{m['id']}/outcomes", {"decision": "d"}, status=201)
    assert o["confirmation_state"] == "pending"
    alice.post(f"/api/outcomes/{o['id']}/confirm", status=403)
    g = _goal(lab["prof"], pid, assignee_id=lab["ids"]["bob"])
    alice.patch(f"/api/goals/{g['id']}", {"research_state": "answered"}, status=403)


def test_private_goal_and_notes_never_leak(lab):
    prof, alice, pid = lab["prof"], lab["alice"], lab["pid"]
    secret = _goal(prof, pid, title="SECRET-PLAN", visibility="private")
    prof.post(f"/api/projects/{pid}/notes", {"body": "SECRET-NOTE", "goal_id": secret["id"]}, status=201)
    shared = _goal(prof, pid, title="shared", assignee_id=lab["ids"]["alice"])
    prof.post(f"/api/projects/{pid}/notes", {"body": "SECRET-NOTE-2", "goal_id": shared["id"]}, status=201)

    alice.get(f"/api/goals/{secret['id']}", status=404)
    alice.get(f"/api/projects/{pid}/timeline?goal_id={secret['id']}", status=404)
    for url in (f"/api/projects/{pid}/goals", f"/api/projects/{pid}/timeline", f"/api/goals/{shared['id']}",
                f"/api/projects/{pid}/notes", "/api/me/home"):
        body = str(alice.get(url))
        assert "SECRET" not in body, url
    # the advisor sees both
    assert "SECRET-PLAN" in str(prof.get(f"/api/projects/{pid}/timeline"))
    assert prof.get(f"/api/goals/{shared['id']}")["private_notes"][0]["body"] == "SECRET-NOTE-2"
    # notes cannot be read or edited by id
    note_id = prof.get(f"/api/projects/{pid}/notes")[0]["id"]
    alice.patch(f"/api/notes/{note_id}", {"body": "x"}, status=404)


def test_private_goal_cannot_be_linked_or_assigned(lab):
    prof, pid, alice_id = lab["prof"], lab["pid"], lab["ids"]["alice"]
    secret = _goal(prof, pid, visibility="private")
    prof.post(f"/api/projects/{pid}/goals", {"title": "x", "visibility": "private", "assignee_id": alice_id},
              status=400)
    prof.post(f"/api/projects/{pid}/goals", {"title": "child", "parent_id": secret["id"]}, status=400)
    prof.post(f"/api/goals/{secret['id']}/updates", {"completed": "x"}, status=400)
    prof.post(f"/api/goals/{secret['id']}/blockers", {"title": "x"}, status=400)
    prof.post(f"/api/projects/{pid}/actions", {"title": "x", "assignee_id": alice_id, "goal_id": secret["id"]},
              status=400)
    prof.patch(f"/api/goals/{secret['id']}", {"assignee_id": alice_id}, status=400)
    # making it shared first allows assignment
    prof.patch(f"/api/goals/{secret['id']}", {"visibility": "shared", "assignee_id": alice_id})


def test_shared_goal_with_records_cannot_become_private_and_history_hides(lab):
    prof, alice, pid = lab["prof"], lab["alice"], lab["pid"]
    g = _goal(prof, pid, title="WILL-BE-PRIVATE")
    g2 = _goal(prof, pid, title="has-updates", assignee_id=lab["ids"]["alice"])
    alice.post(f"/api/goals/{g2['id']}/updates", {"completed": "done", "publish": True}, status=201)
    prof.patch(f"/api/goals/{g2['id']}", {"visibility": "private"}, status=400)
    assert "WILL-BE-PRIVATE" in str(alice.get(f"/api/projects/{pid}/timeline"))
    prof.patch(f"/api/goals/{g['id']}", {"visibility": "private"})
    assert "WILL-BE-PRIVATE" not in str(alice.get(f"/api/projects/{pid}/timeline"))


def test_drafts_are_private_to_author(lab):
    prof, alice, bob, pid = lab["prof"], lab["alice"], lab["bob"], lab["pid"]
    g = _goal(prof, pid, assignee_id=lab["ids"]["alice"])
    d = alice.post(f"/api/goals/{g['id']}/updates",
                   {"completed": "DRAFT-TEXT", "new_blockers": [{"title": "DRAFT-BLOCKER"}]}, status=201)
    assert d["publication_state"] == "draft"
    for api in (prof, bob):
        assert "DRAFT" not in str(api.get(f"/api/goals/{g['id']}"))
        assert "DRAFT" not in str(api.get(f"/api/goals/{g['id']}/updates"))
        assert "DRAFT" not in str(api.get(f"/api/projects/{pid}/timeline"))
        api.patch(f"/api/updates/{d['id']}", {"completed": "x"}, status=404)
        api.post("/api/links", {"target_type": "update", "target_id": d["id"], "url": "https://x.y"}, status=404)
    # draft blockers only materialize on publish
    assert alice.get(f"/api/goals/{g['id']}/blockers") == []
    pub = alice.patch(f"/api/updates/{d['id']}", {"completed": "DRAFT-TEXT", "new_blockers": [{"title": "B"}],
                                                   "publish": True})
    assert pub["publication_state"] == "published"
    assert [b["title"] for b in prof.get(f"/api/goals/{g['id']}/blockers")] == ["B"]
    # published updates are immutable
    alice.patch(f"/api/updates/{d['id']}", {"completed": "changed"}, status=400)


def test_goal_parent_cycle_rejected(lab):
    prof, pid = lab["prof"], lab["pid"]
    a = _goal(prof, pid, title="A")
    b = _goal(prof, pid, title="B", parent_id=a["id"])
    c = _goal(prof, pid, title="C", parent_id=b["id"])
    prof.patch(f"/api/goals/{a['id']}", {"parent_id": c["id"]}, status=400)
    prof.patch(f"/api/goals/{a['id']}", {"parent_id": a["id"]}, status=400)
    prof.patch(f"/api/goals/{c['id']}", {"parent_id": a["id"]})


def test_links_must_be_http(lab):
    prof, pid = lab["prof"], lab["pid"]
    g = _goal(prof, pid)
    prof.post("/api/links", {"target_type": "goal", "target_id": g["id"], "url": "javascript:alert(1)"}, status=422)
    prof.post("/api/links", {"target_type": "goal", "target_id": g["id"], "url": "ftp://x.y/z"}, status=422)
    links = prof.post("/api/links", {"target_type": "goal", "target_id": g["id"], "url": "https://github.com/x"},
                      status=201)
    assert links[0]["url"] == "https://github.com/x"
