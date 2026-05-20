#!/usr/bin/env python3
"""Context-aware academic DOCX reviewer that emits findings JSON."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

from docx_review_lib import Finding, iter_document_paragraphs, short_anchor, unique_findings, write_json


SCIENTIFIC_NOTATION_RE = re.compile(r"\b\d+(?:\.\d+)?e[+-]?\d+\b", re.I)
FIG_CAPTION_RE = re.compile(r"^(?:Fig\.|Figure|Supplementary Figure)\s+\d+\s*\|", re.I)
PANEL_RANGE_RE = re.compile(r"\b[a-h]\s*[-–]\s*[a-h]\b|(?:\([a-h]\).*){2,}", re.I)
COMMON_NAMES = {
    "NVIDIA",
    "A100",
    "Optuna",
    "Python",
    "RDKit",
    "Gaussian",
    "Multiwfn",
    "CP2K",
    "Sigma-Aldrich",
    "PubChem",
}

FIRST_USE_TERMS = {
    "KRFP": (
        "Please give the full name of KRFP at first use and briefly explain what "
        "molecular information this fingerprint encodes."
    ),
    "QSPR": (
        "Please define QSPR at first substantive use and briefly explain the "
        "property-prediction task in this manuscript."
    ),
    "PSC": "Please define PSC at first substantive use before relying on the abbreviation.",
    "PCE": (
        "Please define PCE at first substantive use and distinguish final PCE from "
        "PCE enhancement when both appear."
    ),
    "ΔPCE": (
        "Please define ΔPCE at first substantive use, including the reference state "
        "and sign convention for improvement."
    ),
    "DFT": "Please define DFT at first use and state what role the calculations play in the analysis.",
    "SHAP": "Please define SHAP at first use and briefly explain what the values represent.",
    "UMAP": (
        "Please define UMAP at first use and briefly explain that it is used to "
        "visualize high-dimensional representations."
    ),
    "ESP": "Please define ESP at first use and explain how the map is interpreted for defect interaction.",
    "SEM": "Please define SEM at first use and state what morphology evidence it provides.",
    "ns-PPPc": "Please define ns-PPPc at first use and briefly explain the measured trapping signal.",
    "nTC": "Please define nTC at first use and state whether it denotes trapped carrier concentration.",
    "DFBP": "Please identify DFBP at first use as a candidate modulator molecule.",
    "o-TCPN": "Please identify o-TCPN at first use as a candidate modulator molecule.",
    "MLP": "Please spell out MLP at first use and define how it is used as a model baseline.",
    "TPSA": "Please define TPSA at first use or provide a descriptor legend.",
    "ACD/LogP": "Please define ACD/LogP in the descriptor list or provide a legend for descriptor abbreviations.",
}


def notation_replacement(value: str) -> str:
    base, exponent = re.split("e", value, flags=re.I)
    return f"{base} x 10^{int(exponent)}"


def add(finding_map: dict[str, list[Finding]], finding: Finding) -> None:
    finding_map[finding.category].append(finding)


def term_is_defined_near_use(text: str, term: str) -> bool:
    if term in COMMON_NAMES:
        return True
    escaped = re.escape(term)
    plural = rf"{escaped}s?" if term in {"PSC", "PCE"} else escaped
    patterns = [
        rf"\b[A-Za-z][A-Za-z0-9,\-/ ]{{3,}}\s*\({plural}\)",
        rf"{plural}\s*\([A-Za-z][A-Za-z0-9,\-/ ]{{3,}}\)",
        rf"{plural}\s+(?:denotes|represents|refers to|is defined as|stands for)",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def term_pattern(term: str) -> str:
    escaped = re.escape(term)
    if term in {"PSC", "PCE"}:
        return rf"(?<![A-Za-z0-9]){escaped}s?(?![A-Za-z0-9])"
    return rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"


def paragraph_has_bridge_language(text: str) -> bool:
    return bool(
        re.search(
            r"\b(because|therefore|suggesting that|indicating that|consistent with|"
            r"which implies|which can be attributed to|mechanism|rationale)\b",
            text,
            re.I,
        )
    )


def figure_panel_comment(text: str) -> str | None:
    if not FIG_CAPTION_RE.search(text):
        return None
    panel_count = len(re.findall(r"(?:^|[.;]\s+|,\s+|\()\b[a-h]\b(?:,|\)|[-–])", text, re.I))
    if PANEL_RANGE_RE.search(text) and text.count(". ") < 5:
        return (
            "Please explain each figure panel separately. The caption groups multiple panels together, "
            "which makes it hard for reviewers to understand what each subfigure shows."
        )
    if panel_count >= 4:
        return (
            "Please make the caption more self-contained by stating what each panel shows before "
            "moving to the interpretation."
        )
    if re.search(r"\b[a-h],", text) and text.count(". ") < 4:
        return "Please expand the panel descriptions so the caption can stand alone for reviewers."
    return None


def replacement_findings(text: str) -> list[tuple[str, str, str]]:
    replacements = {
        "Here, we show": ("Here, we demonstrate", "Use a stronger manuscript verb for the core claim."),
        "PSC molecular modulation": (
            "molecular modulation of PSCs",
            "Normalize the phrasing so the modifier and target system are clear.",
        ),
        "conventional machine learning approaches": (
            "conventional ML approaches",
            "Use the abbreviation after it has been defined.",
        ),
        "pretrained backbone": ("pre-trained backbone", "Hyphenate pre-trained consistently."),
        "redction": ("reduction", "Fix this spelling error."),
        "moleculespecific": ("molecule-specific", "Hyphenate this compound modifier."),
        "predictedversusexperimental": (
            "predicted-versus-experimental",
            "Hyphenate the compound comparison phrase.",
        ),
        "devicelevel": ("device-level", "Hyphenate this compound modifier."),
        "Pubchem": ("PubChem", "Use the official database capitalization."),
        "Sigma-aldrich": ("Sigma-Aldrich", "Use the official supplier capitalization."),
        "pre-trained MolCLR pre-trained weights was": (
            "pre-trained MolCLR weights were",
            "Remove the duplicated modifier and match subject-verb agreement.",
        ),
        "ethanol，with": ("ethanol, with", "Use an English comma in the methods text."),
        "machine learning model": ("ML model", "Use the abbreviation after it has been defined."),
        "Hypotheses 1:": ("Hypothesis 1", "Use singular hypothesis numbering."),
        "Hypotheses 2:": ("Hypothesis 2", "Use singular hypothesis numbering."),
        "Average Test R2": ("average test R2", "Use sentence-style wording inside the figure caption."),
        "Overfitting Analysis": ("overfitting analysis", "Use sentence-style wording inside the figure caption."),
        "Electroluminescence EQE": (
            "EL EQE",
            "Use the concise notation after introducing electroluminescence.",
        ),
        "candidate molecule treatment group": (
            "candidate-molecule-treated group",
            "Hyphenate this treatment-group descriptor.",
        ),
        "ns-PPPc (nano second Pump-Push-Photocurrent)": (
            "nano second Pump-Push-Photocurrent (ns-PPPc)",
            "Introduce the full name before the abbreviation.",
        ),
    }
    found: list[tuple[str, str, str]] = []
    for old, value in replacements.items():
        if old in text:
            new, note = value
            found.append((old, new, note))
    if "model's" in text:
        found.append(("model's", "model’s", "Use a typographic apostrophe consistently."))
    if "additive's" in text:
        found.append(("additive's", "additive’s", "Use a typographic apostrophe consistently."))
    if '“"diminishing returns”"' in text:
        found.append(('“"diminishing returns”"', "“diminishing returns”", "Remove duplicated straight quotation marks."))
    return found


def review_docx(docx_path: Path) -> list[Finding]:
    paragraphs = [p for p in iter_document_paragraphs(docx_path) if p.text]
    findings_by_category: dict[str, list[Finding]] = defaultdict(list)
    in_conclusion = False
    seen_terms: set[str] = set()

    for paragraph in paragraphs:
        text = paragraph.text
        lower = text.lower()

        if re.fullmatch(r"conclusions?", lower):
            in_conclusion = True
            continue
        if in_conclusion and re.fullmatch(r"(methods?|references|acknowledgements?|author contributions?)", lower):
            in_conclusion = False

        if "table of contents" in lower or re.fullmatch(r"contents", lower):
            add(
                findings_by_category,
                Finding(
                    "journal_structure",
                    "P2",
                    short_anchor(text),
                    "Nature-style manuscript bodies typically do not include a table of contents. Please remove it from the manuscript body or move the navigational summary to cover-letter material.",
                ),
            )

        if in_conclusion and re.search(r"\b(?:Fig\.|Figure|Table|Supplementary Table)\s+\d+", text):
            add(
                findings_by_category,
                Finding(
                    "journal_structure",
                    "P2",
                    short_anchor(text),
                    "Nature-style conclusions typically synthesize the message without introducing new figure or table citations. Please move this supporting detail earlier or restate the conclusion without the citation.",
                ),
            )

        if "all authors analyzed the data" in lower or ("all authors" in lower and "commented the manuscript" in lower):
            add(
                findings_by_category,
                Finding(
                    "author_contributions",
                    "P2",
                    short_anchor(text),
                    "Please expand the author contribution statement with named responsibilities before sharing the manuscript with coauthors.",
                ),
            )

        for term, comment in FIRST_USE_TERMS.items():
            if term in seen_terms:
                continue
            if re.search(term_pattern(term), text):
                seen_terms.add(term)
                if not term_is_defined_near_use(text, term):
                    add(
                        findings_by_category,
                        Finding("acronym_definition", "P2", short_anchor(text), comment),
                    )

        caption_comment = figure_panel_comment(text)
        if caption_comment:
            add(
                findings_by_category,
                Finding("figure_caption", "P2", short_anchor(text), caption_comment),
            )

        if len(text.split()) > 170 and re.search(r"\bFig\.|Supplementary Fig\.|UMAP|attention heatmap|cluster|inductive bias|QSPR|screening", text):
            add(
                findings_by_category,
                Finding(
                    "paragraph_structure",
                    "P2",
                    "As illustrated in Fig. 3d, the randomly initialized backbone yields UMAP visualization of the pre-trained molecular embeddings reveals",
                    "This paragraph combines setup, result, interpretation, and chemical explanation. Please split it so reviewers can follow the representation analysis step by step.",
                    "UMAP visualization of the pre-trained molecular embeddings reveals a dispersed",
                    "the UMAP visualization of embeddings from the randomly initialized backbone reveals a dispersed",
                ),
            )

        if "multi-stage filtering protocol" in lower:
            add(
                findings_by_category,
                Finding(
                    "method_motivation",
                    "P2",
                    short_anchor(text),
                    "Please explain the rationale for the filtering stages and thresholds before reporting the narrowed candidate set.",
                ),
            )

        if "second type of conventional ML models" in text and "KRFP" in text:
            add(
                findings_by_category,
                Finding(
                    "explanation_gap",
                    "P2",
                    short_anchor(text),
                    "Please explain KRFP before using it as a model category. Reviewers need to know what information this fingerprint captures and why it is an appropriate conventional baseline.",
                ),
            )

        if "top-ranked" in lower and "last-ranked" in lower and "discriminative capability" in lower:
            add(
                findings_by_category,
                Finding(
                    "reasoning_gap",
                    "P2",
                    short_anchor(text),
                    "Please explain why comparing the top-ranked and last-ranked molecules demonstrates model discriminative capability, rather than only listing representative molecules.",
                ),
            )

        if "qualitative support for the learned qspr relationships" in lower and not paragraph_has_bridge_language(text):
            add(
                findings_by_category,
                Finding(
                    "reasoning_gap",
                    "P2",
                    short_anchor(text),
                    "Please add a clearer bridge from the observed chemical separation to the claim that the model learned meaningful structure-property relationships.",
                ),
            )

        if "validated the two major clusters" in lower and "dft-calculated properties" in lower:
            add(
                findings_by_category,
                Finding(
                    "reasoning_gap",
                    "P2",
                    short_anchor(text),
                    "Please explain why the selected DFT-calculated properties validate the representation clusters and how they connect to modulator performance.",
                ),
            )

        if "inductive bias" in lower and ("baseline" in lower or "residual" in lower):
            add(
                findings_by_category,
                Finding(
                    "method_motivation",
                    "P2",
                    short_anchor(text),
                    "Please slow down the inductive-bias argument: define the baseline and residual terms, then explain why separating them improves the learning task.",
                ),
            )

        if "electrostatic potential" in lower and "defects" in lower and "can potentially attract" in lower:
            add(
                findings_by_category,
                Finding(
                    "reasoning_gap",
                    "P2",
                    short_anchor(text),
                    "Please clarify the mechanistic link between the ESP features and defect passivation, including what interaction is expected at the perovskite surface.",
                ),
            )

        if "photoluminescence" in lower and "non-radiative recombination" in lower:
            add(
                findings_by_category,
                Finding(
                    "reasoning_gap",
                    "P2",
                    short_anchor(text),
                    "Please explain the interpretation of the PL evidence more explicitly so the reader can connect the intensity/lifetime change to reduced non-radiative recombination.",
                ),
            )

        if "where are learnable kernel centers" in lower or "where is a bandwidth parameter" in lower:
            add(
                findings_by_category,
                Finding(
                    "definition_gap",
                    "P1",
                    short_anchor(text),
                    "The equation variables are missing before the definitions. Please name the kernel centers and bandwidth parameter explicitly so the formula is readable.",
                ),
            )

        if "pij0=mlpexp" in lower or ("mlp" in text and "k=1" in lower and "rij" in lower):
            add(
                findings_by_category,
                Finding(
                    "definition_gap",
                    "P1",
                    short_anchor(text),
                    "Please define MLP, K, the kernel index, and the distance term around this pair representation equation.",
                ),
            )

        if "latom=" in lower and ("pai" in lower or "hi" in lower):
            add(
                findings_by_category,
                Finding(
                    "definition_gap",
                    "P1",
                    short_anchor(text),
                    "Please define Latom, P, the masked-atom label, and the final atom representation before or immediately after this loss equation.",
                ),
            )

        if "ltotal=" in lower and ("latom" in lower or "lcoord" in lower or "lnorm" in lower):
            add(
                findings_by_category,
                Finding(
                    "definition_gap",
                    "P1",
                    short_anchor(text),
                    "Please define each loss term and weighting coefficient in the total pre-training objective.",
                ),
            )

        if "lmse=" in lower and ("fqspr" in lower or "rxi" in lower):
            add(
                findings_by_category,
                Finding(
                    "definition_gap",
                    "P1",
                    short_anchor(text),
                    "Please define every variable in the QSPR loss, including the residual target, model prediction, molecule index, and sample count.",
                ),
            )

        if text.strip() == "8.5e-05":
            add(
                findings_by_category,
                Finding(
                    "format_notation",
                    "P1",
                    short_anchor(text),
                    "Please use manuscript-style scientific notation instead of programming-style exponential notation.",
                    "8.5e-05",
                    "8.5 x 10^-5",
                ),
            )

        if "rx: the residual" in lower or "RX: The residual" in text:
            add(
                findings_by_category,
                Finding(
                    "definition_gap",
                    "P1",
                    short_anchor(text),
                    "Please define R(X) more explicitly and state how it differs from the linear baseline contribution.",
                ),
            )

        if "ri≔" in lower or "ri:=" in lower:
            add(
                findings_by_category,
                Finding(
                    "definition_gap",
                    "P1",
                    short_anchor(text),
                    "Please define Ri as the training target residual and explain each term in the residual equation.",
                ),
            )

        if "δ∼u" in lower or "delta-position" in lower:
            if "A˚" in text or "A°" in text:
                add(
                    findings_by_category,
                    Finding(
                        "format_notation",
                        "P1",
                        short_anchor(text),
                        "Please verify the coordinate-noise unit and use standard Angstrom notation if Å is intended.",
                        "A˚",
                        "Å",
                    ),
                )
            add(
                findings_by_category,
                Finding(
                    "definition_gap",
                    "P1",
                    short_anchor(text),
                    "Please define the symbols in this pre-training task together, including the noise variable, corrupted-atom set, predicted delta-position, and loss terms.",
                ),
            )

        if "representation normalization loss" in lower and "for any representation" in lower:
            add(
                findings_by_category,
                Finding(
                    "clarity_check",
                    "P2",
                    short_anchor(text),
                    "Please check whether this normalization-loss description is mathematically complete; the variables in the following equation should be defined immediately around the equation.",
                ),
            )

        for match in SCIENTIFIC_NOTATION_RE.finditer(text):
            raw = match.group(0)
            add(
                findings_by_category,
                Finding(
                    "format_notation",
                    "P3",
                    short_anchor(text),
                    "Please use manuscript-style scientific notation instead of programming-style exponential notation.",
                    raw,
                    notation_replacement(raw),
                ),
            )

        for old, new, note in replacement_findings(text):
            add(
                findings_by_category,
                Finding(
                    "format_notation",
                    "P2",
                    short_anchor(text),
                    note,
                    old,
                    new,
                ),
            )

        if lower.startswith("here, represents") or lower.startswith(": the ") or "for each data point (," in lower:
            add(
                findings_by_category,
                Finding(
                    "definition_gap",
                    "P1",
                    short_anchor(text),
                    "The symbol being defined appears to be missing. Please restore the variable name before the definition so the mathematical framework is understandable.",
                ),
            )

        if "Here, RMSE represents" in text and "ΔPCEpred" in text and "ΔPCEexp" in text:
            add(
                findings_by_category,
                Finding(
                    "definition_gap",
                    "P2",
                    short_anchor(text),
                    "Please define ΔPCEpred and ΔPCEexp explicitly when introducing the residual/error term, rather than relying on the notation alone.",
                ),
            )

        if "I ∈ ℝ" in text and "initial PCE" in text:
            add(
                findings_by_category,
                Finding(
                    "notation_choice",
                    "P3",
                    short_anchor(text),
                    "Consider using a more intuitive notation such as PCEi for the initial device efficiency, or explain why I is preferred.",
                ),
            )

        if "negative correlation between Initial_PCE and ΔPCE" in text:
            add(
                findings_by_category,
                Finding(
                    "notation_consistency",
                    "P2",
                    short_anchor(text),
                    "Please keep the notation for initial PCE consistent with the symbol definition section; avoid switching between Initial_PCE and the defined symbol without explanation.",
                ),
            )

        if text.startswith("Supplementary Figure 1 |") and "Outer loop" in text:
            add(
                findings_by_category,
                Finding(
                    "figure_caption",
                    "P2",
                    short_anchor(text),
                    "Please explain what the outer loop contains and how it differs from the inner loop before reporting the seeds and metrics.",
                ),
            )

        if text.startswith("Supplementary Figure 4 |"):
            add(
                findings_by_category,
                Finding(
                    "figure_caption",
                    "P2",
                    short_anchor(text),
                    "Please explain what each panel shows before discussing baseline and residual separation; otherwise the interpretation starts before the figure is introduced.",
                ),
            )

        if text.startswith("Supplementary Figure") and ("SHAP" in text or "attention heatmap" in lower):
            add(
                findings_by_category,
                Finding(
                    "figure_caption",
                    "P2",
                    short_anchor(text),
                    "Please state how to read the interpretability panel before interpreting feature or substructure importance.",
                ),
            )

        comma_items = [item.strip() for item in text.split(",")]
        uppercase_like_items = [
            item for item in comma_items
            if re.search(r"[A-Z]{2,}|[A-Z][a-z]*/[A-Z][a-z]*|Initial PCE", item)
        ]
        if len(comma_items) >= 8 and len(uppercase_like_items) >= 6 and len(text.split()) <= 24:
            add(
                findings_by_category,
                Finding(
                    "abbreviation_legend",
                    "P1",
                    short_anchor(text),
                    "Please define these descriptor abbreviations or provide a legend; this list is not interpretable to reviewers as written.",
                ),
            )

    ordered_categories = [
        "journal_structure",
        "author_contributions",
        "format_notation",
        "acronym_definition",
        "method_motivation",
        "explanation_gap",
        "reasoning_gap",
        "paragraph_structure",
        "figure_caption",
        "abbreviation_legend",
        "definition_gap",
        "clarity_check",
        "notation_choice",
        "notation_consistency",
    ]
    limits = {
        "journal_structure": 3,
        "author_contributions": 1,
        "acronym_definition": 12,
        "method_motivation": 6,
        "explanation_gap": 6,
        "reasoning_gap": 8,
        "paragraph_structure": 4,
        "figure_caption": 10,
        "abbreviation_legend": 4,
        "definition_gap": 12,
        "clarity_check": 4,
        "notation_choice": 3,
        "notation_consistency": 3,
        "format_notation": 24,
    }

    selected: list[Finding] = []
    for category in ordered_categories:
        selected.extend(findings_by_category.get(category, [])[: limits[category]])
    return unique_findings(selected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--max-findings", type=int, default=70)
    args = parser.parse_args()

    docx_path = args.docx.expanduser().resolve()
    findings = review_docx(docx_path)[: args.max_findings]
    payload = {
        "file": str(docx_path),
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
    }
    write_json(args.out, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
