# Arabic section titles

The upstream data (`hadith-api`) gives the section (kitab / chapter) titles in **English only**, even for the Arabic editions.
The files in `titles/ar/<book>.json` are **Arabic renderings of those English titles written for this repository**.
They are **not part of the upstream data** and they are not a copy of any printed edition: each title translates the
English title of the same section id into the standard Arabic name of that book of the collection.

- Keys are the upstream section ids; a section whose upstream title is empty has no entry (nothing is invented for it).
- `tools/build.py` adds them to the Arabic edition file as `sections_ar`; the app shows the Arabic title when the interface is Arabic
  and keeps the original English title next to it.
- `tools/verify.py` checks that every key is an upstream section id and that no upstream section with a title is left without one.
- A correction is a plain edit of the JSON file followed by `build.py`, `verify.py` and a push.
