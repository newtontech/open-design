---
name: docx-long-paragraph-splitter
description: Use when checking DOCX manuscripts for overlong paragraphs that should be split for reviewer readability.
---

# docx-long-paragraph-splitter

Use this skill when the task is only to detect and fix this DOCX issue: long paragraphs that combine setup, result, interpretation, or method explanation.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-long-paragraph-splitter/scripts/check_long_paragraph_splitter.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-long-paragraph-splitter/scripts/check_long_paragraph_splitter.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
