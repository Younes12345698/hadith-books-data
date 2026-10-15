"""Download the upstream data (pinned to upstream/COMMIT) into .cache/ and refresh upstream/ snapshots.

    python tools/fetch_upstream.py              # only the published editions + info.min.json
    python tools/fetch_upstream.py --all        # every edition of the catalogue (~311 MB)
    python tools/fetch_upstream.py ben-muslim   # specific editions

Files are fetched by commit SHA (immutable), never from a moving branch.
"""

import sys
import time
import urllib.request

from common import (
    CACHE,
    ROOT,
    UPSTREAM_REPO,
    configure_output,
    edition_cache_path,
    load_publish_list,
    load_upstream_json,
    pinned_commit,
)

SNAPSHOT_FILES = ["editions.json", "LICENSE", "References.md"]


def download(commit: str, path: str, target):
    url = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{commit}/{path}"
    last_error = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return len(data)
        except Exception as error:  # noqa: BLE001 - report and retry
            last_error = error
            time.sleep(2 * attempt)
    raise SystemExit(f"download failed: {url}: {last_error}")


def main():
    configure_output()
    args = sys.argv[1:]
    commit = pinned_commit()
    print(f"upstream {UPSTREAM_REPO} @ {commit}")

    for name in SNAPSHOT_FILES:
        size = download(commit, name, ROOT / "upstream" / name)
        print(f"  snapshot {name} ({size} bytes)")

    catalogue = load_upstream_json(ROOT / "upstream" / "editions.json")
    all_names = [e["name"] for book in catalogue.values() for e in book["collection"]]

    if "--all" in args:
        wanted = all_names
    elif args:
        wanted = args
    else:
        wanted = load_publish_list()
    unknown = [name for name in wanted if name not in all_names]
    if unknown:
        raise SystemExit(f"not in the upstream catalogue: {unknown}")

    for name in wanted:
        target = edition_cache_path(name)
        if target.exists():
            continue
        size = download(commit, f"editions/{name}.min.json", target)
        print(f"  edition {name} ({size / 1e6:.2f} MB)")

    info = CACHE / "info.min.json"
    if not info.exists():
        size = download(commit, "info.min.json", info)
        print(f"  info.min.json ({size / 1e6:.2f} MB)")
    print("done")


if __name__ == "__main__":
    main()
