---
name: docx-journal-structure-check
description: Use when checking DOCX manuscripts for journal structure issues such as table of contents in the body or figure citations in conclusions.
---

# docx-journal-structure-check

Use this skill when the task is only to detect and fix this DOCX issue: journal-style structure issues such as body TOC and conclusion citations.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-journal-structure-check/scripts/check_journal_structure_check.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-journal-structure-check/scripts/check_journal_structure_check.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
