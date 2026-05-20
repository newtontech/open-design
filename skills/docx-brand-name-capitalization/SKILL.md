---
name: docx-brand-name-capitalization
description: Use when checking or fixing official database, supplier, software, and brand-name capitalization in DOCX files.
---

# docx-brand-name-capitalization

Use this skill when the task is only to detect and fix this DOCX issue: official capitalization for databases, suppliers, software, and brand names.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-brand-name-capitalization/scripts/check_brand_name_capitalization.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-brand-name-capitalization/scripts/check_brand_name_capitalization.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
