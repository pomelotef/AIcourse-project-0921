"""Live refresh: who gets told that a project changed (app/live.py)."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import live
from app.main import app


class Listener:
    """Stands in for open browser tabs: one hub queue per user, drained on demand."""

    def __init__(self, ids: dict[str, int]):
        self.loop = asyncio.new_event_loop()
        self.ids = ids
        self.queues = {name: live.hub.subscribe(uid, loop=self.loop) for name, uid in ids.items()}

    def drain(self) -> dict[str, list[dict]]:
        self.loop.run_until_complete(asyncio.sleep(0))  # run the call_soon_threadsafe callbacks
        out = {}
        for name, q in self.queues.items():
            out[name] = []
            while not q.empty():
                out[name].append(q.get_nowait())
        return out

    def notified(self) -> set[str]:
        return {name for name, msgs in self.drain().items() if msgs}

    def close(self):
        for name, q in self.queues.items():
            live.hub.unsubscribe(self.ids[name], q)
        self.loop.close()


@pytest.fixture()
def listen(lab):
    listener = Listener(lab["ids"])
    listener.drain()
    yield listener
    listener.close()


def _goal(lab, who="alice", visibility="shared"):
    ids = lab["ids"]
    return lab[who].post(f"/api/projects/{lab['pid']}/goals",
                         {"title": "G", "assignee_id": ids[who], "visibility": visibility}, status=201)


def test_shared_write_reaches_every_member_but_not_outsiders(lab, listen):
    goal = _goal(lab)
    assert listen.notified() == {"prof", "alice", "bob"}

    lab["alice"].post(f"/api/goals/{goal['id']}/updates",
                      {"completed": "ran baseline", "no_blocker": True, "publish": True}, status=201)
    msgs = listen.drain()
    assert msgs["prof"] == [{"projects": [lab["pid"]]}]
    assert msgs["bob"] and not msgs["eve"]


def test_private_rows_only_reach_their_author(lab, listen):
    goal = _goal(lab)
    listen.drain()

    lab["alice"].post(f"/api/projects/{lab['pid']}/notes", {"goal_id": goal["id"], "body": "secret"}, status=201)
    assert listen.notified() == {"alice"}

    draft = lab["alice"].post(f"/api/goals/{goal['id']}/updates",
                              {"completed": "wip", "no_blocker": True, "publish": False}, status=201)
    assert listen.notified() == {"alice"}

    _goal(lab, visibility="private")
    assert listen.notified() == {"alice"}

    # Publishing the draft makes it shared, so everyone refreshes.
    lab["alice"].patch(f"/api/updates/{draft['id']}",
                       {"completed": "done", "no_blocker": True, "publish": True})
    assert listen.notified() == {"prof", "alice", "bob"}


def test_link_on_private_goal_only_reaches_its_author(lab, listen):
    goal = _goal(lab, visibility="private")
    listen.drain()
    lab["alice"].post("/api/links", {"target_type": "goal", "target_id": goal["id"], "url": "https://example.com"},
                      status=201)
    assert listen.notified() == {"alice"}


def test_draft_citing_a_blocker_only_reaches_its_author(lab, listen):
    goal = _goal(lab)
    up = lab["bob"].post(f"/api/goals/{goal['id']}/updates",
                         {"completed": "x", "new_blockers": [{"title": "GPU"}], "publish": True}, status=201)
    listen.drain()
    lab["alice"].post(f"/api/goals/{goal['id']}/updates",
                      {"completed": "wip", "referenced_blocker_ids": [up["blockers"][0]["id"]], "publish": False},
                      status=201)
    assert listen.notified() == {"alice"}


def test_writes_without_activity_events_still_notify(lab, listen):
    goal = _goal(lab)
    listen.drain()

    # Links and meeting edits do not write an ActivityEvent; the ORM hook catches them anyway.
    lab["alice"].post("/api/links", {"target_type": "goal", "target_id": goal["id"],
                                     "url": "https://example.com", "label": "doc", "link_type": "document"},
                      status=201)
    assert listen.notified() == {"prof", "alice", "bob"}

    meeting = lab["prof"].post(f"/api/projects/{lab['pid']}/meetings",
                               {"title": "M", "category": "lab", "occurred_at": "2026-11-20T10:00:00+08:00"},
                               status=201)
    listen.drain()
    lab["prof"].patch(f"/api/meetings/{meeting['id']}", {"participant_ids": [lab["ids"]["alice"]]})
    assert listen.notified() == {"prof", "alice", "bob"}


def test_removed_member_is_told_once_more(lab, listen):
    lab["prof"].delete(f"/api/projects/{lab['pid']}/members/{lab['ids']['bob']}")
    assert listen.notified() == {"prof", "alice", "bob"}

    _goal(lab)
    assert listen.notified() == {"prof", "alice"}


def test_failed_request_sends_nothing(lab, listen):
    lab["bob"].patch(f"/api/projects/{lab['pid']}", {"title": "hijack"}, status=403)
    assert listen.notified() == set()


def test_stream_requires_login(session_factory):
    r = TestClient(app).get("/api/stream")
    assert r.status_code == 401


def test_stream_formats_server_sent_events():
    async def first_two():
        gen = live.stream(user_id=42)
        hello = await gen.__anext__()
        live.hub.publish({42: {"projects": [7]}})
        changed = await gen.__anext__()
        await gen.aclose()
        return hello, changed

    hello, changed = asyncio.run(first_two())
    assert "event: ready" in hello and hello.startswith("retry: ")
    assert changed == 'event: changed\ndata: {"projects": [7]}\n\n'
    assert not live.hub.has_subscribers()
