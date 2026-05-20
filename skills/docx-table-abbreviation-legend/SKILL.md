---
name: docx-table-abbreviation-legend
description: Use when checking DOCX tables, descriptor lists, and feature lists for unexplained abbreviations that need a legend.
---

# docx-table-abbreviation-legend

Use this skill when the task is only to detect and fix this DOCX issue: table or descriptor-list abbreviations that need a legend.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-table-abbreviation-legend/scripts/check_table_abbreviation_legend.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-table-abbreviation-legend/scripts/check_table_abbreviation_legend.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
