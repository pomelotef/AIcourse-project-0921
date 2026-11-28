"""Export the summary prompt and build one PromptFoo fixture per case.

Run from the repository root:   python promptfoo/brief_summary/build.py
Run it again after any change to SYSTEM_PROMPT, build_user_message or cases/.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))

from app.ai import brief_summary as bs  # noqa: E402


def main():
    (HERE / "prompts").mkdir(exist_ok=True)
    prompt = [{"role": "system", "content": bs.SYSTEM_PROMPT},
              {"role": "user", "content": "{{input}}"}]
    (HERE / "prompts" / "brief_summary.json").write_text(
        json.dumps(prompt, ensure_ascii=False, indent=2), encoding="utf-8")
    out = HERE / "fixtures"
    out.mkdir(exist_ok=True)
    cases = sorted((HERE / "cases").glob("*.json"))
    for case in cases:
        records = json.loads(case.read_text(encoding="utf-8"))
        prepared = bs.prepare_records(records)
        message = bs.build_user_message(prepared, omitted=len(records) - len(prepared))
        (out / (case.stem + ".txt")).write_text(message, encoding="utf-8")
    print(f"exported the prompt and wrote {len(cases)} fixture(s) to {out}")


if __name__ == "__main__":
    main()
