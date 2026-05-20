---
name: docx-author-contribution-detail
description: Use when checking DOCX author contribution statements for generic wording that needs named responsibilities.
---

# docx-author-contribution-detail

Use this skill when the task is only to detect and fix this DOCX issue: generic author contribution statements that need named responsibilities.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-author-contribution-detail/scripts/check_author_contribution_detail.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-author-contribution-detail/scripts/check_author_contribution_detail.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
