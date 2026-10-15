"""Build the app-facing data files from the pinned upstream snapshot.

    python tools/build.py                 # published editions -> data/v1  (what gets committed)
    python tools/build.py --all --out .local-all
                                          # every edition -> .local-all/data/v1  (local testing only, never committed)

Per book:
  core.<sha8>.json.gz        language-neutral: per-hadith numbers, reference, grades (built from the Arabic edition)
  <edition>.<sha8>.json.gz   texts only: hadith numbers (as written in the source) + texts + section titles

Texts and numbers are copied exactly as in the source: no cleaning, no normalisation, no repair.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

from common import (
    GRADE_CLASSES,
    LANGUAGE_CODES,
    RTL_LANGUAGE_CODES,
    ROOT,
    SCHEMA,
    UPSTREAM_REPO,
    configure_output,
    dump_json,
    edition_cache_path,
    gzip_bytes,
    load_publish_list,
    load_upstream_json,
    pinned_commit,
    sha256_hex,
)


def fail(message):
    raise SystemExit(f"BUILD FAILED: {message}")


def load_arabic_titles(book_id, upstream):
    """Arabic renderings of the English section titles (titles/ar/<book>.json) — our own addition, not upstream data.

    Every key must be an upstream section id with a non-empty English title, and every used section that has an
    English title must be covered, so nothing is invented and nothing is left half-translated.
    """
    path = ROOT / "titles" / "ar" / f"{book_id}.json"
    if not path.exists():
        return None
    titles = json.loads(path.read_text(encoding="utf-8"))
    english = upstream["metadata"]["sections"]
    for key, value in titles.items():
        if not isinstance(value, str) or not value.strip():
            fail(f"titles/ar/{book_id}.json: empty title for section {key}")
        if not english.get(key, "").strip():
            fail(f"titles/ar/{book_id}.json: section {key} has no English title upstream")
    used = {str(h["reference"]["book"]) for h in upstream["hadiths"] if h.get("reference")}
    missing = sorted(k for k in used if english.get(k, "").strip() and k not in titles)
    if missing:
        fail(f"titles/ar/{book_id}.json: no Arabic title for sections {missing}")
    return titles


NAME_LANGUAGES = {"ar", "de", "fr", "es", "tr", "ur", "ms", "bn", "fa", "id"}


def load_book_names():
    """Names of the collections per language (titles/book-names.json); a missing language means "show the English name"."""
    data = json.loads((ROOT / "titles" / "book-names.json").read_text(encoding="utf-8"))
    names = {}
    for book, per_language in data.items():
        if book.startswith("_"):
            continue
        for language, value in per_language.items():
            if language not in NAME_LANGUAGES:
                fail(f"titles/book-names.json: unknown language {language!r} for {book}")
            if not isinstance(value, str) or not value.strip():
                fail(f"titles/book-names.json: empty name for {book}/{language}")
        names[book] = per_language
    return names


def build_edition_pack(book_id, name, upstream, sections_ar=None):
    sections = upstream["metadata"]["sections"]
    numbers, texts, seen = [], [], set()
    for hadith in upstream["hadiths"]:
        number, text = hadith.get("hadithnumber"), hadith.get("text")
        if not isinstance(number, str) or not isinstance(text, str):
            fail(f"{name}: hadith without a number/text: {hadith!r}")
        if number in seen:
            fail(f"{name}: duplicate hadith number {number}")
        seen.add(number)
        numbers.append(number)
        texts.append(text)
    pack = {"v": SCHEMA, "id": name, "book": book_id, "sections": sections, "n": numbers, "t": texts}
    if sections_ar:
        pack["sections_ar"] = sections_ar
    empty = sum(1 for text in texts if not text.strip())
    return pack, empty


def build_core(book_id, pivot):
    scholars, scholar_index = [], {}
    grades, grade_index = [], {}
    rows = []
    section_ids = set()
    has_grades = False
    for hadith in pivot["hadiths"]:
        reference = hadith.get("reference") or {}
        picks = []
        for grade in hadith.get("grades") or []:
            if set(grade) != {"name", "grade"}:
                fail(f"{book_id}: unexpected grade fields {sorted(grade)}")
            scholar, text = grade["name"], grade["grade"]
            if scholar not in scholar_index:
                scholar_index[scholar] = len(scholars)
                scholars.append(scholar)
            if text not in grade_index:
                grade_index[text] = len(grades)
                grades.append([text, GRADE_CLASSES.get(text.strip(), "o")])
            picks.append([scholar_index[scholar], grade_index[text]])
        has_grades = has_grades or bool(picks)
        book_ref = reference.get("book")
        if book_ref is not None:
            section_ids.add(book_ref)
        rows.append(
            [hadith["hadithnumber"], hadith.get("arabicnumber"), book_ref, reference.get("hadith"), picks]
        )
    core = {"v": SCHEMA, "book": book_id, "S": scholars, "G": grades, "h": rows}
    return core, has_grades, len(section_ids)


def write_blob(directory: Path, stem: str, value, root: Path):
    data = gzip_bytes(dump_json(value))
    digest = sha256_hex(data)
    path = directory / f"{stem}.{digest[:8]}.json.gz"
    directory.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": len(data),
        "sha256": digest,
    }


def main():
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="include held editions (local testing only)")
    parser.add_argument("--out", default=None, help="output root (default: the repository root)")
    parser.add_argument(
        "--only",
        default=None,
        help="with --all: comma-separated held editions to build besides the published ones (local testing)",
    )
    options = parser.parse_args()

    out_root = (ROOT / options.out) if options.out else ROOT
    if options.all and not options.out:
        fail("--all needs --out so that held editions can never land in the committed data/v1")
    if options.all and out_root.resolve() == ROOT.resolve():
        fail("--all must not write into the repository root")
    only = set(options.only.split(",")) if options.only else None
    if only is not None and not options.all:
        fail("--only needs --all")
    data_dir = out_root / "data" / "v1"

    catalogue = load_upstream_json(ROOT / "upstream" / "editions.json")
    published = set(load_publish_list())
    catalogue_names = {e["name"] for book in catalogue.values() for e in book["collection"]}
    missing = published - catalogue_names
    if missing:
        fail(f"publish.json lists editions that do not exist upstream: {sorted(missing)}")

    book_names = load_book_names()
    books_out, referenced = [], set()
    totals = {"editions": 0, "bytes": 0}
    for book_id in sorted(catalogue):
        book = catalogue[book_id]
        entries = [
            e
            for e in book["collection"]
            if e["name"] in published or (options.all and (only is None or e["name"] in only))
        ]
        if not entries:
            continue
        pivot_name = f"ara-{book_id}"
        if pivot_name not in {e["name"] for e in entries}:
            fail(f"{book_id}: the Arabic edition {pivot_name} is required (numbering, references, grades)")

        book_dir = data_dir / "books" / book_id
        pivot = load_upstream_json(edition_cache_path(pivot_name))
        core, has_grades, section_count = build_core(book_id, pivot)
        core_file = write_blob(book_dir, "core", core, out_root)
        core_file["count"] = len(core["h"])
        referenced.add(core_file["path"])

        editions_out = []
        for entry in entries:
            name = entry["name"]
            cache = edition_cache_path(name)
            if not cache.exists():
                fail(f"{name}: not downloaded (run tools/fetch_upstream.py)")
            language = entry["language"]
            if language not in LANGUAGE_CODES:
                fail(f"{name}: language {language!r} has no ISO code in tools/common.py")
            upstream = pivot if name == pivot_name else load_upstream_json(cache)
            titles_ar = load_arabic_titles(book_id, upstream) if name == pivot_name else None
            pack, empty = build_edition_pack(book_id, name, upstream, titles_ar)
            file = write_blob(book_dir, name, pack, out_root)
            referenced.add(file["path"])
            edition = {
                "id": name,
                "lang": LANGUAGE_CODES[language],
                "langName": language,
                "direction": "rtl" if LANGUAGE_CODES[language] in RTL_LANGUAGE_CODES else "ltr",
                "translator": entry.get("author", ""),
                "source": entry.get("source", ""),
                "comments": entry.get("comments", ""),
                "count": len(pack["n"]),
                "emptyCount": empty,
                **file,
            }
            if name not in published:
                edition["held"] = True
            editions_out.append(edition)
            totals["editions"] += 1
            totals["bytes"] += file["bytes"]
        books_out.append(
            {
                "id": book_id,
                "name": book["name"],
                "count": len(core["h"]),
                "sectionCount": section_count,
                "hasGrades": has_grades,
                **({"names": book_names[book_id]} if book_id in book_names else {}),
                "core": core_file,
                "editions": editions_out,
            }
        )
        totals["bytes"] += core_file["bytes"]

    index = {
        "schema": SCHEMA,
        "upstream": {"repo": UPSTREAM_REPO, "commit": pinned_commit(), "license": "Unlicense"},
        "books": books_out,
    }

    index_path = data_dir / "index.json"
    previous = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else None
    stripped = lambda value: {k: v for k, v in value.items() if k not in ("revision", "generatedAt")}  # noqa: E731
    if previous and stripped(previous) == index:
        index["revision"], index["generatedAt"] = previous["revision"], previous["generatedAt"]
    else:
        index["revision"] = (previous["revision"] + 1) if previous else 1
        index["generatedAt"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_bytes(json.dumps(index, ensure_ascii=False, indent=1).encode("utf-8") + b"\n")

    # remove files that are no longer referenced (older revisions of a file)
    removed = 0
    for path in (data_dir / "books").rglob("*.json.gz"):
        if path.relative_to(out_root).as_posix() not in referenced:
            path.unlink()
            removed += 1

    if not options.all:
        write_sources(catalogue, published)
    print(
        f"revision {index['revision']}: {len(books_out)} books, {totals['editions']} editions, "
        f"{totals['bytes'] / 1e6:.2f} MB gzip, {removed} stale files removed -> {data_dir}"
    )


def write_sources(catalogue, published):
    lines = [
        "# Sources of the published editions",
        "",
        "Generated by `tools/build.py` from `upstream/editions.json` — do not edit by hand.",
        "",
        "Every published edition is a copy of the text of the same-named file in",
        f"[{UPSTREAM_REPO}](https://github.com/{UPSTREAM_REPO}) at the commit pinned in `upstream/COMMIT`.",
        "Texts, hadith numbers, references and grades are reproduced exactly as in that project.",
        "",
        "| Edition | Collection | Language | Author field (as upstream) | Source field (as upstream) |",
        "|---|---|---|---|---|",
    ]
    for book_id in sorted(catalogue):
        for entry in catalogue[book_id]["collection"]:
            if entry["name"] in published:
                author = entry.get("author") or "-"
                source = entry.get("source") or "-"
                lines.append(
                    f"| `{entry['name']}` | {catalogue[book_id]['name']} | {entry['language']} | {author} | {source} |"
                )
    lines += [
        "",
        "## What the upstream project says about its own sources",
        "",
        "- The upstream maintainer states (issue #8) that the Arabic and English texts come from sunnah.com,",
        "  other translations from several websites listed in `upstream/References.md`, and the hadith grades from al-maktaba.org.",
        "- Grades are the judgements of the named scholars (for example Al-Albani, Shuaib Al Arnaut, Zubair Ali Zai);",
        "  they exist only for Abu Dawud, Tirmidhi, Nasai, Ibn Majah and Malik. Bukhari, Muslim and the Forty Hadith collections have none.",
        "- Section titles are in English in the upstream data, also for the Arabic editions. `titles/ar/` holds Arabic renderings of them",
        "  written for this repository (not upstream data; see `titles/README.md`); they are stored in the Arabic edition files as `sections_ar`.",
        "",
        "See `NOTICE.md` for what this repository does and does not claim, and `TAKEDOWN.md` to request removal.",
        "",
    ]
    (ROOT / "SOURCES.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
