"""Notification bell: who gets told about what (app/notify.py) and the bell API."""

from .conftest import iso, now


def _bell(api) -> dict:
    return api.get("/api/notifications")


def _summaries(api) -> list[str]:
    return [n["summary"] for n in _bell(api)["items"]]


def _clear(lab):
    """Mark everything read so each test starts from an empty bell (adding members already notified)."""
    for who in ("prof", "alice", "bob", "eve"):
        lab[who].post("/api/notifications/read-all")


def _unread(api) -> int:
    return _bell(api)["unread"]


def _goal(lab, who="alice", visibility="shared"):
    return lab[who].post(f"/api/projects/{lab['pid']}/goals",
                         {"title": "G", "assignee_id": lab["ids"][who], "visibility": visibility}, status=201)


def _meeting(lab):
    return lab["prof"].post(f"/api/projects/{lab['pid']}/meetings",
                            {"title": "Weekly", "occurred_at": iso(now())}, status=201)


# ---------------------------------------------------------------- normal cases
def test_published_update_reaches_the_advisor_and_read_clears_it(lab):
    goal = _goal(lab)
    _clear(lab)
    lab["alice"].post(f"/api/goals/{goal['id']}/updates", {"completed": "ran the baseline", "publish": True},
                      status=201)

    bell = _bell(lab["prof"])
    assert bell["unread"] == 1
    item = bell["items"][0]
    assert item["event_type"] == "update_published"
    assert item["actor"]["name"] == "alice"
    assert item["link"] == f"/goals/{goal['id']}"
    assert item["read"] is False

    lab["prof"].post(f"/api/notifications/{item['id']}/read")
    assert _unread(lab["prof"]) == 0
    assert _bell(lab["prof"])["items"][0]["read"] is True


def test_new_action_reaches_its_assignee_only(lab):
    _clear(lab)
    lab["prof"].post(f"/api/projects/{lab['pid']}/actions", {"title": "read paper", "assignee_id": lab["ids"]["bob"]},
                     status=201)
    assert _unread(lab["bob"]) == 1
    assert _unread(lab["alice"]) == 0
    assert _unread(lab["prof"]) == 0  # the one who did it


def test_student_outcome_asks_advisor_to_confirm_then_tells_author(lab):
    meeting = _meeting(lab)
    _clear(lab)
    outcome = lab["alice"].post(f"/api/meetings/{meeting['id']}/outcomes", {"decision": "switch dataset"},
                                status=201)
    assert _unread(lab["prof"]) == 1
    assert _bell(lab["prof"])["items"][0]["link"] == f"/meetings/{meeting['id']}"

    lab["prof"].post(f"/api/outcomes/{outcome['id']}/confirm")
    assert _unread(lab["alice"]) == 1
    assert _unread(lab["bob"]) == 0


def test_comment_reaches_author_and_earlier_commenters(lab):
    meeting = _meeting(lab)
    outcome = lab["prof"].post(f"/api/meetings/{meeting['id']}/outcomes", {"decision": "submit to ICASSP"},
                               status=201)
    _clear(lab)
    lab["alice"].post(f"/api/outcomes/{outcome['id']}/comments", {"body": "deadline?"}, status=201)
    assert _unread(lab["prof"]) == 1
    assert _unread(lab["bob"]) == 0

    lab["bob"].post(f"/api/outcomes/{outcome['id']}/comments", {"body": "Oct 20"}, status=201)
    assert _unread(lab["prof"]) == 1  # same outcome: still one notification, now showing bob's reply
    assert "Oct 20" in _bell(lab["prof"])["items"][0]["summary"]
    assert _unread(lab["alice"]) == 1  # commented earlier, so she hears the reply


def test_added_member_is_told(make_user, lab):
    dan, _ = make_user("dan")
    _clear(lab)
    lab["prof"].post(f"/api/projects/{lab['pid']}/members", {"email": "dan@test.local", "role": "student"},
                     status=201)
    bell = _bell(dan)
    assert bell["unread"] == 1
    assert bell["items"][0]["event_type"] == "member_added"
    assert bell["items"][0]["project"]["id"] == lab["pid"]
    # only the new member hears about it, not the members already there (nor the advisor who added him)
    assert _unread(lab["alice"]) == 0
    assert _unread(lab["bob"]) == 0
    assert _unread(lab["prof"]) == 0


def test_blocker_reaches_advisors_and_goal_assignee(lab):
    goal = _goal(lab, who="alice")
    _clear(lab)
    lab["bob"].post(f"/api/goals/{goal['id']}/blockers", {"title": "GPU quota", "description": ""}, status=201)

    for who in ("prof", "alice"):  # the advisor and the goal's assignee
        bell = _bell(lab[who])
        assert bell["unread"] == 1
        item = bell["items"][0]
        assert item["event_type"] == "blocker_opened"
        assert item["actor"]["name"] == "bob"
        assert item["link"] == f"/goals/{goal['id']}"  # the blocker's goal, not the blocker id
    assert _unread(lab["bob"]) == 0  # the one who did it
    assert _unread(lab["eve"]) == 0  # not a member


