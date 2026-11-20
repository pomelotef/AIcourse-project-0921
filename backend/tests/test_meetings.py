"""Meeting brief business rules, outcomes and the full two-meeting loop."""

from app.models import Blocker, Meeting, ProgressUpdate

from .conftest import days, iso, now


def _setup(lab):
    prof, alice, pid = lab["prof"], lab["alice"], lab["pid"]
    goal = prof.post(f"/api/projects/{pid}/goals",
                     {"title": "Vulkan", "assignee_id": lab["ids"]["alice"], "research_state": "investigating"},
                     status=201)
    return prof, alice, pid, goal


def test_first_meeting_brief(lab):
    prof, alice, pid, goal = _setup(lab)
    alice.post(f"/api/goals/{goal['id']}/updates", {"completed": "c1", "publish": True}, status=201)
    m = prof.post(f"/api/projects/{pid}/meetings", {"title": "M1", "occurred_at": iso(now() + days(1))}, status=201)
    brief = prof.get(f"/api/meetings/{m['id']}/brief")
    assert brief["is_first_meeting"] is True
    assert brief["previous_meeting"] is None
    assert [u["completed"] for u in brief["updates"]] == ["c1"]
    assert brief["previous_commitments"] == []


def test_two_meeting_loop_end_to_end(lab):
    """The CP1 interaction: advisor assigns -> student updates -> advisor reviews brief and records
    decision + next action -> student sees it -> history keeps both rounds."""
    prof, alice, pid, goal = _setup(lab)
    alice_id = lab["ids"]["alice"]

    m1 = prof.post(f"/api/projects/{pid}/meetings",
                   {"title": "M1", "occurred_at": iso(now() - days(3)), "participant_ids": [lab["ids"]["prof"], alice_id]},
                   status=201)
    prof.post(f"/api/meetings/{m1['id']}/outcomes",
              {"goal_id": goal["id"], "decision": "先比較模型", "rationale": "需要 baseline"}, status=201)
    done = prof.post(f"/api/projects/{pid}/actions",
                     {"title": "比較 Gemma/Llama", "assignee_id": alice_id, "goal_id": goal["id"],
                      "source_meeting_id": m1["id"], "priority": "high"}, status=201)
    stuck = prof.post(f"/api/projects/{pid}/actions",
                      {"title": "Vulkan profiling", "assignee_id": alice_id, "goal_id": goal["id"],
                       "source_meeting_id": m1["id"]}, status=201)
    older = prof.post(f"/api/projects/{pid}/actions", {"title": "讀論文", "assignee_id": alice_id}, status=201)

    # Student works between meetings
    alice.patch(f"/api/actions/{done['id']}", {"state": "done", "note": "已完成"})
    upd = alice.post(f"/api/goals/{goal['id']}/updates",
                     {"completed": "模型比較完成", "findings": "Gemma 較省記憶體", "next_steps": "修 Vulkan build",
                      "new_blockers": [{"title": "Vulkan 編譯失敗"}],
                      "links": [{"url": "https://github.com/org/repo/issues/1", "link_type": "code"}],
                      "publish": True}, status=201)
    assert upd["blockers"][0]["title"] == "Vulkan 編譯失敗"
    assert upd["links"][0]["link_type"] == "code"

    # Advisor prepares meeting 2
    m2 = prof.post(f"/api/projects/{pid}/meetings",
                   {"title": "M2", "occurred_at": iso(now() + days(1)), "agenda": "是否延續 Vulkan？"}, status=201)
    brief = prof.get(f"/api/meetings/{m2['id']}/brief")
    assert brief["is_first_meeting"] is False
    assert brief["previous_meeting"]["id"] == m1["id"]
    assert {a["title"]: a["state"] for a in brief["previous_commitments"]} == {
        "比較 Gemma/Llama": "done", "Vulkan profiling": "open"}
    assert [a["title"] for a in brief["carried_over_actions"]] == ["讀論文"]
    assert [u["id"] for u in brief["updates"]] == [upd["id"]]
    assert [b["title"] for b in brief["open_blockers"]] == ["Vulkan 編譯失敗"]
    assert [o["decision"] for o in brief["previous_outcomes"]] == ["先比較模型"]
    assert brief["agenda"] == "是否延續 Vulkan？"

    # Decision, feedback and next action recorded in meeting 2
    out = prof.post(f"/api/meetings/{m2['id']}/outcomes",
                    {"goal_id": goal["id"], "decision": "先驗證量測方法，再給 Vulkan 一週",
                     "rationale": "數據可信度優先", "feedback": "先確認量測工具"}, status=201)
    assert out["confirmation_state"] == "confirmed"
    prof.post(f"/api/projects/{pid}/actions",
              {"title": "驗證量測方法", "assignee_id": alice_id, "goal_id": goal["id"],
               "source_meeting_id": m2["id"], "priority": "high"}, status=201)

    # Student sees the new action, feedback and goal summary after reloading
    home = alice.get("/api/me/home")
    assert home["my_actions"][0]["title"] == "驗證量測方法"
    assert home["my_actions"][0]["priority"] == "high"
    assert any(f["decision"].startswith("先驗證量測方法") for f in home["recent_feedback"])
    detail = alice.get(f"/api/goals/{goal['id']}")
    s = detail["summary"]
    assert s["latest_update"]["id"] == upd["id"]
    assert s["open_blockers"][0]["title"] == "Vulkan 編譯失敗"
    assert s["next_steps_text"] == "修 Vulkan build"
    assert s["latest_decision"]["decision"] == "先驗證量測方法，再給 Vulkan 一週"
    # Old meeting's decision is still there, not overwritten
    assert [o["decision"] for o in detail["outcomes"]] == ["先驗證量測方法，再給 Vulkan 一週", "先比較模型"]
    assert "已完成" in [a["note"] for a in detail["actions"]]

    # Timeline keeps both rounds
    tl = alice.get(f"/api/projects/{pid}/timeline?goal_id={goal['id']}")
    types = [e["event_type"] for e in tl]
    assert types.count("outcome_recorded") == 2
    assert "update_published" in types and "blocker_opened" in types
    decisions = alice.get(f"/api/projects/{pid}/timeline?kind=decision")
    assert all(e["event_type"].startswith(("outcome", "meeting")) for e in decisions)
    _ = older


