---
name: docx-logic-bridge-review
description: Use when reviewing DOCX manuscripts for unclear reasoning from observed results to scientific conclusions.
---

# docx-logic-bridge-review

Use this skill when the task is only to detect and fix this DOCX issue: result-to-conclusion jumps that need a clearer reasoning bridge.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-logic-bridge-review/scripts/check_logic_bridge_review.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-logic-bridge-review/scripts/check_logic_bridge_review.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
