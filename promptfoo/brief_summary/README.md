# Prompt test suite: Meeting Brief AI summary

Uses the real model, so it costs money: keep `--repeat` at 3 and do not loop.

    python promptfoo/brief_summary/build.py        (repository root: exports the prompt, builds fixtures)
    cd promptfoo/brief_summary
    npx promptfoo@latest eval --no-cache --repeat 3 -o results_original.json
    python count_results.py results_original.json

Before the first run, the team replaces every `EXPECTED BEHAVIOUR WRITTEN BEFORE THE RUN` in
`tests.yaml` with its own expected behaviour, and writes the P1 prediction.
