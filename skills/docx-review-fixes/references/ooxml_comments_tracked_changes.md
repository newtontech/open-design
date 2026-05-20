# OOXML Comments And Tracked Changes

DOCX files are ZIP packages containing WordprocessingML XML.

## Real Word Comments

A real comment needs:

- `word/comments.xml` with a `w:comment` body.
- A relationship from `word/_rels/document.xml.rels` to `comments.xml`.
- A content type override for `/word/comments.xml`.
- In `word/document.xml`, matching `w:commentRangeStart`, `w:commentRangeEnd`, and
  a `w:commentReference` run.

Comment IDs must not collide with existing comment IDs.

## Tracked Changes

Tracked insertions use `w:ins`; tracked deletions use `w:del`.

- Inserted text uses normal `w:t`.
- Deleted text uses `w:delText`.
- Scan existing `w:id` values before adding new tracked changes.
- Add `w:trackRevisions` in `word/settings.xml`, but remember that this only enables
  the setting; it does not create edits by itself.

## Validation

- For comments, verify the comments part, relationship, content type override, and
  document anchors all exist.
- For tracked changes, count `w:ins` and `w:del` before and after applying fixes.
- Rendering to PDF/PNG is useful for layout, but comments may not render in headless tools.
