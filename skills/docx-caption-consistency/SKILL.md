---
name: docx-caption-consistency
description: Use when checking or fixing DOCX figure caption panel marker consistency, especially mixed styles such as bold "a," markers versus "(a)" or "(a,)" markers inside captions.
---

# DOCX Caption Consistency

Use this skill when the only task is to police figure-caption panel marker consistency in a `.docx`.

## Scope

Check only caption paragraphs such as `Fig. 3 | ...`, `Figure 3 | ...`,
`Supplementary Figure 4 | ...`, or `Supplementary Fig. 4 | ...`.

Look for inconsistent panel markers inside captions:

- `a,` / `b,` / `c,`
- `(a)` / `(b)`
- `(a,)` / `(b,)`
- `a-b,` / `d-f,`
- `(a-f)`
- bold versus non-bold panel markers

Do not review science, grammar, table content, author metadata, equations, or non-caption body text.

## Workflow

1. Run a report first:

   ```bash
   python skills/docx-caption-consistency/scripts/check_caption_markers.py input.docx --report report.json
   ```

2. Inspect the reported dominant style. By default the script normalizes minority styles to the document's dominant caption marker style.

3. Apply tracked changes:

   ```bash
   python skills/docx-caption-consistency/scripts/check_caption_markers.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate the output structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Prefer the majority style found across caption markers.
- Treat `a,` and `a-b,` as the same comma-marker family. Treat `(a)` and `(a-f)` as the same parenthetical-marker family.
- If no clear majority exists, prefer the comma-marker family.
- Preserve the surrounding caption text.
- Use Word tracked changes for marker text normalization.
- When the dominant style uses bold panel markers, mark inserted panel markers bold where the script can identify the marker run.
- Report every changed caption with before/after marker text.
