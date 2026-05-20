---
name: docx-unit-symbol-consistency
description: Use when checking or fixing DOCX unit and symbol consistency, especially Angstrom notation, malformed units, and spacing around scientific units.
---

# docx-unit-symbol-consistency

Use this skill when the task is only to detect and fix this DOCX issue: unit and symbol consistency, such as Angstrom notation and malformed unit expressions.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-unit-symbol-consistency/scripts/check_unit_symbol_consistency.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-unit-symbol-consistency/scripts/check_unit_symbol_consistency.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
