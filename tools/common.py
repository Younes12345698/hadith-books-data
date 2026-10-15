"""Shared helpers for the hadith-books-data tools (Python standard library only)."""

import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_REPO = "fawazahmed0/hadith-api"
CACHE = ROOT / ".cache" / "upstream"
DATA = ROOT / "data" / "v1"
SCHEMA = 1

# Language names used by the upstream catalogue -> ISO 639-1 codes.
# A language that is not listed here makes the build fail on purpose: adding a language is a decision.
LANGUAGE_CODES = {
    "Arabic": "ar",
    "Bengali": "bn",
    "English": "en",
    "French": "fr",
    "Indonesian": "id",
    "Russian": "ru",
    "Tamil": "ta",
    "Turkish": "tr",
    "Urdu": "ur",
}

# Writing direction is a property of the language, so it is derived from the language code rather than copied:
# the upstream catalogue marks some Bengali editions "rtl" by mistake (Bengali is written left to right).
RTL_LANGUAGE_CODES = {"ar", "ur", "fa", "he"}

# Grade strings are free text in the source (1600+ variants) and are always shown exactly as written.
# This table only drives the app's filter chips, and ONLY exact matches are classified;
# everything else is "o" (other) so that a grade is never presented as something it is not.
#   s = sahih, hs = hasan sahih (the Tirmidhi phrase), h = hasan, d = daif
GRADE_CLASSES = {
    "Sahih": "s",
    "Sahih Lighairihi": "s",
    "Isnaad Sahih": "s",
    "Sahih Isnaad": "s",
    "Sahih - Agreed Upon": "s",
    "Sahih Muslim": "s",
    "Sahih Bukhari": "s",
    "Sahih - Bukhari And Muslim": "s",
    "Sahih Hadith": "s",
    "Sahih Mutawatir": "s",
    "Hasan Sahih": "hs",
    "Hasan": "h",
    "Hasan Lighairihi": "h",
    "Isnaad Hasan": "h",
    "Hasan Isnaad": "h",
    "Daif": "d",
    "Very Daif": "d",
    "Daif Isnaad": "d",
    "Sanad Daif": "d",
    "Very Daif Isnaad": "d",
}


def configure_output():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def gzip_bytes(data: bytes) -> bytes:
    # mtime=0 makes the archive reproducible: same input -> same bytes -> same SHA-256
    return gzip.compress(data, compresslevel=9, mtime=0)


def dump_json(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def load_upstream_json(path: Path):
    """Read an upstream JSON file with every number kept as its original text.

    Hadith numbers such as 402.2 must never go through float, so ints and floats are returned as str.
    """
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle, parse_float=lambda s: s, parse_int=lambda s: s)


def pinned_commit() -> str:
    return (ROOT / "upstream" / "COMMIT").read_text(encoding="utf-8").strip()


def load_publish_list() -> list:
    config = json.loads((ROOT / "tools" / "publish.json").read_text(encoding="utf-8"))
    return list(config["published"])


def edition_cache_path(name: str) -> Path:
    return CACHE / "editions" / f"{name}.min.json"
