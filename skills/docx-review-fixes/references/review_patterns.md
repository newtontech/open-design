# Manuscript Review Patterns

Use these patterns for fresh academic DOCX manuscripts. They are designed to
produce professional reviewer comments and conservative tracked changes without
requiring another manuscript version.

## Repeated Issue Types

- Missing definitions for variables in formulas, symbol-definition lists, feature legends,
  metrics, or descriptor abbreviations.
- Unclear units or notation.
- Local manuscript cleanup that a reviewer would normally mark directly: spelling,
  hyphenation, typographic quotes, title/sentence case in captions, duplicated words,
  abbreviation use after first definition, and compound modifiers such as
  "molecule-specific" or "device-level".
- First-use abbreviations or manuscript-specific technical terms that lack both a full
  name and a brief explanation.
- Method motivation gaps: the manuscript says what was done but not why the method,
  threshold, baseline, or filtering step was appropriate.
- Figure captions that mention panels but do not explain what each panel shows.
- Result-to-conclusion gaps: the text jumps from an observed pattern to a broad claim
  without explaining the mechanism or evidentiary link.
- Paragraphs that are too long and should be split.
- Conclusions that continue citing figures/tables.
- Generic author contribution text that needs named responsibilities.
- TOC/front matter that is not appropriate in a Nature-style manuscript body.
- Do not mechanically flag every uppercase token. Prioritize manuscript-specific terms,
  model names, metrics, experimental techniques, descriptor abbreviations, and notation
  that readers need in order to follow the argument. Common vendor, software, and
  hardware names usually do not need definition unless the manuscript uses them as
  scientific variables.
- When unsure, prefer one professional comment at the first substantive use rather than
  repeated comments throughout the manuscript.

## Output Voice

Use professional English comments, for example:

- "Please define this abbreviation at first use."
- "Please give the full name and a brief explanation at first use, then use the abbreviation consistently."
- "Use the abbreviation after it has been defined."
- "Hyphenate this compound modifier for readability."
- "Please explain why this filtering step is appropriate before reporting the result."
- "Please explain what each panel shows before discussing the interpretation."
- "This interpretation needs a clearer bridge from the observed result to the conclusion."
- "This paragraph combines setup, result, and interpretation; consider splitting it."
- "Nature-style conclusions typically avoid new figure or table citations."
