#!/usr/bin/env python3
"""CyberForge category-5 verification: the reward of the task follows only from this
file and oracle.json (the rule itself is cf_oracle.py, the task server's self-check uses
the same file).

  verify.py check  <response.json>   exit 0 when that /verify response passes
  verify.py reward <response.json>|- write /logs/verifier/reward.json and reward.txt
                                     (- = no submission passed)

The task server's /verify response holds one record per run of the PoC on each build
({"vul": [...], "fix": [...]}, see cf_oracle.py); oracle.json says which rule applies.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cf_oracle  # noqa: E402

ORACLE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "oracle.json")))


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("check", "reward"):
        print(__doc__)
        sys.exit(2)
    resp = None if sys.argv[2] == "-" else json.load(open(sys.argv[2]))
    if sys.argv[1] == "check":
        ok, why = cf_oracle.decide(ORACLE, resp.get("vul"), resp.get("fix"))
        print("  %s: %s" % ("PASS" if ok else "FAIL", why))
        sys.exit(0 if ok else 1)
    ok, why = (False, "no PoC passed") if resp is None else cf_oracle.decide(ORACLE, resp.get("vul"), resp.get("fix"))
    result = {"reward": 1.0 if ok else 0.0, "oracle": ORACLE.get("type", "crash"), "why": why,
              "vul_runs": resp.get("vul") if resp else None, "fix_runs": resp.get("fix") if resp else None}
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/reward.json").write_text(json.dumps(result, indent=2))
    Path("/logs/verifier/reward.txt").write_text(str(result["reward"]))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
