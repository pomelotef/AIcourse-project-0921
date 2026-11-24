# Prompt card: Meeting Brief AI summary

| Field | Content |
|---|---|
| Name | Meeting Brief AI summary (`backend/app/ai/brief_summary.py`, endpoint `POST /api/meetings/{id}/brief/ai-summary`) |
| Purpose | Before a meeting, turn the records the Brief already shows into a 1-3 sentence summary and up to 6 discussion points, each citing its records. It supports the evaluation goal of shorter meeting preparation; it does not replace the Brief, and the professor still makes every decision. |
| Model | `claude-haiku-5-5` by default; set `LABPULSE_AI_MODEL` to change it. Off (status `disabled`) when `ANTHROPIC_API_KEY` is not set. |
| Input | Exactly the Brief's records, so the same permission rules apply: published updates (P), open blockers (B, as blockers), blockers resolved in the window (B, as progress), previous commitments and carried-over actions with their state (A), decisions of the previous meeting (D). The most recent 40, each cut to 400 characters. Only the author's role is sent, never names or emails. Record text is untrusted data. |
| Output | One JSON object: `status` (`ok` or `insufficient_data`), `summary`, `points` (`kind`, `text`, `record_ids`). The endpoint adds `records`, a label for every cited ID. |
| Checks in code | `validate()`: bare JSON, allowed values, at most 6 points, length limits, and every cited ID must be one of the input records. One retry with the problems listed; after that the page says the summary is unavailable and the Brief stays as it is. A Brief with no records never reaches the model. |
| Known limits | The validator can prove that a cited record exists, not that the sentence says what the record says. The meeting agenda is not sent yet. Untested so far: records in mixed languages within one meeting, more than 40 records, and models other than the default. |
| Tests | Layer 1: `backend/tests/test_brief_summary.py` and `backend/tests/test_ai_summary_api.py` (fake model, run in CI). Layer 2: `promptfoo/brief_summary/` (real model, run by hand with `--repeat 3`). |
| Owner | (name) |
| Last updated | (date) |
