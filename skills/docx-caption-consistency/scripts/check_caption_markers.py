#!/usr/bin/env python3
"""Check and normalize DOCX figure-caption panel marker style."""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import zipfile
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

NS = {"w": W_NS}
ET.register_namespace("w", W_NS)


CAPTION_RE = re.compile(r"^(?:Fig\.|Figure|Supplementary Fig\.|Supplementary Figure)\s+\d+\s*\|", re.I)
MARKER_RE = re.compile(
    r"(?P<prefix>(?:^|[.;]\s+|\|\s+))"
    r"(?P<marker>"
    r"\([a-h](?:\s*[-–]\s*[a-h])?,?\)"
    r"|[a-h](?:\s*[-–]\s*[a-h])?,"
    r")"
)


def qn(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def paragraph_text(paragraph: ET.Element) -> str:
    return normalize_space(
        "".join(node.text or "" for node in paragraph.iter() if node.tag in {qn("t"), qn("delText")})
    )


def has_bold(run: ET.Element | None) -> bool:
    if run is None:
        return False
    rpr = run.find("w:rPr", NS)
    if rpr is None:
        return False
    bold = rpr.find("w:b", NS)
    return bold is not None and bold.get(qn("val"), "1") != "0"


def marker_style(marker: str, bold: bool) -> str:
    if marker.startswith("("):
        return "bold_paren" if bold else "paren"
    return "bold_comma" if bold else "comma"


def canonical_marker(marker: str, target_style: str) -> str:
    inner = marker.strip()
    inner = inner.strip("()")
    inner = inner.rstrip(",")
    inner = re.sub(r"\s*[-–]\s*", "-", inner)
    wants_paren = target_style in {"paren", "bold_paren"}
    if wants_paren:
        return f"({inner})"
    return f"{inner},"


def target_uses_bold(target_style: str) -> bool:
    return target_style.startswith("bold_")


def run_text(run: ET.Element) -> str:
    return "".join(node.text or "" for node in run.iter() if node.tag == qn("t"))


def find_marker_bold(paragraph: ET.Element, marker: str) -> bool:
    for run in paragraph.findall(".//w:r", NS):
        if marker in run_text(run):
            return has_bold(run)
    return False


def clone_run(template: ET.Element | None, text: str, *, bold: bool | None = None, tag: str = "t") -> ET.Element:
    run = ET.Element(qn("r"))
    if template is not None:
        rpr = template.find("w:rPr", NS)
        if rpr is not None:
            run.append(copy.deepcopy(rpr))
    if bold is not None:
        rpr = run.find("w:rPr", NS)
        if rpr is None:
            rpr = ET.Element(qn("rPr"))
            run.insert(0, rpr)
        existing = rpr.find("w:b", NS)
        if bold and existing is None:
            rpr.append(ET.Element(qn("b")))
        if not bold and existing is not None:
            rpr.remove(existing)
    text_el = ET.Element(qn(tag))
    text_el.text = text
    run.append(text_el)
    return run


def max_word_id(root: ET.Element) -> int:
    ids = []
    for el in root.iter():
        value = el.get(qn("id"))
        if value and value.isdigit():
            ids.append(int(value))
    return max(ids, default=0)


def apply_tracked_replacement(
    paragraph: ET.Element,
    old: str,
    new: str,
    change_id: int,
    author: str,
    date: str,
    *,
    inserted_bold: bool | None,
) -> bool:
    if old == new:
        return False
    for text_el in paragraph.findall(".//w:t", NS):
        text = text_el.text or ""
        if old not in text:
            continue
        run = text_el
        parent = parent_map(paragraph)
        while run is not None and run.tag != qn("r"):
            run = parent.get(run)
        container = parent.get(run) if run is not None else None
        if run is None or container is None:
            continue

        before, after = text.split(old, 1)
        pieces: list[ET.Element] = []
        if before:
            pieces.append(clone_run(run, before))
        deletion = ET.Element(qn("del"), {qn("id"): str(change_id), qn("author"): author, qn("date"): date})
        deletion.append(clone_run(run, old, tag="delText"))
        insertion = ET.Element(qn("ins"), {qn("id"): str(change_id + 1), qn("author"): author, qn("date"): date})
        insertion.append(clone_run(run, new, bold=inserted_bold))
        pieces.extend([deletion, insertion])
        if after:
            pieces.append(clone_run(run, after))

        children = list(container)
        idx = children.index(run)
        container.remove(run)
        for offset, piece in enumerate(pieces):
            container.insert(idx + offset, piece)
        return True
    return apply_cross_run_replacement(paragraph, old, new, change_id, author, date, inserted_bold=inserted_bold)


def apply_cross_run_replacement(
    paragraph: ET.Element,
    old: str,
    new: str,
    change_id: int,
    author: str,
    date: str,
    *,
    inserted_bold: bool | None,
) -> bool:
    full_text = paragraph_text(paragraph)
    if old not in full_text:
        return False
    direct_runs = [child for child in list(paragraph) if child.tag == qn("r")]
    if not direct_runs:
        return False
    template = direct_runs[0]
    before, after = full_text.split(old, 1)
    pieces: list[ET.Element] = []
    if before:
        pieces.append(clone_run(template, before))
    deletion = ET.Element(qn("del"), {qn("id"): str(change_id), qn("author"): author, qn("date"): date})
    deletion.append(clone_run(template, old, tag="delText"))
    insertion = ET.Element(qn("ins"), {qn("id"): str(change_id + 1), qn("author"): author, qn("date"): date})
    insertion.append(clone_run(template, new, bold=inserted_bold))
    pieces.extend([deletion, insertion])
    if after:
        pieces.append(clone_run(template, after))
    first_index = list(paragraph).index(direct_runs[0])
    for run in direct_runs:
        paragraph.remove(run)
    for offset, piece in enumerate(pieces):
        paragraph.insert(first_index + offset, piece)
    return True


def set_marker_bold(paragraph: ET.Element, marker: str, bold: bool, change_id: int, author: str, date: str) -> bool:
    for run in paragraph.findall(".//w:r", NS):
        if marker not in run_text(run):
            continue
        rpr = run.find("w:rPr", NS)
        if rpr is None:
            rpr = ET.Element(qn("rPr"))
            run.insert(0, rpr)
        previous_rpr = copy.deepcopy(rpr)
        for existing_change in previous_rpr.findall("w:rPrChange", NS):
            previous_rpr.remove(existing_change)
        existing = rpr.find("w:b", NS)
        changed = False
        if bold and existing is None:
            rpr.append(ET.Element(qn("b")))
            changed = True
        if not bold and existing is not None:
            rpr.remove(existing)
            changed = True
        if changed:
            change = ET.Element(qn("rPrChange"), {qn("id"): str(change_id), qn("author"): author, qn("date"): date})
            change.append(previous_rpr)
            rpr.append(change)
            return True
    return False


def parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in list(parent)}


