#!/usr/bin/env python3
"""Evaluate whether a reviewed DOCX covers comments from a reference review."""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inspect_review_markup import count_revisions, extract_comments, revision_texts  # noqa: E402


DEFAULT_SIMILARITY_THRESHOLD = 0.72


def normalize_anchor_text(text: str) -> str:
    """Normalize anchor text for resilient cross-DOCX matching."""
    lowered = (text or "").casefold()
    collapsed_punctuation = re.sub(r"[^\w\s]+", " ", lowered)
    return re.sub(r"\s+", " ", collapsed_punctuation).strip()


def similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def anchor_match_score(reference_anchor: str, candidate_anchor: str) -> tuple[float, str]:
    reference_norm = normalize_anchor_text(reference_anchor)
    candidate_norm = normalize_anchor_text(candidate_anchor)
    if not reference_norm or not candidate_norm:
        return 0.0, "empty"
    if reference_norm == candidate_norm:
        return 1.0, "exact"
    if reference_norm in candidate_norm or candidate_norm in reference_norm:
        shorter = min(len(reference_norm), len(candidate_norm))
        longer = max(len(reference_norm), len(candidate_norm))
        return shorter / longer if longer else 0.0, "substring"
    return similarity(reference_norm, candidate_norm), "similarity"


def comment_summary(comment: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(comment.get("id", "")),
        "text": str(comment.get("text", "")),
        "anchor_text": str(comment.get("anchor_text", "")),
    }


def best_candidate_match(
    reference_comment: dict[str, Any],
    candidate_comments: list[dict[str, Any]],
    used_candidate_indexes: set[int],
    threshold: float,
) -> tuple[int | None, float, str]:
    best_index: int | None = None
    best_score = 0.0
    best_strategy = "none"
    reference_anchor = str(reference_comment.get("anchor_text", ""))
    for index, candidate_comment in enumerate(candidate_comments):
        if index in used_candidate_indexes:
            continue
        candidate_anchor = str(candidate_comment.get("anchor_text", ""))
        score, strategy = anchor_match_score(reference_anchor, candidate_anchor)
        if score > best_score:
            best_index = index
            best_score = score
            best_strategy = strategy

    if best_index is None or best_score < threshold:
        return None, best_score, best_strategy
    return best_index, best_score, best_strategy


def covered_by_revision(reference_anchor: str, candidate_revision_values: list[str]) -> bool:
    reference_norm = normalize_anchor_text(reference_anchor)
    if not reference_norm:
        return False
    for value in candidate_revision_values:
        value_norm = normalize_anchor_text(value)
        if not value_norm:
            continue
        if reference_norm == value_norm or reference_norm in value_norm or value_norm in reference_norm:
            return True
        if similarity(reference_norm, value_norm) >= 0.9:
            return True
    return False


def evaluate_coverage(
    reference_path: Path,
    candidate_path: Path,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> dict[str, Any]:
    reference_comments = extract_comments(reference_path)
    candidate_comments = extract_comments(candidate_path)
    reference_revision_counts = count_revisions(reference_path)
    candidate_revision_counts = count_revisions(candidate_path)
    candidate_revision_values = revision_texts(candidate_path, "ins") + revision_texts(candidate_path, "del")

    anchored_reference_indexes = [
        index
        for index, comment in enumerate(reference_comments)
        if normalize_anchor_text(str(comment.get("anchor_text", "")))
    ]

    used_candidate_indexes: set[int] = set()
    anchor_matches: list[dict[str, Any]] = []
    missing_reference_comments: list[dict[str, str]] = []

    for reference_index in anchored_reference_indexes:
        reference_comment = reference_comments[reference_index]
        candidate_index, score, strategy = best_candidate_match(
            reference_comment,
            candidate_comments,
            used_candidate_indexes,
            similarity_threshold,
        )
        if candidate_index is None:
            if covered_by_revision(str(reference_comment.get("anchor_text", "")), candidate_revision_values):
                anchor_matches.append(
                    {
                        "reference_comment": comment_summary(reference_comment),
                        "candidate_comment": {"id": "", "text": "covered by tracked change", "anchor_text": ""},
                        "score": 1.0,
                        "strategy": "tracked_change_text",
                    }
                )
                continue
            missing_reference_comments.append(comment_summary(reference_comment))
            continue

        used_candidate_indexes.add(candidate_index)
        candidate_comment = candidate_comments[candidate_index]
        anchor_matches.append(
            {
                "reference_comment": comment_summary(reference_comment),
                "candidate_comment": comment_summary(candidate_comment),
                "score": round(score, 4),
                "strategy": strategy,
            }
        )

    candidate_extra_comments = [
        comment_summary(comment)
        for index, comment in enumerate(candidate_comments)
        if index not in used_candidate_indexes
    ]

    anchored_reference_count = len(anchored_reference_indexes)
    coverage_score = (
        len(anchor_matches) / anchored_reference_count
        if anchored_reference_count
        else 1.0
    )

    return {
        "reference_comment_count": len(reference_comments),
        "candidate_comment_count": len(candidate_comments),
        "anchored_reference_count": anchored_reference_count,
        "anchor_matches": anchor_matches,
        "missing_reference_comments": missing_reference_comments,
        "candidate_extra_comments": candidate_extra_comments,
        "reference_revision_counts": reference_revision_counts,
        "candidate_revision_counts": candidate_revision_counts,
        "coverage_score": round(coverage_score, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path, help="Reference reviewed DOCX")
    parser.add_argument("--candidate", required=True, type=Path, help="Candidate reviewed DOCX")
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help="Minimum normalized anchor similarity for a match",
    )
    parser.add_argument("--out", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    payload = evaluate_coverage(
        args.reference.expanduser().resolve(),
        args.candidate.expanduser().resolve(),
        args.similarity_threshold,
    )
    data = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        args.out.expanduser().resolve().write_text(data + "\n", encoding="utf-8")
    else:
        print(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
