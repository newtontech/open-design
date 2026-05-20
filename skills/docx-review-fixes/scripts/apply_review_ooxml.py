#!/usr/bin/env python3
"""Apply review findings to a DOCX as Word comments and conservative redlines."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
import zipfile

from docx_review_lib import CT_NS, M_NS, NS, PKG_REL_NS, W_NS, load_findings, normalize_space, qn

COMMENTS_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
COMMENTS_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"


def w_el(name: str, attrs: dict[str, str] | None = None, text: str | None = None) -> ET.Element:
    el = ET.Element(qn(W_NS, name), attrs or {})
    if text is not None:
        el.text = text
    return el


def clone_run_with_text(template_run: ET.Element | None, tag: str, text: str) -> ET.Element:
    run = w_el("r")
    if template_run is not None:
        rpr = template_run.find("w:rPr", NS)
        if rpr is not None:
            run.append(copy.deepcopy(rpr))
    run.append(w_el(tag, text=text))
    return run


def max_word_id(root: ET.Element) -> int:
    values = []
    for el in root.iter():
        value = el.get(qn(W_NS, "id"))
        if value and value.isdigit():
            values.append(int(value))
    return max(values, default=-1)


def ensure_comments_root(existing: bytes | None) -> ET.Element:
    if existing:
        return ET.fromstring(existing)
    return ET.Element(qn(W_NS, "comments"))


def append_comment(comments_root: ET.Element, comment_id: int, text: str, author: str, date: str) -> None:
    comment = w_el(
        "comment",
        {
            qn(W_NS, "id"): str(comment_id),
            qn(W_NS, "author"): author,
            qn(W_NS, "date"): date,
            qn(W_NS, "initials"): "".join(part[0] for part in author.split()[:2]).upper() or "AI",
        },
    )
    paragraph = w_el("p")
    run = w_el("r")
    run.append(w_el("t", text=text))
    paragraph.append(run)
    comment.append(paragraph)
    comments_root.append(comment)


def paragraph_text(paragraph: ET.Element) -> str:
    return normalize_space(
        "".join(
            node.text or ""
            for node in paragraph.iter()
            if node.tag in {qn(W_NS, "t"), qn(W_NS, "delText"), qn(M_NS, "t")}
        )
    )


def find_anchor_paragraph(document_root: ET.Element, anchor_text: str) -> ET.Element | None:
    anchor = normalize_space(anchor_text)
    if not anchor:
        return None
    candidates = [anchor, anchor[:120], anchor[:80], anchor[:48]]
    for paragraph in document_root.findall(".//w:p", NS):
        text = paragraph_text(paragraph)
        if text and any(candidate and candidate in text for candidate in candidates):
            return paragraph
    return None


def add_comment_markers(paragraph: ET.Element, comment_id: int) -> bool:
    children = list(paragraph)
    run_indices = [idx for idx, child in enumerate(children) if child.tag == qn(W_NS, "r")]
    if run_indices:
        first_idx = run_indices[0]
        last_idx = run_indices[-1]
    else:
        content_indices = [
            idx for idx, child in enumerate(children)
            if child.tag in {
                qn(M_NS, "oMath"),
                qn(M_NS, "oMathPara"),
                qn(W_NS, "hyperlink"),
                qn(W_NS, "ins"),
                qn(W_NS, "del"),
            }
        ]
        if not content_indices:
            return False
        first_idx = content_indices[0]
        last_idx = content_indices[-1]
    start = w_el("commentRangeStart", {qn(W_NS, "id"): str(comment_id)})
    end = w_el("commentRangeEnd", {qn(W_NS, "id"): str(comment_id)})
    ref_run = w_el("r")
    rpr = w_el("rPr")
    rpr.append(w_el("rStyle", {qn(W_NS, "val"): "CommentReference"}))
    ref_run.append(rpr)
    ref_run.append(w_el("commentReference", {qn(W_NS, "id"): str(comment_id)}))

    paragraph.insert(first_idx, start)
    paragraph.append(end)
    paragraph.append(ref_run)
    return True


def parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in list(parent)}


def apply_tracked_replacement(paragraph: ET.Element, old: str, new: str, change_id: int, author: str, date: str) -> bool:
    if not old or old == new:
        return False
    parents = parent_map(paragraph)
    for text_el in paragraph.findall(".//w:t", NS):
        text = text_el.text or ""
        if old not in text:
            continue
        run = parents.get(text_el)
        while run is not None and run.tag != qn(W_NS, "r"):
            run = parents.get(run)
        if run is None:
            continue
        container = parents.get(run)
        if container is None:
            continue

        before, after = text.split(old, 1)
        replacements: list[ET.Element] = []
        if before:
            replacements.append(clone_run_with_text(run, "t", before))

        deletion = w_el(
            "del",
            {qn(W_NS, "id"): str(change_id), qn(W_NS, "author"): author, qn(W_NS, "date"): date},
        )
        deletion.append(clone_run_with_text(run, "delText", old))
        insertion = w_el(
            "ins",
            {qn(W_NS, "id"): str(change_id + 1), qn(W_NS, "author"): author, qn(W_NS, "date"): date},
        )
        insertion.append(clone_run_with_text(run, "t", new))
        replacements.extend([deletion, insertion])

        if after:
            replacements.append(clone_run_with_text(run, "t", after))

        children = list(container)
        try:
            idx = children.index(run)
        except ValueError:
            continue
        container.remove(run)
        for offset, replacement in enumerate(replacements):
            container.insert(idx + offset, replacement)
        return True
    return apply_cross_run_tracked_replacement(paragraph, old, new, change_id, author, date)


def apply_cross_run_tracked_replacement(
    paragraph: ET.Element,
    old: str,
    new: str,
    change_id: int,
    author: str,
    date: str,
) -> bool:
    full_text = normalize_space(
        "".join(
            node.text or ""
            for node in paragraph.iter()
            if node.tag in {qn(W_NS, "t"), qn(W_NS, "delText"), qn(M_NS, "t")}
        )
    )
    if old not in full_text:
        return False

    direct_runs = [
        child for child in list(paragraph)
        if child.tag == qn(W_NS, "r") and child.find(".//w:commentReference", NS) is None
    ]
    if not direct_runs:
        return False

    template_run = direct_runs[0]
    before, after = full_text.split(old, 1)
    replacement_nodes: list[ET.Element] = []
    if before:
        replacement_nodes.append(clone_run_with_text(template_run, "t", before))

    deletion = w_el(
        "del",
        {qn(W_NS, "id"): str(change_id), qn(W_NS, "author"): author, qn(W_NS, "date"): date},
    )
    deletion.append(clone_run_with_text(template_run, "delText", old))
    insertion = w_el(
        "ins",
        {qn(W_NS, "id"): str(change_id + 1), qn(W_NS, "author"): author, qn(W_NS, "date"): date},
    )
    insertion.append(clone_run_with_text(template_run, "t", new))
    replacement_nodes.extend([deletion, insertion])

    if after:
        replacement_nodes.append(clone_run_with_text(template_run, "t", after))

    first_run_index = list(paragraph).index(direct_runs[0])
    for run in direct_runs:
        paragraph.remove(run)
    for offset, node in enumerate(replacement_nodes):
        paragraph.insert(first_run_index + offset, node)
    return True


def ensure_comments_relationship(rels_root: ET.Element) -> None:
    for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.get("Type") == COMMENTS_REL_TYPE and rel.get("Target") == "comments.xml":
            return
    ids = []
    for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        rid = rel.get("Id", "")
        if rid.startswith("rId") and rid[3:].isdigit():
            ids.append(int(rid[3:]))
    rel = ET.Element(
        qn(PKG_REL_NS, "Relationship"),
        {"Id": f"rId{max(ids, default=0) + 1}", "Type": COMMENTS_REL_TYPE, "Target": "comments.xml"},
    )
    rels_root.append(rel)


def ensure_comments_content_type(content_root: ET.Element) -> None:
    for override in content_root.findall(f"{{{CT_NS}}}Override"):
        if override.get("PartName") == "/word/comments.xml":
            return
    content_root.append(
        ET.Element(
            qn(CT_NS, "Override"),
            {"PartName": "/word/comments.xml", "ContentType": COMMENTS_CONTENT_TYPE},
        )
    )


def ensure_track_revisions(settings_root: ET.Element | None) -> ET.Element | None:
    if settings_root is None:
        return None
    if settings_root.find("w:trackRevisions", NS) is None:
        settings_root.append(w_el("trackRevisions"))
    return settings_root


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("findings_json", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--author", default="AI Reviewer")
    args = parser.parse_args()

    docx_path = args.docx.expanduser().resolve()
    out_path = args.out.expanduser().resolve()
    findings = load_findings(args.findings_json.expanduser().resolve())
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    with zipfile.ZipFile(docx_path) as zin:
        original_parts = {info.filename: zin.read(info.filename) for info in zin.infolist()}

    document_root = ET.fromstring(original_parts["word/document.xml"])
    comments_root = ensure_comments_root(original_parts.get("word/comments.xml"))
    rels_root = ET.fromstring(original_parts["word/_rels/document.xml.rels"])
    content_root = ET.fromstring(original_parts["[Content_Types].xml"])
    settings_root = ET.fromstring(original_parts["word/settings.xml"]) if "word/settings.xml" in original_parts else None

    next_comment_id = max(max_word_id(comments_root), max_word_id(document_root)) + 1
    next_change_id = max_word_id(document_root) + 1000
    comments_added = 0
    replacements_added = 0

    for finding in findings:
        paragraph = find_anchor_paragraph(document_root, finding.anchor_text)
        if paragraph is None:
            continue
        comment_id = next_comment_id
        next_comment_id += 1
        append_comment(comments_root, comment_id, finding.comment, args.author, now)

        if finding.replacement_old and finding.replacement_new:
            if apply_tracked_replacement(
                paragraph,
                finding.replacement_old,
                finding.replacement_new,
                next_change_id,
                args.author,
                now,
            ):
                replacements_added += 1
                next_change_id += 2

        if add_comment_markers(paragraph, comment_id):
            comments_added += 1

    if comments_added:
        ensure_comments_relationship(rels_root)
        ensure_comments_content_type(content_root)
    if replacements_added:
        settings_root = ensure_track_revisions(settings_root)

    original_parts["word/document.xml"] = xml_bytes(document_root)
    original_parts["word/comments.xml"] = xml_bytes(comments_root)
    original_parts["word/_rels/document.xml.rels"] = xml_bytes(rels_root)
    original_parts["[Content_Types].xml"] = xml_bytes(content_root)
    if settings_root is not None:
        original_parts["word/settings.xml"] = xml_bytes(settings_root)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in original_parts.items():
            zout.writestr(name, data)

    print(f"output={out_path}")
    print(f"comments_added={comments_added}")
    print(f"tracked_replacements_added={replacements_added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