def test_brief_window_boundaries(lab, session_factory):
    prof, alice, pid, goal = _setup(lab)
    t1 = now() - days(10)
    t2 = now() - days(2)
    m1 = prof.post(f"/api/projects/{pid}/meetings", {"title": "M1", "occurred_at": iso(t1)}, status=201)
    m2 = prof.post(f"/api/projects/{pid}/meetings", {"title": "M2", "occurred_at": iso(t2)}, status=201)
    ids = {}
    for label in ("at_prev", "inside", "at_this", "after"):
        ids[label] = alice.post(f"/api/goals/{goal['id']}/updates", {"completed": label, "publish": True},
                                status=201)["id"]
    db = session_factory()
    stamps = {"at_prev": t1, "inside": t1 + days(3), "at_this": t2, "after": t2 + days(1)}
    for label, ts in stamps.items():
        db.get(ProgressUpdate, ids[label]).published_at = ts
    db.commit()
    brief = prof.get(f"/api/meetings/{m2['id']}/brief")
    assert sorted(u["completed"] for u in brief["updates"]) == ["at_this", "inside"]
    assert brief["window"]["start"] is not None
    # The first meeting's window is everything up to it (inclusive)
    brief1 = prof.get(f"/api/meetings/{m1['id']}/brief")
    assert [u["completed"] for u in brief1["updates"]] == ["at_prev"]


def test_brief_keeps_categories_separate(lab):
    prof, alice, pid, goal = _setup(lab)
    lab1 = prof.post(f"/api/projects/{pid}/meetings",
                     {"title": "Lab1", "category": "lab", "occurred_at": iso(now() - days(5))}, status=201)
    ind = prof.post(f"/api/projects/{pid}/meetings",
                    {"title": "Ind", "category": "industry", "occurred_at": iso(now() - days(2))}, status=201)
    lab2 = prof.post(f"/api/projects/{pid}/meetings",
                     {"title": "Lab2", "category": "lab", "occurred_at": iso(now() + days(1))}, status=201)
    assert prof.get(f"/api/meetings/{lab2['id']}/brief")["previous_meeting"]["id"] == lab1["id"]
    assert prof.get(f"/api/meetings/{ind['id']}/brief")["is_first_meeting"] is True
    assert [m["title"] for m in prof.get(f"/api/projects/{pid}/meetings?category=industry")] == ["Ind"]
    prof.post(f"/api/meetings/{ind['id']}/outcomes", {"decision": "廠商要比較表"}, status=201)
    tl = prof.get(f"/api/projects/{pid}/timeline?category=industry")
    assert tl and all(e["meeting_category"] == "industry" for e in tl)


