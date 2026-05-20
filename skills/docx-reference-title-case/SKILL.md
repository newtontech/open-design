---
name: docx-reference-title-case
description: Use when checking or fixing DOCX reference-list title capitalization consistency, especially mixed Title Case versus sentence case bibliography titles.
---

# DOCX Reference Title Case

Use this skill when the task is only to normalize reference-title capitalization style in a `.docx` bibliography.

## Scope

Check reference-list paragraphs after a `References` heading. A reference entry is a paragraph beginning with a numeric label such as `1.` or `[1]`.

Normalize the detected reference title as a whole:

- If most titles use Title Case, convert sentence-case outliers to Title Case.
- If most titles use sentence case, convert Title Case outliers to sentence case.
- Preserve journal-name case, author names, chemical symbols, acronyms, software names, DOI/URL text, and known brand/model names.
- Let the agent/LLM decide domain-specific protected terms from context before applying. Examples include `DNA`, `RDKit`, `CP2K`, `VESTA`, `Optuna`, chemical formulas, and model names.
- Skip entries where the title start cannot be identified confidently.

## Workflow

1. Generate a report:

   ```bash
   python skills/docx-reference-title-case/scripts/check_reference_title_case.py input.docx --report report.json
   ```

2. Inspect `target_style`, `style_counts`, `findings`, and `questions`.

3. Before applying, use LLM judgment on candidate title changes. Identify proper
   nouns, acronyms, software names, dataset names, chemical names/formulas, and
   model names that must keep their official capitalization. Re-run with
   `--protect` for any term the script should preserve:

   ```bash
   python skills/docx-reference-title-case/scripts/check_reference_title_case.py input.docx --report report.json --protect DNA --protect RDKit
   ```

4. Apply tracked changes:

   ```bash
   python skills/docx-reference-title-case/scripts/check_reference_title_case.py input.docx --apply --out output.docx --report report.json
   ```

5. Validate structurally:

   ```bash
   unzip -t output.docx
   ```

## Rules

- Majority wins. Do not assume uppercase or lowercase is correct before reading the document.
- Use tracked changes for every modified reference title.
- Preserve all punctuation, numbering, authors, journal names, years, URLs, and citation metadata.
- When the script reports `questions`, ask the user before applying if those cases matter for the deliverable.
- Report skipped entries so the user can manually inspect ambiguous references.
