##This is a first draft, not the finished product.


Section 1 — What AI tools we plan to use, and what we will use each for

"We will use Claude Sonnet (via the API) for generating boilerplate CRUD endpoints and first-draft unit tests — not for anything touching authentication or payment logic, which a human writes from scratch."
"We will use Claude Haiku for quick syntax checks and one-off debugging questions — not for code that gets merged to main without review."
"We will use GitHub Copilot's inline autocomplete while typing — not as a substitute for writing the PR description or DECISIONS.md entry ourselves."
"We will use Claude to brainstorm and compare architecture options before we commit to a design — not to make the final call; that's a team discussion, recorded in DECISIONS.md."
"We will use Claude to draft the first pass of docstrings and API documentation — a human always reviews and edits before it's merged."
"We will use Claude to generate an initial test skeleton for a new module — a human adds edge cases and confirms coverage before it counts as done."

Section 2 — How we will document AI interactions
"Every prompt used to generate code that ends up in the repo goes in the prompt engineering log: the prompt text, the model used, and what we kept vs. changed."
"One-off debugging questions or syntax lookups don't need a log entry — only prompts that produced code, text, or decisions that ended up in the repo."
"The PR description's 'what this PR does' field always names whether AI was involved, even in one sentence — it's not a copy of the full log entry, just a pointer to it."
"If an AI suggestion changed our actual approach — for example, it proposed a different data model than we'd planned — that's a DECISIONS.md entry, not just a prompt log entry."

Section 3 — How we will handle disagreements about AI output quality
"If two engineers disagree about whether AI-generated code is good enough to merge, the code steward has final say — not whoever wrote the prompt, and not whoever has more experience."
"Evidence required before a merge decision: passes the existing test suite, passes the PR review checklist, and can be explained by someone other than whoever generated it."
"If the disagreement is about style or preference rather than correctness, we defer to the team's existing style guide and linter config rather than debating it case by case."
"A vote is not evidence. If the team can't resolve it using the criteria above, the code steward's call is final, and gets one sentence in DECISIONS.md explaining why."