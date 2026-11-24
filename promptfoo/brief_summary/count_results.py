"""count_results.py - per-test pass counts from one PromptFoo JSON results file.

Run from the promptfoo folder:
    python count_results.py results_original.json
"""
import json
import sys


def main(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = data["results"]["results"]
    rows.sort(key=lambda r: (r.get("testIdx", 0), r.get("repeatIndex", 0)))
    groups = {}
    for r in rows:
        desc = (r.get("testCase") or {}).get("description") or "test " + str(r.get("testIdx"))
        g = groups.setdefault(desc, {"passed": 0, "runs": 0, "reasons": []})
        g["runs"] += 1
        if r.get("success"):
            g["passed"] += 1
        else:
            reason = (r.get("gradingResult") or {}).get("reason") or r.get("error") or "no reason given"
            reason = " ".join(str(reason).split())[:110]
            g["reasons"].append("run " + str(r.get("repeatIndex", "?")) + ": " + reason)
    print("ID   passed/runs  result   description")
    for desc, g in groups.items():
        if g["passed"] == g["runs"]:
            verdict = "pass"
        elif g["passed"] == 0:
            verdict = "FAIL"
        else:
            verdict = "FLAKY"
        count = str(g["passed"]) + "/" + str(g["runs"])
        print(f"{desc.split()[0]:<5}{count:<13}{verdict:<9}{desc[:70]}")
        for line in g["reasons"]:
            print(" " * 27 + line)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1])
