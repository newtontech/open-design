---
name: docx-scientific-notation
description: Use when checking or fixing DOCX scientific notation such as 8.5e-05 in academic manuscripts.
---

# docx-scientific-notation

Use this skill when the task is only to detect and fix this DOCX issue: programming-style scientific notation in manuscript text.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-scientific-notation/scripts/check_scientific_notation.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-scientific-notation/scripts/check_scientific_notation.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
