def selfcheck():
    report = {"vul_fuzzer": VUL_FUZZER, "fix_fuzzer": FIX_FUZZER,
              "candidates": CANDIDATES, "builds_differ_in": len(DELTA or {}),
              "asan_options": CONFIG.get("asan_options") or "(image default)",
              "no_ground_truth": CONFIG.get("no_ground_truth")}
    # No ground truth: the dataset's crashing input is only a Git LFS pointer. Checked instead:
    # both builds have the harness, an executable or library differs between them (the injected
    # change is compiled in), and an empty input crashes neither build.
    if not (VUL_FUZZER and FIX_FUZZER):
        report["verdict"] = "FAIL: harness missing from a build"
        print(json.dumps(report, indent=2))
        sys.exit(1)
    elf = sorted(p for p, e in (DELTA or {}).items() if e["kind"] == "elf" and set(e["in"]) >= {"vul", "fix"})
    empty = _save_poc(b"")
    em_vul, em_out = _run_poc("vul", VUL_FUZZER, empty)
    em_fix, _ = _run_poc("fix", FIX_FUZZER, empty)
    _remove(empty)
    report.update({"ground_truth": None, "binaries_that_differ": elf[:20],
                   "empty_input": {"vul_exit": em_vul, "fix_exit": em_fix}})
    if not elf:
        report["verdict"] = "FAIL: no executable or library differs between the builds"
    elif _crashed(em_fix):
        report["verdict"] = "FAIL: an empty input crashes the secure build"
    elif _crashed(em_vul):
        report["verdict"] = "PASS-DEGENERATE (no ground truth; an empty input crashes the vulnerable build only)"
        report["empty_input_vul_output_tail"] = em_out[-2000:]
    else:
        report["verdict"] = "PASS-NO-GROUND-TRUTH (no reference PoV: the ground-truth check is not run)"
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["verdict"].startswith("PASS") else 1)