@dataclass
class MarkerFinding:
    paragraph_index: int
    caption_anchor: str
    marker: str
    style: str
    replacement: str
    target_style: str


def analyze(root: ET.Element) -> tuple[str, list[MarkerFinding], Counter[str]]:
    captions: list[tuple[int, ET.Element, str]] = []
    style_counts: Counter[str] = Counter()
    markers_by_caption: list[tuple[int, ET.Element, str, list[tuple[str, str]]]] = []

    for index, paragraph in enumerate(root.findall(".//w:p", NS)):
        text = paragraph_text(paragraph)
        if not CAPTION_RE.match(text):
            continue
        markers: list[tuple[str, str]] = []
        for match in MARKER_RE.finditer(text):
            marker = match.group("marker")
            bold = find_marker_bold(paragraph, marker)
            style = marker_style(marker, bold)
            markers.append((marker, style))
            style_counts[style] += 1
        if markers:
            captions.append((index, paragraph, text))
            markers_by_caption.append((index, paragraph, text, markers))

    if style_counts:
        target_style = style_counts.most_common(1)[0][0]
    else:
        target_style = "letter_comma"
    if len(style_counts) > 1 and style_counts["comma"] == style_counts.most_common(1)[0][1]:
        target_style = "comma"

    findings: list[MarkerFinding] = []
    for index, _paragraph, text, markers in markers_by_caption:
        for marker, style in markers:
            replacement = canonical_marker(marker, target_style)
            if style != target_style or marker != replacement:
                findings.append(
                    MarkerFinding(
                        index,
                        text[:180],
                        marker,
                        style,
                        replacement,
                        target_style,
                    )
                )
    return target_style, findings, style_counts


def ensure_track_revisions(parts: dict[str, bytes]) -> None:
    if "word/settings.xml" not in parts:
        return
    root = ET.fromstring(parts["word/settings.xml"])
    if root.find("w:trackRevisions", NS) is None:
        root.append(ET.Element(qn("trackRevisions")))
        parts["word/settings.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)


def apply_findings(root: ET.Element, findings: list[MarkerFinding], author: str) -> int:
    paragraphs = root.findall(".//w:p", NS)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    change_id = max_word_id(root) + 1000
    applied = 0
    for finding in findings:
        paragraph = paragraphs[finding.paragraph_index]
        if finding.marker == finding.replacement:
            if set_marker_bold(paragraph, finding.marker, target_uses_bold(finding.target_style), change_id, author, now):
                applied += 1
                change_id += 1
            continue
        if apply_tracked_replacement(
            paragraph,
            finding.marker,
            finding.replacement,
            change_id,
            author,
            now,
            inserted_bold=target_uses_bold(finding.target_style),
        ):
            applied += 1
            change_id += 2
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true", help="Write tracked changes")
    parser.add_argument("--out", type=Path, help="Output DOCX path when --apply is set")
    parser.add_argument("--author", default="Caption Consistency Inspector")
    args = parser.parse_args()

    docx_path = args.docx.expanduser().resolve()
    with zipfile.ZipFile(docx_path) as zin:
        parts = {info.filename: zin.read(info.filename) for info in zin.infolist()}

    root = ET.fromstring(parts["word/document.xml"])
    target_style, findings, style_counts = analyze(root)
    applied = 0

    if args.apply:
        if args.out is None:
            raise SystemExit("--out is required with --apply")
        applied = apply_findings(root, findings, args.author)
        parts["word/document.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        ensure_track_revisions(parts)
        out_path = args.out.expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for name, data in parts.items():
                zout.writestr(name, data)
        shutil.move(tmp_path, out_path)

    payload = {
        "file": str(docx_path),
        "target_style": target_style,
        "style_counts": dict(style_counts),
        "finding_count": len(findings),
        "tracked_replacements_applied": applied,
        "findings": [asdict(finding) for finding in findings],
    }
    data = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.report:
        args.report.expanduser().resolve().write_text(data + "\n", encoding="utf-8")
    else:
        print(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