def test_brief_member_filter(lab):
    prof, alice, pid, goal = _setup(lab)
    bob = lab["bob"]
    bgoal = prof.post(f"/api/projects/{pid}/goals", {"title": "Bob goal", "assignee_id": lab["ids"]["bob"]},
                      status=201)
    alice.post(f"/api/goals/{goal['id']}/updates", {"completed": "alice work", "publish": True}, status=201)
    bob.post(f"/api/goals/{bgoal['id']}/updates", {"completed": "bob work", "new_blockers": [{"title": "bob blk"}],
                                                   "publish": True}, status=201)
    m = prof.post(f"/api/projects/{pid}/meetings", {"title": "M", "occurred_at": iso(now() + days(1))}, status=201)
    brief = prof.get(f"/api/meetings/{m['id']}/brief?member_id={lab['ids']['alice']}")
    assert [u["completed"] for u in brief["updates"]] == ["alice work"]
    assert brief["open_blockers"] == []
    prof.get(f"/api/meetings/{m['id']}/brief?member_id={lab['ids']['eve']}", status=400)


def test_same_blocker_referenced_by_many_updates(lab):
    prof, alice, pid, goal = _setup(lab)
    first = alice.post(f"/api/goals/{goal['id']}/updates",
                       {"completed": "u1", "new_blockers": [{"title": "GPU driver"}], "publish": True}, status=201)
    bid = first["blockers"][0]["id"]
    for i in range(2):
        alice.post(f"/api/goals/{goal['id']}/updates",
                   {"completed": f"u{i + 2}", "referenced_blocker_ids": [bid], "publish": True}, status=201)
    blockers = prof.get(f"/api/goals/{goal['id']}/blockers")
    assert len(blockers) == 1 and blockers[0]["id"] == bid and blockers[0]["reference_count"] == 3
    # resolve with a stable id; it then shows as resolved in the brief window
    alice.patch(f"/api/blockers/{bid}", {"state": "resolved", "resolution": "換驅動版本"})
    m = prof.post(f"/api/projects/{pid}/meetings", {"title": "M", "occurred_at": iso(now() + days(1))}, status=201)
    brief = prof.get(f"/api/meetings/{m['id']}/brief")
    assert brief["open_blockers"] == []
    assert brief["resolved_blockers"][0]["resolution"] == "換驅動版本"
    # bob (not reporter, not goal owner, not advisor) cannot reopen it
    lab["bob"].patch(f"/api/blockers/{bid}", {"state": "open"}, status=403)


def test_student_outcome_needs_advisor_confirmation(lab):
    prof, alice, pid, goal = _setup(lab)
    m = alice.post(f"/api/projects/{pid}/meetings", {"title": "M", "occurred_at": iso(now())}, status=201)
    o = alice.post(f"/api/meetings/{m['id']}/outcomes", {"decision": "draft decision", "goal_id": goal["id"]},
                   status=201)
    assert o["confirmation_state"] == "pending"
    o = alice.patch(f"/api/outcomes/{o['id']}", {"decision": "revised decision"})
    assert prof.get("/api/me/home")["pending_confirmation"][0]["id"] == o["id"]
    assert any(a["kind"] == "pending_outcome" for a in prof.get("/api/me/overview")["attention"])
    o = prof.post(f"/api/outcomes/{o['id']}/confirm")
    assert o["confirmation_state"] == "confirmed" and o["confirmed_by"]["name"] == "prof"
    # confirmed decisions are not edited in place; discussion goes into comments
    alice.patch(f"/api/outcomes/{o['id']}", {"decision": "sneaky"}, status=400)
    o = prof.post(f"/api/outcomes/{o['id']}/comments", {"body": "補充：先跑小模型"}, status=201)
    assert o["comments"][0]["body"] == "補充：先跑小模型"
    prof.post(f"/api/outcomes/{o['id']}/confirm", status=400)


def test_meeting_update_permissions(lab, session_factory):
    prof, alice, pid, _ = _setup(lab)
    m = prof.post(f"/api/projects/{pid}/meetings", {"title": "M", "occurred_at": iso(now())}, status=201)
    alice.patch(f"/api/meetings/{m['id']}", {"title": "x"}, status=403)
    prof.patch(f"/api/meetings/{m['id']}", {"title": "M renamed", "category": "one_on_one"})
    db = session_factory()
    assert db.get(Meeting, m["id"]).category == "one_on_one"
    assert db.query(Blocker).count() == 0
