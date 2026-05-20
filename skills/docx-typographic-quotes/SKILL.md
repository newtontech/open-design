---
name: docx-typographic-quotes
description: Use when checking or fixing DOCX apostrophes, smart quotes, duplicated quote marks, and quote consistency.
---

# docx-typographic-quotes

Use this skill when the task is only to detect and fix this DOCX issue: typographic apostrophes, smart quotes, and duplicated quotation marks.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-typographic-quotes/scripts/check_typographic_quotes.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-typographic-quotes/scripts/check_typographic_quotes.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
