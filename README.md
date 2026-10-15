# hadith-books-data

Data files for the **Hadith Books** feature of the Muflihin Pro app: the Arabic texts of ten hadith collections and their translations (54 editions in 8 languages), with sections, references and (where the source has them) the grades given by named scholars.

مستودع بيانات ميزة «كتب الحديث» في تطبيق Muflihin Pro: النصوص العربية لعشر مجموعات حديثية وترجماتها (54 إصداراً بثماني لغات) مع الأقسام والمراجع ودرجات الحديث المنسوبة لأصحابها حيث وُجدت في المصدر.

## What is here

| Collection | Hadiths | Grades in the source |
|---|---|---|
| Sahih al-Bukhari | 7589 | none |
| Sahih Muslim | 7563 | none |
| Sunan Abu Dawud | 5274 | yes |
| Jami at-Tirmidhi | 3998 | yes |
| Sunan an-Nasai | 5765 | yes |
| Sunan Ibn Majah | 4343 | yes |
| Muwatta Malik | 1858 | yes |
| Forty Hadith of an-Nawawi | 42 | none |
| Forty Hadith Qudsi | 40 | none |
| Forty Hadith of Shah Waliullah Dehlawi | 40 | none |

The data is a faithful, compact repackaging of [fawazahmed0/hadith-api](https://github.com/fawazahmed0/hadith-api) (commit pinned in `upstream/COMMIT`). Nothing is added, corrected or translated here: texts, translations, numbers, references and grades are copied exactly. Gaps in the source stay gaps (some hadiths have an empty text there; the app says so instead of filling them).

## Layout

```
data/v1/index.json                         catalogue read by the app (books, editions, sizes, SHA-256)
data/v1/books/<book>/core.<hash>.json.gz   per-hadith numbers, references and grades (language-neutral)
data/v1/books/<book>/<edition>.<hash>.json.gz   texts and section titles of one edition
upstream/                                  snapshot of the upstream catalogue, licence and references used
tools/                                     fetch_upstream.py, build.py, verify.py (Python standard library only)
```

File names carry a content hash, so a changed file is never confused with an old cached one. The app learns about books and languages only from `index.json`.

## Rebuilding and checking

```
python tools/fetch_upstream.py
python tools/build.py
python tools/verify.py
```

`verify.py` re-reads the pinned upstream files and fails if any text, number, reference, grade, size or hash differs.

## Rights

Read `NOTICE.md` and `SOURCES.md` before reusing anything. To request the removal of any content, see `TAKEDOWN.md`.
