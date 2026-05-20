#!/usr/bin/env python3
"""Check and normalize reference title capitalization style in DOCX files."""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
ET.register_namespace("w", W_NS)

REF_HEADING_RE = re.compile(r"^(references|bibliography)$", re.I)
REF_ENTRY_RE = re.compile(r"^\s*(?:\[\d+\]|\d+[\.)])\s*")
TITLE_AFTER_ET_AL_RE = re.compile(r"\bet al\.\s+(?P<title>[A-Za-z][^.]*)")
TITLE_AFTER_LAST_INITIAL_RE = re.compile(
    r"(?:^|&\s*)[^.]*?,\s*(?:[A-Z]\.\s*){1,5}(?P<title>[A-Za-z][^.]*)"
)
TITLE_AFTER_INITIAL_NAME_RE = re.compile(r"^(?:[A-Z]\.\s*)+[A-Z][A-Za-z-]+\.?\s+(?P<title>[A-Za-z][^.]*)")
TITLE_STOP_RE = re.compile(
    r"\.\s+(?:"
    r"[A-Z][A-Za-z.]*\s+(?:\d|[A-Z][a-z])"
    r"|Preprint at\b"
    r"|in\s*\("
    r"|https?://"
    r")"
)
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’-]*")

SMALL_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "from",
    "in",
    "into",
    "nor",
    "of",
    "on",
    "or",
    "per",
    "the",
    "to",
    "via",
    "with",
}

PROTECTED_TOKENS = {
    "AI",
    "CP2K",
    "DFT",
    "DNA",
    "DOI",
    "FAIR",
    "ICLR",
    "ML",
    "Multiwfn",
    "Optuna",
    "QSPR",
    "RDKit",
    "SMILES",
    "VESTA",
}
EXTRA_PROTECTED_TOKENS: set[str] = set()


def qn(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def paragraph_text(paragraph: ET.Element) -> str:
    return normalize_space(
        "".join(node.text or "" for node in paragraph.iter() if node.tag in {qn("t"), qn("delText")})
    )


def parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in list(parent)}


def clone_run(template: ET.Element | None, text: str, tag: str = "t") -> ET.Element:
    run = ET.Element(qn("r"))
    if template is not None:
        rpr = template.find("w:rPr", NS)
        if rpr is not None:
            run.append(copy.deepcopy(rpr))
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


def in_references(paragraphs: list[ET.Element]) -> list[tuple[int, ET.Element, str]]:
    active = False
    entries: list[tuple[int, ET.Element, str]] = []
    for index, paragraph in enumerate(paragraphs):
        text = paragraph_text(paragraph)
        if not text:
            continue
        if REF_HEADING_RE.match(text):
            active = True
            continue
        if not active:
            continue
        if REF_ENTRY_RE.match(text):
            entries.append((index, paragraph, text))
            continue
        if entries and re.match(r"^[A-Z][A-Za-z ]{0,40}$", text) and not REF_ENTRY_RE.match(text):
            break
    return entries


def reference_body(text: str) -> str:
    return REF_ENTRY_RE.sub("", text, count=1).strip()


def title_text(text: str) -> str | None:
    body = REF_ENTRY_RE.sub("", text, count=1).strip()
    match = TITLE_AFTER_ET_AL_RE.search(body)
    if match is None:
        matches = list(TITLE_AFTER_LAST_INITIAL_RE.finditer(body))
        match = matches[-1] if matches else None
    if match is None:
        match = TITLE_AFTER_INITIAL_NAME_RE.search(body)
    if match is None:
        return None
    title = match.group("title").strip()
    stop = TITLE_STOP_RE.search(title)
    if stop:
        title = title[: stop.start()].strip()
    return title.rstrip(". ").strip() or None


def title_words(title: str) -> list[str]:
    return [word for word in WORD_RE.findall(title) if re.search(r"[A-Za-z]", word)]


