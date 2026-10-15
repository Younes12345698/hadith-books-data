"""Verify data/v1 against the pinned upstream snapshot. Exit code 1 on any error.

    python tools/verify.py                       # the committed data/v1
    python tools/verify.py --root .local-all --all

Checks: file sizes and SHA-256 of every file listed in index.json, valid gzip/JSON and structure,
texts / numbers / section titles identical to upstream, references and grades identical to upstream and to
info.min.json, no unreferenced files, and (without --all) that no held edition is present.
"""

import argparse
import gzip
import json
import re
import sys

NUMBER_RE = re.compile(r"^\d{1,6}(\.\d{1,4})?$")

from common import CACHE, ROOT, SCHEMA, configure_output, edition_cache_path, load_publish_list, load_upstream_json, sha256_hex

errors = []


def error(message):
    errors.append(message)
    if len(errors) <= 40:
        print("ERROR:", message)


def read_blob(root, entry, label):
    path = root / entry["path"]
    if not path.exists():
        error(f"{label}: missing file {entry['path']}")
        return None
    data = path.read_bytes()
    if len(data) != entry["bytes"]:
        error(f"{label}: size {len(data)} != index {entry['bytes']}")
    if sha256_hex(data) != entry["sha256"]:
        error(f"{label}: sha256 differs from the index")
    if entry["sha256"][:8] not in path.name:
        error(f"{label}: file name does not carry the hash")
    try:
        return json.loads(gzip.decompress(data).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        error(f"{label}: cannot read ({exc})")
        return None


def grades_of(core, row):
    return [(core["S"][s], core["G"][g][0]) for s, g in row[4]]


def main():
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    parser.add_argument("--all", action="store_true")
    options = parser.parse_args()
    root = (ROOT / options.root) if options.root else ROOT

    index = json.loads((root / "data" / "v1" / "index.json").read_text(encoding="utf-8"))
    published = set(load_publish_list())
    info = load_upstream_json(CACHE / "info.min.json")
    if index.get("schema") != SCHEMA:
        error(f"unexpected schema {index.get('schema')}")

    referenced = set()
    stats = {"hadiths": 0, "empty": 0, "no_arabicnumber": 0, "fractional": 0, "grade_entries": 0, "grade_classified": 0}
    for book in index["books"]:
        book_id = book["id"]
        pivot = load_upstream_json(edition_cache_path(f"ara-{book_id}"))
        up = pivot["hadiths"]
        core = read_blob(root, book["core"], f"{book_id}/core")
        referenced.add(book["core"]["path"])
        if core:
            if core.get("v") != SCHEMA or core.get("book") != book_id:
                error(f"{book_id}/core: wrong header")
            if len(core["h"]) != len(up) or book["count"] != len(up) or book["core"].get("count") != len(up):
                error(f"{book_id}/core: count {len(core['h'])} != upstream {len(up)}")
            info_by_number = {h["hadithnumber"]: h for h in info[book_id]["hadiths"]}
            any_grade = False
            for row, source in zip(core["h"], up):
                number = source["hadithnumber"]
                reference = source.get("reference") or {}
                expected = (number, source.get("arabicnumber"), reference.get("book"), reference.get("hadith"))
                if tuple(row[:4]) != expected:
                    error(f"{book_id}/core #{number}: row {row[:4]} != upstream {expected}")
                source_grades = [(g["name"], g["grade"]) for g in source.get("grades") or []]
                if grades_of(core, row) != source_grades:
                    error(f"{book_id}/core #{number}: grades differ from upstream")
                any_grade = any_grade or bool(source_grades)
                reference_info = info_by_number.get(number)
                if reference_info is None:
                    error(f"{book_id} #{number}: not in info.min.json")
                else:
                    info_grades = [(g["name"], g["grade"]) for g in reference_info.get("grades") or []]
                    if info_grades != source_grades or reference_info.get("reference") != source.get("reference"):
                        error(f"{book_id} #{number}: edition and info.min.json disagree")
                if not NUMBER_RE.match(number):
                    error(f"{book_id} #{number}: hadith number is not numeric (the app builds links from it)")
                if "arabicnumber" not in source:
                    stats["no_arabicnumber"] += 1
                if "." in number:
                    stats["fractional"] += 1
                for _, gi in row[4]:
                    stats["grade_entries"] += 1
                    stats["grade_classified"] += core["G"][gi][1] != "o"
            if any_grade != book["hasGrades"]:
                error(f"{book_id}: hasGrades flag is wrong")
            if len(info_by_number) != len(up):
                error(f"{book_id}: info.min.json has {len(info_by_number)} hadiths, edition {len(up)}")

        for edition in book["editions"]:
            name = edition["id"]
            label = f"{book_id}/{name}"
            referenced.add(edition["path"])
            if not options.all and (name not in published or edition.get("held")):
                error(f"{label}: held edition found in the published data")
            if not options.all and name not in published:
                continue
            pack = read_blob(root, edition, label)
            cache = edition_cache_path(name)
            if pack is None or not cache.exists():
                if pack is not None:
                    error(f"{label}: upstream file not downloaded, cannot compare")
                continue
            upstream = load_upstream_json(cache)
            numbers = [h["hadithnumber"] for h in upstream["hadiths"]]
            texts = [h["text"] for h in upstream["hadiths"]]
            if pack.get("v") != SCHEMA or pack.get("id") != name or pack.get("book") != book_id:
                error(f"{label}: wrong header")
            if pack["n"] != numbers:
                error(f"{label}: hadith numbers differ from upstream")
            if pack["t"] != texts:
                bad = [n for n, a, b in zip(pack["n"], pack["t"], texts) if a != b]
                error(f"{label}: {len(bad)} texts differ from upstream (first: {bad[:3]})")
            if pack["sections"] != upstream["metadata"]["sections"]:
                error(f"{label}: section titles differ from upstream")
            titles_file = ROOT / "titles" / "ar" / f"{book_id}.json"
            expected_ar = json.loads(titles_file.read_text(encoding="utf-8")) if name == f"ara-{book_id}" and titles_file.exists() else None
            if (pack.get("sections_ar") or None) != expected_ar:
                error(f"{label}: sections_ar differs from titles/ar/{book_id}.json")
            elif expected_ar:
                english = upstream["metadata"]["sections"]
                used = {str(h["reference"]["book"]) for h in upstream["hadiths"] if h.get("reference")}
                for key in expected_ar:
                    if not english.get(key, "").strip():
                        error(f"{label}: Arabic title for section {key} which has no English title")
                for key in used:
                    if english.get(key, "").strip() and key not in expected_ar:
                        error(f"{label}: section {key} has an English title but no Arabic one")
            empty = sum(1 for t in texts if not t.strip())
            if edition["count"] != len(numbers) or edition["emptyCount"] != empty:
                error(f"{label}: count/emptyCount in the index are wrong")
            if name == f"ara-{book_id}":
                stats["hadiths"] += len(numbers)
                stats["empty"] += empty
            if core and name != f"ara-{book_id}":
                known = {row[0] for row in core["h"]}
                extra = [n for n in pack["n"] if n not in known]
                if extra:
                    print(f"note: {label}: {len(extra)} hadith numbers are not in the Arabic numbering (first {extra[:3]})")

    data_dir = root / "data" / "v1" / "books"
    for path in data_dir.rglob("*.json.gz"):
        if path.relative_to(root).as_posix() not in referenced:
            error(f"unreferenced file {path.relative_to(root).as_posix()}")

    if stats["grade_entries"]:
        share = 100 * stats["grade_classified"] / stats["grade_entries"]
        print(f"grades: {stats['grade_entries']} entries, {share:.1f}% classified s/hs/h/d, rest shown as 'other'")
    print(
        f"arabic hadiths: {stats['hadiths']} (empty text in source: {stats['empty']}, "
        f"without arabicnumber: {stats['no_arabicnumber']}, fractional numbers: {stats['fractional']})"
    )
    if errors:
        print(f"FAILED with {len(errors)} errors")
        sys.exit(1)
    print("OK: every file matches the index and the pinned upstream data")


if __name__ == "__main__":
    main()
