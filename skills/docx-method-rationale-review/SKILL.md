---
name: docx-method-rationale-review
description: Use when reviewing DOCX manuscripts for missing method rationale, threshold explanation, filtering justification, or baseline/residual motivation.
---

# docx-method-rationale-review

Use this skill when the task is only to detect and fix this DOCX issue: method choices, filtering thresholds, baselines, and inductive-bias rationale.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-method-rationale-review/scripts/check_method_rationale_review.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-method-rationale-review/scripts/check_method_rationale_review.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
