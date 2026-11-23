"""Model client for LabPulse AI features.

The real client is created only when ANTHROPIC_API_KEY is set, so the tests, CI and
anyone without a key can run the app: the AI summary is then simply turned off.
"""
import os

DEFAULT_MODEL = "claude-haiku-5-5"


class AnthropicClient:
    """Sends one system prompt and one user message, returns the reply text."""

    def __init__(self, model=None, max_tokens=800, timeout=30.0):
        import anthropic  # imported here so tests never need the package or a key

        self._client = anthropic.Anthropic(timeout=timeout, max_retries=1)
        self.model = model or os.environ.get("LABPULSE_AI_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens

    def complete(self, system, user):
        message = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in message.content if block.type == "text")


def get_client():
    """The real client, or None when no API key is set (the AI summary is then off)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    return AnthropicClient()
