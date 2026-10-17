#!/usr/bin/env python3
"""Inventory what the CyberForge base images' docker-commit snapshot layers added.

    python3 -I scan_snapshots.py records.json snapshot_scan/ [PROJECT ...]

The `vuljector/<project>:setup` images are the project's OSS-Fuzz setup image plus
one or more `docker commit` layers taken while the dataset was produced (a full
compile of the secure tree, /opt/src_snapshot.tar, unit-test scripts, caches...).
For every tier-A project with a published image this reads the image config from
Docker Hub, takes the layers after the last Dockerfile instruction, streams them
(nothing is stored) and writes snapshot_scan/<project>.json:

    image, digest (what `docker pull <image>` resolves to; FROM lines pin it),
    setup_end (creation time of the last Dockerfile layer), post_layers,
    post_setup_files (every non-directory entry of those layers),
    deleted (whiteouts: setup files the snapshot removed)

convert.py turns post_setup_files into each bundle's build/snapshot_residue.txt.
Existing outputs are kept; delete one to rescan it. The tag -> digest lookup uses
the Docker Hub web API; each image then costs one registry manifest GET (anonymous
Docker Hub access allows ~100 per hour) plus streamed layer blobs.
"""
import json
import os
import re
import ssl
import sys
import tarfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

CA = "/root/.ccr/ca-bundle.crt"  # proxy CA where present; system store otherwise
CTX = ssl.create_default_context(cafile=CA if os.path.exists(CA) else None)
MANIFEST = "application/vnd.docker.distribution.manifest.v2+json,application/vnd.oci.image.manifest.v1+json"
DOCKERFILE = re.compile(r"^(RUN|COPY|ADD|WORKDIR|ENV|ARG|LABEL|USER|CMD|ENTRYPOINT|EXPOSE|VOLUME|SHELL|"
                        r"STOPSIGNAL|HEALTHCHECK|ONBUILD|MAINTAINER)\b|^/bin/(ba)?sh -c |^\|\d+ ")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_api = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX), _NoRedirect)
_web = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX))


def _token(repo):
    u = "https://auth.docker.io/token?service=registry.docker.io&scope=repository:%s:pull" % repo
    return json.load(_web.open(u, timeout=60))["token"]


def _req(repo, path, tok, accept=None, method="GET"):
    r = urllib.request.Request("https://registry-1.docker.io/v2/%s/%s" % (repo, path), method=method)
    r.add_header("Authorization", "Bearer " + tok)
    if accept:
        r.add_header("Accept", accept)
    try:
        return _api.open(r, timeout=300)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):  # blob -> CDN; do not forward the token
            return _web.open(e.headers["Location"], timeout=600)
        raise


def _hub_digest(repo, tag):
    """Tag -> manifest digest via the Docker Hub web API (not counted as a pull)."""
    info = json.load(_web.open("https://hub.docker.com/v2/repositories/%s/tags/%s" % (repo, tag), timeout=60))
    imgs = info.get("images") or []
    if len(imgs) != 1 or imgs[0].get("architecture") != "amd64" or imgs[0].get("digest") != info.get("digest"):
        raise RuntimeError("%s:%s is not a single linux/amd64 manifest" % (repo, tag))
    return info["digest"]


def scan(project, image):
    repo, tag = image.rsplit(":", 1)
    digest = _hub_digest(repo, tag)
    tok = _token(repo)
    # by digest, so the layers read are exactly the ones the FROM lines pin
    man = json.load(_req(repo, "manifests/" + digest, tok, MANIFEST))
    if "layers" not in man:
        raise RuntimeError("%s is a multi-platform index; scan its linux/amd64 manifest" % image)
    cfg = json.load(_req(repo, "blobs/" + man["config"]["digest"], tok))
    entries, li = [], 0
    for h in cfg.get("history", []):
        e = {"created": h.get("created"), "created_by": (h.get("created_by") or "").strip()}
        if not h.get("empty_layer"):
            e["layer"] = li
            li += 1
        entries.append(e)
    last_df = max(i for i, e in enumerate(entries) if DOCKERFILE.search(e["created_by"]))
    post = [e for e in entries[last_df + 1:] if "layer" in e]
    files, deleted = set(), set()
    for e in post:
        blob = man["layers"][e["layer"]]["digest"]
        with tarfile.open(fileobj=_req(repo, "blobs/" + blob, tok), mode="r|*") as tf:
            for m in tf:
                p = "/" + m.name.lstrip("./")
                base = os.path.basename(p)
                if base.startswith(".wh."):
                    if base != ".wh..wh..opq":
                        deleted.add(os.path.join(os.path.dirname(p), base[4:]))
                elif not m.isdir():
                    files.add(p)
    return {"project": project, "image": image, "digest": digest,
            "setup_end": entries[last_df]["created"],
            "post_layers": [{"created": e["created"], "created_by": e["created_by"],
                             "size": man["layers"][e["layer"]]["size"]} for e in post],
            "post_setup_files": sorted(files), "deleted": sorted(deleted - files)}


def main():
    recs = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2]
    only = set(sys.argv[3:])
    os.makedirs(out, exist_ok=True)
    # named projects are scanned whatever their tier (tier-B/C conversion needs them too)
    todo = sorted({(r["project"], r["dockerhub_image"]) for r in recs
                   if (r["project"] in only if only else r["tier"] == "A") and r["dockerhub_image"]
                   and not os.path.exists(os.path.join(out, r["project"] + ".json"))})
    print("to scan:", len(todo), flush=True)

    def one(item):
        project, image = item
        err = ""
        for attempt in range(3):
            try:
                res = scan(project, image)
                dst = os.path.join(out, project + ".json")
                with open(dst + ".tmp", "w", encoding="utf-8") as f:
                    json.dump(res, f, indent=0)
                os.replace(dst + ".tmp", dst)
                return "%s: %d post-setup layer(s), %d files" % (project, len(res["post_layers"]),
                                                                 len(res["post_setup_files"]))
            except Exception as ex:  # transient stream/registry errors: retry
                err = repr(ex)[:200]
                time.sleep(10 * (attempt + 1))
        return "%s: ERROR %s" % (project, err)

    bad = 0
    with ThreadPoolExecutor(4) as ex:
        for msg in ex.map(one, todo):
            bad += "ERROR" in msg
            print(msg, flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
