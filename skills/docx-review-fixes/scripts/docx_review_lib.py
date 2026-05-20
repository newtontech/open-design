#!/usr/bin/env python3
"""Small standard-library helpers for DOCX review scripts."""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

NS = {
    "w": W_NS,
    "r": R_NS,
    "pr": PKG_REL_NS,
    "ct": CT_NS,
    "m": M_NS,
}

ET.register_namespace("w", W_NS)
ET.register_namespace("r", R_NS)
ET.register_namespace("m", M_NS)


def qn(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"


@dataclass
class Paragraph:
    index: int
    text: str
    element: ET.Element


@dataclass
class Finding:
    category: str
    severity: str
    anchor_text: str
    comment: str
    replacement_old: str | None = None
    replacement_new: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def load_xml_from_docx(docx_path: Path, part: str) -> ET.Element:
    with zipfile.ZipFile(docx_path) as zf:
        return ET.fromstring(zf.read(part))


def iter_document_paragraphs(docx_path: Path) -> list[Paragraph]:
    root = load_xml_from_docx(docx_path, "word/document.xml")
    paragraphs: list[Paragraph] = []
    for idx, p_el in enumerate(root.findall(".//w:p", NS)):
        text = "".join(
            node.text or ""
            for node in p_el.iter()
            if node.tag in {qn(W_NS, "t"), qn(W_NS, "delText"), qn(M_NS, "t")}
        )
        paragraphs.append(Paragraph(idx, normalize_space(text), p_el))
    return paragraphs


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def short_anchor(text: str, limit: int = 160) -> str:
    text = normalize_space(text)
    return text[:limit]


def write_json(path: Path | None, payload: dict) -> None:
    data = json.dumps(payload, indent=2, ensure_ascii=False)
    if path is None:
        print(data)
    else:
        path.write_text(data + "\n", encoding="utf-8")


def load_findings(path: Path) -> list[Finding]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_findings = payload.get("findings", payload if isinstance(payload, list) else [])
    findings: list[Finding] = []
    for item in raw_findings:
        findings.append(
            Finding(
                category=item["category"],
                severity=item.get("severity", "P2"),
                anchor_text=item["anchor_text"],
                comment=item["comment"],
                replacement_old=item.get("replacement_old"),
                replacement_new=item.get("replacement_new"),
            )
        )
    return findings


def unique_findings(findings: Iterable[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, str, str | None, str | None]] = set()
    result: list[Finding] = []
    for finding in findings:
        key = (
            finding.category,
            finding.anchor_text,
            finding.comment,
            finding.replacement_old,
            finding.replacement_new,
        )
        if key not in seen:
            seen.add(key)
            result.append(finding)
    return result
