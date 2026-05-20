---
name: docx-abbreviation-after-definition
description: Use when checking or fixing DOCX abbreviation consistency after first definition, such as using ML after machine learning has been defined.
---

# docx-abbreviation-after-definition

Use this skill when the task is only to detect and fix this DOCX issue: repeated full terms after their abbreviation has already been defined.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-abbreviation-after-definition/scripts/check_abbreviation_after_definition.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-abbreviation-after-definition/scripts/check_abbreviation_after_definition.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
