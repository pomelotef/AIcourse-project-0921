"""Tests for the real model client in app/ai/llm.py. The Anthropic SDK client is replaced by a
fake, so these tests need no API key and make no network call. They check what the client sends
and how it reads the reply; the other AI tests use a fake model and never reach this code."""
from types import SimpleNamespace

import anthropic

from app.ai import llm


class FakeMessages:
    def __init__(self, content):
        self.content = content
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(content=self.content, stop_reason="end_turn")


def make_client(monkeypatch, content):
    messages = FakeMessages(content)
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: SimpleNamespace(messages=messages))
    return llm.AnthropicClient(model="test-model"), messages


def test_thinking_is_turned_off(monkeypatch):
    # With thinking on, the model can spend all of max_tokens on thinking and return no text.
    client, messages = make_client(monkeypatch, [SimpleNamespace(type="text", text="{}")])
    client.complete("system prompt", "user message")
    assert messages.kwargs["thinking"] == {"type": "disabled"}
    assert messages.kwargs["system"] == "system prompt"
    assert messages.kwargs["messages"] == [{"role": "user", "content": "user message"}]
    assert messages.kwargs["model"] == "test-model"


def test_only_text_blocks_are_returned(monkeypatch):
    content = [
        SimpleNamespace(type="thinking", thinking=""),
        SimpleNamespace(type="text", text='{"status": '),
        SimpleNamespace(type="text", text='"ok"}'),
    ]
    client, _ = make_client(monkeypatch, content)
    assert client.complete("s", "u") == '{"status": "ok"}'


def test_no_text_returns_empty_string(monkeypatch):
    # An empty reply is then rejected by validate() and the page falls back to the plain Brief.
    client, _ = make_client(monkeypatch, [SimpleNamespace(type="thinking", thinking="")])
    assert client.complete("s", "u") == ""