# ---------------------------------------------------------------- what must not happen
def test_nothing_for_events_private_to_one_user():
    # Events about a private goal carry private_to; they must never fan out, whatever their type.
    from app import notify
    from app.models import ActivityEvent

    ev = ActivityEvent(project_id=1, actor_id=1, event_type="update_published", entity_type="update", entity_id=1,
                       summary="", private_to=1)
    assert notify.recipients(None, ev) == set()


def test_outsiders_get_nothing(lab):
    goal = _goal(lab)
    _clear(lab)
    lab["alice"].post(f"/api/goals/{goal['id']}/updates", {"completed": "x", "publish": True}, status=201)
    assert _unread(lab["eve"]) == 0
    assert all(n["project"]["id"] != lab["pid"] for n in _bell(lab["eve"])["items"])


def test_cannot_mark_someone_elses_notification(lab):
    goal = _goal(lab)
    lab["alice"].post(f"/api/goals/{goal['id']}/updates", {"completed": "x", "publish": True}, status=201)
    nid = _bell(lab["prof"])["items"][0]["id"]
    lab["bob"].post(f"/api/notifications/{nid}/read", status=404)
    assert _bell(lab["prof"])["items"][0]["read"] is False


def test_failed_request_creates_no_notification(lab):
    _clear(lab)
    # bob may not reassign a task to someone else: 403, and nothing may be left behind
    action = lab["prof"].post(f"/api/projects/{lab['pid']}/actions",
                              {"title": "t", "assignee_id": lab["ids"]["bob"]}, status=201)
    lab["bob"].post("/api/notifications/read-all")
    lab["bob"].patch(f"/api/actions/{action['id']}", {"assignee_id": lab["ids"]["alice"]}, status=403)
    assert _unread(lab["alice"]) == 0


# ---------------------------------------------------------------- edge cases
def test_notification_whose_event_became_private_is_hidden(lab, session_factory):
    # The API refuses to make a goal with shared history private today; the bell must stay safe if that changes.
    goal = _goal(lab)
    lab["alice"].post(f"/api/goals/{goal['id']}/updates", {"completed": "shared work", "publish": True}, status=201)
    assert "進度更新：shared work" in _summaries(lab["prof"])

    from app.models import ActivityEvent

    with session_factory() as db:
        db.query(ActivityEvent).filter(ActivityEvent.goal_id == goal["id"]).update(
            {ActivityEvent.private_to: lab["ids"]["alice"]})
        db.commit()
    assert "進度更新：shared work" not in _summaries(lab["prof"])
    assert _unread(lab["prof"]) == 0


def test_removed_member_no_longer_sees_project_notifications(lab):
    action = lab["prof"].post(f"/api/projects/{lab['pid']}/actions",
                              {"title": "t", "assignee_id": lab["ids"]["bob"]}, status=201)
    assert _unread(lab["bob"]) >= 1
    lab["prof"].delete(f"/api/projects/{lab['pid']}/members/{lab['ids']['bob']}")
    assert _bell(lab["bob"]) == {"items": [], "unread": 0}
    assert action  # the action itself is untouched


def test_changes_to_one_thing_merge_into_one_notification(lab):
    action = lab["prof"].post(f"/api/projects/{lab['pid']}/actions",
                              {"title": "t", "assignee_id": lab["ids"]["bob"]}, status=201)
    for p in ("high", "low", "medium"):
        lab["prof"].patch(f"/api/actions/{action['id']}", {"priority": p})
    bell = _bell(lab["bob"])
    about_action = [n for n in bell["items"] if n["event_type"].startswith("action_")]
    assert len(about_action) == 1
    assert "中" in about_action[0]["summary"]  # shows the latest change (priority -> medium)


def test_new_event_reopens_a_read_notification_and_moves_it_up(lab):
    a1 = lab["prof"].post(f"/api/projects/{lab['pid']}/actions", {"title": "first", "assignee_id": lab["ids"]["bob"]},
                          status=201)
    lab["prof"].post(f"/api/projects/{lab['pid']}/actions", {"title": "second", "assignee_id": lab["ids"]["bob"]},
                     status=201)
    _clear(lab)
    lab["prof"].patch(f"/api/actions/{a1['id']}", {"priority": "high"})
    bell = _bell(lab["bob"])
    assert bell["unread"] == 1
    assert "first" in bell["items"][0]["summary"]  # back on top, unread again


def test_acting_on_a_thing_marks_your_own_notification_read(lab):
    meeting = _meeting(lab)
    outcome = lab["alice"].post(f"/api/meetings/{meeting['id']}/outcomes", {"decision": "switch dataset"},
                                status=201)
    assert _unread(lab["prof"]) >= 1
    lab["prof"].post(f"/api/outcomes/{outcome['id']}/confirm")  # the advisor has clearly seen it
    assert all(n["read"] for n in _bell(lab["prof"])["items"] if n["link"] == f"/meetings/{meeting['id']}")


def test_bell_requires_login(session_factory):
    from fastapi.testclient import TestClient

    from app.main import app

    assert TestClient(app).get("/api/notifications").status_code == 401
