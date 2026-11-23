"""Meeting Brief AI summary endpoint: permissions, what is (and is not) sent to the model,
and the fallbacks. The model is always a fake here: no API key, no cost."""

import inspect
import json
from types import SimpleNamespace

from app.ai import llm
from app.main import app
from app.routers.ai_summary import get_summary_client

from .conftest import days, iso, now


class FakeClient:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.replies.pop(0)


def use_model(*replies):
    fake = FakeClient(*replies)
    app.dependency_overrides[get_summary_client] = lambda: fake
    return fake


def _meeting_with_records(lab):
    prof, alice, pid = lab["prof"], lab["alice"], lab["pid"]
    goal = prof.post(f"/api/projects/{pid}/goals", {"title": "Vulkan", "assignee_id": lab["ids"]["alice"]}, status=201)
    upd = alice.post(f"/api/goals/{goal['id']}/updates",
                     {"completed": "模型比較完成", "findings": "Gemma 較省記憶體",
                      "new_blockers": [{"title": "Vulkan 編譯失敗"}], "publish": True}, status=201)
    alice.post(f"/api/goals/{goal['id']}/updates", {"completed": "SECRET-DRAFT 還沒想清楚"}, status=201)
    alice.post(f"/api/projects/{pid}/notes", {"body": "SECRET-NOTE 只給自己看", "goal_id": goal["id"]}, status=201)
    alice.post(f"/api/projects/{pid}/goals", {"title": "SECRET-PRIVATE-GOAL", "visibility": "private"}, status=201)
    meeting = prof.post(f"/api/projects/{pid}/meetings", {"title": "M1", "occurred_at": iso(now() + days(1))}, status=201)
    return meeting, upd


def _reply(*points, status="ok", summary="模型比較完成，但 Vulkan 編譯卡住。"):
    return json.dumps({"status": status, "summary": summary,
                       "points": [{"kind": k, "text": t, "record_ids": ids} for k, t, ids in points]},
                      ensure_ascii=False)


def test_disabled_without_an_api_key(lab):
    meeting, _ = _meeting_with_records(lab)
    app.dependency_overrides[get_summary_client] = lambda: None
    r = lab["prof"].post(f"/api/meetings/{meeting['id']}/brief/ai-summary", status=200)
    assert r["status"] == "disabled"


def test_summary_cites_brief_records_and_returns_their_labels(lab):
    meeting, upd = _meeting_with_records(lab)
    pid, bid = f"P{upd['id']}", f"B{upd['blockers'][0]['id']}"
    fake = use_model(_reply(("blocker", "Vulkan 編譯失敗，需要討論。", [bid]), ("progress", "完成模型比較。", [pid])))
    r = lab["alice"].post(f"/api/meetings/{meeting['id']}/brief/ai-summary", status=200)
    assert r["status"] == "ok"
    assert r["records"] == {bid: "Blocker：Vulkan 編譯失敗", pid: "進度更新 · Vulkan"}
    sent = fake.calls[0][1]
    assert f"[{pid}] progress" in sent and "模型比較完成" in sent
    assert f"[{bid}] blocker" in sent


def test_drafts_private_records_and_names_never_reach_the_model(lab):
    meeting, upd = _meeting_with_records(lab)
    fake = use_model(_reply(("progress", "完成模型比較。", [f"P{upd['id']}"])))
    lab["alice"].post(f"/api/meetings/{meeting['id']}/brief/ai-summary", status=200)
    sent = fake.calls[0][1]
    for secret in ("SECRET-DRAFT", "SECRET-NOTE", "SECRET-PRIVATE-GOAL", "alice", "prof", "@test.local"):
        assert secret not in sent, secret
    assert "| student |" in sent          # only the author's role is sent


def test_outsider_gets_404_and_the_model_is_never_called(lab):
    meeting, _ = _meeting_with_records(lab)
    fake = use_model()
    lab["eve"].post(f"/api/meetings/{meeting['id']}/brief/ai-summary", status=404)
    assert fake.calls == []


def test_invented_citation_falls_back_to_the_plain_brief(lab):
    meeting, _ = _meeting_with_records(lab)
    invented = _reply(("progress", "完成。", ["P999"]))
    fake = use_model(invented, invented)
    r = lab["prof"].post(f"/api/meetings/{meeting['id']}/brief/ai-summary", status=200)
    assert r["status"] == "unavailable" and r["points"] == [] and r["records"] == {}
    assert len(fake.calls) == 2


def test_meeting_with_nothing_to_summarize_does_not_call_the_model(lab):
    meeting = lab["prof"].post(f"/api/projects/{lab['pid']}/meetings",
                               {"title": "Empty", "occurred_at": iso(now() + days(1))}, status=201)
    fake = use_model()
    r = lab["prof"].post(f"/api/meetings/{meeting['id']}/brief/ai-summary", status=200)
    assert r["status"] == "insufficient_data"
    assert fake.calls == []


def test_real_client_is_off_without_a_key_and_reads_text_blocks(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.get_client() is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    client = llm.get_client()
    params = inspect.signature(client._client.messages.create).parameters
    assert {"model", "max_tokens", "system", "messages"} <= set(params)
    seen = {}

    def fake_create(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"status": "ok"}')])

    client._client.messages.create = fake_create
    assert client.complete("SYS", "USER") == '{"status": "ok"}'
    assert seen["system"] == "SYS" and seen["messages"] == [{"role": "user", "content": "USER"}]
