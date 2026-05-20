---
name: docx-formula-variable-definitions
description: Use when checking DOCX equations and OfficeMath for undefined variables, loss terms, kernel symbols, and formula notation.
---

# docx-formula-variable-definitions

Use this skill when the task is only to detect and fix this DOCX issue: undefined variables and loss terms around equations and OfficeMath.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-formula-variable-definitions/scripts/check_formula_variable_definitions.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-formula-variable-definitions/scripts/check_formula_variable_definitions.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
