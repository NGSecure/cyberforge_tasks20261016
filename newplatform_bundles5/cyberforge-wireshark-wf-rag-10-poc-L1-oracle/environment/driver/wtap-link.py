#!/usr/bin/env python3
"""Build helper of these tasks (category 5):
prints the libraries the project's own fuzzshark_ip fuzzer is linked with (LINK_FLAGS and
LINK_LIBRARIES of its link statement in /work/build/build.ninja), with relative paths made
absolute and the fuzzing engine (-fsanitize=fuzzer, libFuzzingEngine) left out, so that the
judge links its wiretap driver with the same static libwiretap.a, libwsutil.a and system
libraries as the build's fuzzers. If build.ninja has no such statement, a fixed list of the
libraries libwiretap and libwsutil need is printed instead."""
import os
import re
import shlex
import subprocess

BUILD = os.environ.get("CF_WS_BUILD", "/work/build")
FALLBACK = ["run/libwiretap.a", "run/libwsutil.a"]


def link_vars(text):
    """{var: value} of the first link statement of a fuzzshark program in build.ninja."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if re.match(r"build run/fuzzshark(_ip)?: ", line) or re.match(r"build run/fuzzshark_\S+: ", line):
            out = {}
            for v in lines[i + 1:]:
                if not v.startswith("  "):
                    break
                k, _, val = v.strip().partition(" = ")
                out[k] = val
            if "LINK_LIBRARIES" in out:
                return out
    return None


def absolute(tok):
    if tok.startswith("-") or os.path.isabs(tok):
        return tok
    p = os.path.join(BUILD, tok)
    return p if os.path.exists(p) else tok


def main():
    try:
        text = open(os.path.join(BUILD, "build.ninja"), encoding="utf-8", errors="replace").read()
    except OSError:
        text = ""
    v = link_vars(text)
    if v:
        toks = shlex.split(v.get("LINK_FLAGS", "")) + shlex.split(v["LINK_LIBRARIES"])
    else:
        glib = subprocess.run(["pkg-config", "--static", "--libs", "glib-2.0", "gmodule-2.0"],
                              capture_output=True, text=True).stdout.split()
        opt = ["-l" + n for n in ("zstd", "lz4", "xxhash")  # optional libraries, if installed
               if any(os.path.exists("%s/lib%s.%s" % (d, n, e)) for d in ("/usr/lib/x86_64-linux-gnu", "/usr/local/lib")
                      for e in ("a", "so"))]
        xml = ["/usr/local/lib/libxml2.a"] if os.path.exists("/usr/local/lib/libxml2.a") else []
        toks = FALLBACK + xml + opt + glib + ["-lgcrypt", "-lgpg-error", "-lz", "-lm", "-ldl", "-lpthread"]
    keep = [absolute(t) for t in toks
            if t not in ("-fsanitize=fuzzer", "-pie") and "libFuzzingEngine" not in t and t != "$LIB_FUZZING_ENGINE"]
    print(" ".join(keep))  # read back by $(cat ...): no token holds a space


if __name__ == "__main__":
    main()