def is_protected(word: str) -> bool:
    if word in PROTECTED_TOKENS or word in EXTRA_PROTECTED_TOKENS:
        return True
    if re.search(r"\d", word):
        return True
    if len(word) > 1 and word.isupper():
        return True
    if any(char.isupper() for char in word[1:]) and not word.istitle():
        return True
    return False


def classify_title_style(title: str) -> str | None:
    words = [word for word in title_words(title) if not is_protected(word)]
    if len(words) < 2:
        return None
    major_words = [
        word for idx, word in enumerate(words)
        if idx == 0 or word.casefold() not in SMALL_WORDS
    ]
    if len(major_words) < 2:
        return None
    capitalized = sum(1 for word in major_words[1:] if word[0].isupper())
    total = max(len(major_words) - 1, 1)
    ratio = capitalized / total
    if ratio >= 0.6:
        return "title_case"
    if ratio <= 0.25:
        return "sentence_case"
    return "mixed"


def titlecase_word(word: str, *, first: bool, after_colon: bool) -> str:
    if is_protected(word):
        return word
    if not first and not after_colon and word.casefold() in SMALL_WORDS:
        return word.lower()
    parts = re.split(r"([-–])", word)
    converted = []
    for part in parts:
        if part in {"-", "–"}:
            converted.append(part)
        elif part:
            converted.append(part[0].upper() + part[1:].lower())
    return "".join(converted)


def sentencecase_word(word: str, *, first: bool, after_colon: bool) -> str:
    if is_protected(word):
        return word
    if first or after_colon:
        return word[0].upper() + word[1:].lower()
    return word.lower()


def convert_title(title: str, target_style: str) -> str:
    word_index = 0
    previous_end = 0
    pieces: list[str] = []
    for match in WORD_RE.finditer(title):
        word = match.group(0)
        if not re.search(r"[A-Za-z]", word):
            pieces.append(title[previous_end:match.end()])
            previous_end = match.end()
            continue
        pieces.append(title[previous_end:match.start()])
        prefix = title[: match.start()].rstrip()
        after_colon = prefix.endswith(":")
        first = word_index == 0
        if target_style == "title_case":
            pieces.append(titlecase_word(word, first=first, after_colon=after_colon))
        else:
            pieces.append(sentencecase_word(word, first=first, after_colon=after_colon))
        previous_end = match.end()
        word_index += 1
    pieces.append(title[previous_end:])
    return "".join(pieces)


def apply_tracked_word_replacement(
    paragraph: ET.Element,
    old: str,
    new: str,
    change_id: int,
    author: str,
    date: str,
) -> bool:
    if old == new:
        return False
    parents = parent_map(paragraph)
    for text_el in paragraph.findall(".//w:t", NS):
        text = text_el.text or ""
        if old not in text:
            continue
        run = text_el
        while run is not None and run.tag != qn("r"):
            run = parents.get(run)
        container = parents.get(run) if run is not None else None
        if run is None or container is None:
            continue

        before, after = text.split(old, 1)
        pieces: list[ET.Element] = []
        if before:
            pieces.append(clone_run(run, before))
        deletion = ET.Element(qn("del"), {qn("id"): str(change_id), qn("author"): author, qn("date"): date})
        deletion.append(clone_run(run, old, tag="delText"))
        insertion = ET.Element(qn("ins"), {qn("id"): str(change_id + 1), qn("author"): author, qn("date"): date})
        insertion.append(clone_run(run, new))
        pieces.extend([deletion, insertion])
        if after:
            pieces.append(clone_run(run, after))

        children = list(container)
        idx = children.index(run)
        container.remove(run)
        for offset, piece in enumerate(pieces):
            container.insert(idx + offset, piece)
        return True
    return False


