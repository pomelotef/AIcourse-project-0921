# Prompt test suite: Meeting Brief AI summary

Uses the real model, so it costs money: keep `--repeat` at 3 and do not loop.

    python promptfoo/brief_summary/build.py        (repository root: exports the prompt, builds fixtures)
    cd promptfoo/brief_summary
    npx promptfoo@latest eval --no-cache --repeat 3 -o results_original.json
    python count_results.py results_original.json

Each description in `tests.yaml` states the expected behaviour, written before the first run (who
and when: top of `tests.yaml`). Add a new case the same way: write the expectation first, then run.
