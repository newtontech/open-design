---
name: docx-review-fixes
description: >
  Review fresh academic manuscript DOCX files with a context-aware reviewer that
  produces professional English Word comments plus tracked changes. Use for
  Nature-style manuscript checks, first-use abbreviation definitions, equation and
  variable definition gaps, figure-caption explanation gaps, scientific reasoning
  gaps, notation/unit cleanup, paragraph-structure issues, and generic
  author-contribution statements.
triggers:
  - "docx review fixes"
  - "review manuscript docx"
  - "tracked changes"
  - "Nature manuscript review"
od:
  mode: utility
  category: documents
  upstream: "https://github.com/nexu-io/open-design/tree/main/skills/docx"
---

# DOCX Review Fixes

Use this skill when a user wants an academic Word manuscript reviewed in-place with
Word comments and tracked changes from a fresh DOCX manuscript.

## Workflow

1. **Back up first.** Run `scripts/backup_docx_set.py <folder>` before editing any DOCX.
2. **Read for context.** Skim the title, abstract, section headings, figure captions,
   formula blocks, and author contribution text before deciding which issues matter.
3. **Review the original.** Run `scripts/review_docx.py <original.docx> --out findings.json`.
   The script provides a first pass; add or prune findings when a deep contextual read
   reveals important manuscript-specific issues.
4. **Apply review markup.** Run
   `scripts/apply_review_ooxml.py <original.docx> findings.json --out <reviewed.docx>`.
5. **Validate structurally.** Re-run `inspect_review_markup.py` on the output and confirm
   comments and tracked-change counts are nonzero when findings require them.
6. **When a reference-reviewed DOCX is available locally**, run
   `scripts/evaluate_review_coverage.py --reference <reference-reviewed.docx> --candidate <candidate-reviewed.docx>`
   and iterate on missed anchors or missing revision classes. Keep reference files and
   evaluation reports out of public commits unless the user explicitly says otherwise.

## Review Policy

- Comments are English, professional, and reviewer-like.
- Default manuscript target is Nature-style unless the user provides another journal.
- Prefer contextual recall over excessive conservatism. A small number of false positives
  is acceptable when the issue would plausibly block reviewer comprehension.
- Define manuscript-specific abbreviations and technical terms at first substantive use:
  give the full name and a brief explanation, then use the abbreviation consistently.
- Use comments for content gaps that require author knowledge: missing equation symbols,
  unexplained descriptor legends, figure-panel interpretation, method motivation,
  result-to-conclusion reasoning, author-contribution detail, or claims needing domain
  verification.
- Use tracked changes for grammar, sentence splitting, malformed units, scientific
  notation formatting, symbol/notation normalization, and context-supported scientific
  clarification. Also mark small reviewer-style cleanup directly, including spelling,
  hyphenation, typographic quotes, caption case, duplicated words, and abbreviation use
  after first definition. Do not invent facts that are absent from the manuscript.
- Never commit or publish private manuscript DOCX files as fixtures. Keep extracted
  JSON reports as local paths outside this public repository.

## References

- `references/nature_manuscript_rules.md` - journal-style defaults and review checklist.
- `references/review_patterns.md` - common manuscript review categories and comment voice.
- `references/ooxml_comments_tracked_changes.md` - implementation notes for real Word markup.

## Useful Commands

```bash
python skills/docx-review-fixes/scripts/backup_docx_set.py /path/to/manuscripts
python skills/docx-review-fixes/scripts/review_docx.py /path/to/original.docx --out findings.json
python skills/docx-review-fixes/scripts/apply_review_ooxml.py /path/to/original.docx findings.json --out reviewed.docx
python skills/docx-review-fixes/scripts/inspect_review_markup.py reviewed.docx --out markup.json
```