def apply_cross_run_replacement(
    paragraph: ET.Element,
    old: str,
    new: str,
    change_id: int,
    author: str,
    date: str,
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
    insertion.append(clone_run(template, new))
    pieces.extend([deletion, insertion])
    if after:
        pieces.append(clone_run(template, after))
    first_index = list(paragraph).index(direct_runs[0])
    for run in direct_runs:
        paragraph.remove(run)
    for offset, piece in enumerate(pieces):
        paragraph.insert(first_index + offset, piece)
    return True


def ensure_track_revisions(parts: dict[str, bytes]) -> None:
    if "word/settings.xml" not in parts:
        return
    root = ET.fromstring(parts["word/settings.xml"])
    if root.find("w:trackRevisions", NS) is None:
        root.append(ET.Element(qn("trackRevisions")))
        parts["word/settings.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)


@dataclass
class Finding:
    paragraph_index: int
    anchor: str
    title: str
    style: str
    replacement: str
    target_style: str


def analyze(root: ET.Element) -> tuple[str, Counter[str], list[Finding], list[dict[str, str]], list[dict[str, str]]]:
    paragraphs = root.findall(".//w:p", NS)
    entries = in_references(paragraphs)
    styles: Counter[str] = Counter()
    parsed: list[tuple[int, str, str, str]] = []
    skipped: list[dict[str, str]] = []
    questions: list[dict[str, str]] = []

    for index, _paragraph, text in entries:
        title = title_text(text)
        if title is None:
            skipped.append({"paragraph_index": str(index), "anchor": text[:180], "reason": "title not identified"})
            continue
        style = classify_title_style(title)
        if style is None:
            skipped.append({"paragraph_index": str(index), "anchor": text[:180], "reason": "not enough title words to classify"})
            continue
        if style == "mixed":
            questions.append({"paragraph_index": str(index), "title": title, "reason": "mixed capitalization pattern"})
        styles[style] += 1
        parsed.append((index, text, title, style))

    comparable_styles = Counter({key: value for key, value in styles.items() if key in {"title_case", "sentence_case"}})
    target_style = comparable_styles.most_common(1)[0][0] if comparable_styles else "sentence_case"
    if comparable_styles["title_case"] == comparable_styles["sentence_case"]:
        target_style = "sentence_case"

    findings: list[Finding] = []
    for index, text, title, style in parsed:
        if style == target_style:
            continue
        replacement = convert_title(title, target_style)
        if replacement != title:
            findings.append(Finding(index, text[:180], title, style, replacement, target_style))
    return target_style, styles, findings, skipped, questions


def apply_findings(root: ET.Element, findings: list[Finding], author: str) -> int:
    paragraphs = root.findall(".//w:p", NS)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    change_id = max_word_id(root) + 1000
    applied = 0
    for finding in findings:
        paragraph = paragraphs[finding.paragraph_index]
        if apply_tracked_word_replacement(paragraph, finding.title, finding.replacement, change_id, author, now) or apply_cross_run_replacement(paragraph, finding.title, finding.replacement, change_id, author, now):
            applied += 1
            change_id += 2
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--author", default="Reference Title Case Inspector")
    parser.add_argument(
        "--protect",
        action="append",
        default=[],
        help="Additional exact terms to preserve, such as DNA, RDKit, or domain-specific names",
    )
    args = parser.parse_args()
    EXTRA_PROTECTED_TOKENS.update(args.protect)

    docx_path = args.docx.expanduser().resolve()
    with zipfile.ZipFile(docx_path) as zin:
        parts = {info.filename: zin.read(info.filename) for info in zin.infolist()}

    root = ET.fromstring(parts["word/document.xml"])
    target_style, styles, findings, skipped, questions = analyze(root)
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
        "style_counts": dict(styles),
        "finding_count": len(findings),
        "tracked_replacements_applied": applied,
        "findings": [asdict(finding) for finding in findings],
        "skipped": skipped,
        "questions": questions,
    }
    data = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.report:
        args.report.expanduser().resolve().write_text(data + "\n", encoding="utf-8")
    else:
        print(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
