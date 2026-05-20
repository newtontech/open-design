---
name: docx-figure-caption-explanation
description: Use when checking DOCX figure and supplementary figure captions for missing panel explanations.
---

# docx-figure-caption-explanation

Use this skill when the task is only to detect and fix this DOCX issue: figure captions that mention panels but do not explain each panel clearly.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-figure-caption-explanation/scripts/check_figure_caption_explanation.py input.docx --report report.json
   ```

2. Inspect findings. For scientific/proper-noun-sensitive changes, use agent judgment and pass `--protect TERM` when relevant.

3. Apply markup:

   ```bash
   python skills/docx-figure-caption-explanation/scripts/check_figure_caption_explanation.py input.docx --apply --out output.docx --report report.json
   ```

4. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Keep this skill narrow; do not perform unrelated manuscript review.
- Use tracked changes for direct text fixes and Word comments for author-facing review items.
- Preserve private manuscript files and reports outside the repository.
