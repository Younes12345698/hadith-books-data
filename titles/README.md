# Arabic section titles

The upstream data (`hadith-api`) gives the section (kitab / chapter) titles in **English only**, even for the Arabic editions.

`titles/ar/<book>.json` holds the **original Arabic names of those sections**, taken from the Arabic book names published by sunnah.com
(through the dataset [AhmedBaset/hadith-json](https://github.com/AhmedBaset/hadith-json), which carries Arabic and English names side by side).
Each upstream English title was matched to the identical English title in that dataset (396 of 396 matched one-to-one for the seven large collections),
and the Arabic name next to it was copied as it is, with only whitespace and invisible direction marks cleaned.
Nothing here is a translation made for this repository.

- One title (Tirmidhi section 37) is cut short in that dataset («… عن رسول الله صلى الله»); it was completed to «… صلى الله عليه وسلم», the same ending as its sibling titles.
- The three Forty Hadith collections have one section each, named like the collection; their Arabic name is the collection's usual Arabic name.
- Keys are the upstream section ids; a section whose upstream title is empty has no entry (nothing is invented for it).
- `tools/build.py` adds them to the Arabic edition file as `sections_ar`; the app shows the Arabic title first when the interface is Arabic and keeps the English title next to it.
- `tools/verify.py` checks that every key is an upstream section id and that no upstream section with a title is left without one.
- That dataset has no licence file; it republishes sunnah.com's Arabic names, the same source family as the Arabic hadith texts of hadith-api. Removal requests: see `TAKEDOWN.md`.
