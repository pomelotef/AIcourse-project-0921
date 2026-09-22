##This is a first draft, not the finished product.


# Section 1 — What AI tools we plan to use, and what we will use each for

"We will use Claude Haiku for quick syntax checks and one-off debugging questions — not for code that gets merged to main without review."<br>
"We will use GitHub Copilot's inline autocomplete while typing — not as a substitute for writing the PR description or DECISIONS.md entry ourselves."<br>
"We will use Claude to brainstorm and compare architecture options before we commit to a design — not to make the final call; that's a team discussion, recorded in DECISIONS.md."<br>

# Section 2 — How we will document AI interactions
"Every meaningful prompt used to generate code that ends up in the repo goes in the prompt engineering log: the prompt text, the model used, and what we kept vs. changed. Insignificant prompts include One-off debugging questions and syntax lookup."<br>

# Section 3 — How we will handle disagreements about AI output quality
"If two engineers disagree about whether AI-generated code is good enough to merge, we will resolve to discussion, if needed, voting."<br>
"Evidence required before a merge decision: passes the existing test suite, passes the PR review checklist, and can be explained by someone other than whoever generated it."<br>
"If the disagreement is about style or preference rather than correctness, we defer to the team's existing style guide and linter config rather than debating it case by case."<br>
