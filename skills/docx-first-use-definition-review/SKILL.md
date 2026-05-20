---
name: docx-first-use-definition-review
description: Use when checking DOCX manuscripts for first-use definitions and brief explanations of technical abbreviations.
---

# docx-first-use-definition-review

Use this skill when the task is only to detect and fix this DOCX issue: first-use definitions and brief explanations for manuscript-specific abbreviations.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-first-use-definition-review/scripts/check_first_use_definition_review.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-first-use-definition-review/scripts/check_first_use_definition_review.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
