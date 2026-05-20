#!/usr/bin/env python3
"""Inspect comments and tracked-change counts in a DOCX."""

from __future__ import annotations

import argparse
from pathlib import Path
from xml.etree import ElementTree as ET
import zipfile

from docx_review_lib import M_NS, NS, W_NS, load_xml_from_docx, normalize_space, qn, write_json


REVISION_TAGS = [
    "ins",
    "del",
    "moveFrom",
    "moveTo",
    "rPrChange",
    "pPrChange",
    "tblPrChange",
    "tcPrChange",
    "trPrChange",
]


def extract_comments(docx_path: Path) -> list[dict]:
    with zipfile.ZipFile(docx_path) as zf:
        names = set(zf.namelist())
        if "word/comments.xml" not in names:
            return []
        comments_root = ET.fromstring(zf.read("word/comments.xml"))
        doc_root = ET.fromstring(zf.read("word/document.xml"))

    anchor_text_by_id: dict[str, str] = {}
    for paragraph in doc_root.findall(".//w:p", NS):
        ids = [el.get(qn(W_NS, "id")) for el in paragraph.findall(".//w:commentRangeStart", NS)]
        if not ids:
            continue
        text = normalize_space(
            "".join(
                node.text or ""
                for node in paragraph.iter()
                if node.tag in {qn(W_NS, "t"), qn(W_NS, "delText"), qn(M_NS, "t")}
            )
        )
        for comment_id in ids:
            if comment_id is not None:
                anchor_text_by_id.setdefault(comment_id, text[:240])

    comments = []
    for comment in comments_root.findall(".//w:comment", NS):
        comment_id = comment.get(qn(W_NS, "id"), "")
        text = normalize_space("".join(node.text or "" for node in comment.findall(".//w:t", NS)))
        comments.append(
            {
                "id": comment_id,
                "author": comment.get(qn(W_NS, "author"), ""),
                "date": comment.get(qn(W_NS, "date"), ""),
                "initials": comment.get(qn(W_NS, "initials"), ""),
                "text": text,
                "anchor_text": anchor_text_by_id.get(comment_id, ""),
            }
        )
    return comments


def count_revisions(docx_path: Path) -> dict[str, int]:
    root = load_xml_from_docx(docx_path, "word/document.xml")
    return {tag: len(root.findall(f".//w:{tag}", NS)) for tag in REVISION_TAGS}


def sample_revision_text(docx_path: Path, tag: str, limit: int = 12) -> list[str]:
    root = load_xml_from_docx(docx_path, "word/document.xml")
    samples = []
    for node in root.findall(f".//w:{tag}", NS)[:limit]:
        text = normalize_space(
            "".join(
                child.text or ""
                for child in node.iter()
                if child.tag in {qn(W_NS, "t"), qn(W_NS, "delText"), qn(M_NS, "t")}
            )
        )
        if text:
            samples.append(text[:160])
    return samples


def revision_texts(docx_path: Path, tag: str) -> list[str]:
    root = load_xml_from_docx(docx_path, "word/document.xml")
    texts = []
    for node in root.findall(f".//w:{tag}", NS):
        text = normalize_space(
            "".join(
                child.text or ""
                for child in node.iter()
                if child.tag in {qn(W_NS, "t"), qn(W_NS, "delText"), qn(M_NS, "t")}
            )
        )
        if text:
            texts.append(text)
    return texts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    docx_path = args.docx.expanduser().resolve()
    comments = extract_comments(docx_path)
    revisions = count_revisions(docx_path)
    payload = {
        "file": str(docx_path),
        "comment_count": len(comments),
        "comments": comments,
        "revision_counts": revisions,
        "revision_samples": {
            "insertions": sample_revision_text(docx_path, "ins"),
            "deletions": sample_revision_text(docx_path, "del"),
        },
        "revision_texts": {
            "insertions": revision_texts(docx_path, "ins"),
            "deletions": revision_texts(docx_path, "del"),
        },
    }
    write_json(args.out, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
