"""
Turn categorised NER output into a summary a clinician can read.

Nothing here generates language. Every word in the result is either a fixed
heading or a span the model marked in the submitted documents, so the summary
cannot say anything the documents did not.
"""

import re
import unicodedata
from typing import Dict, Iterable, List, Optional, Tuple

from app.schemas.extraction import EntityDetail
from app.schemas.summary import ClinicalSummary, SummarySection

# The only use the score has. It is a noise floor, not a number anyone sees:
# below this the model is guessing, and a guess in a clinical summary costs
# more than the recall it buys.
MIN_CONFIDENCE = 0.5

# The category the opening line is built from. Named rather than inlined
# because the shipped label mappings have to agree with it: a mapping that
# files demographics elsewhere silently costs every summary its patient line.
PATIENT_INFO_CATEGORY = "patient_info"

# Sections in the order a clinician reads them, with the heading each gets.
# `temporal`, `measurements` and `other` are deliberately absent: a bare list of
# durations, of loose values, or of unclassified spans carries no clinical
# meaning once it is separated from the sentence it came from. They stay in the
# entity payload for callers that want them.
SECTION_ORDER: Tuple[Tuple[str, str], ...] = (
    ("pathologies", "Pathologies"),
    ("symptoms", "Signes et symptômes"),
    ("examinations", "Examens"),
    ("treatments", "Traitements"),
    ("anatomy", "Localisations"),
)

WHITESPACE = re.compile(r"\s+")

# Trailing and leading punctuation survives a span boundary often enough to
# create two entries for one finding.
EDGE_PUNCTUATION = ".,;:!?()[]{}\"'«»…-–—/\\ "


def comparison_key(text: str) -> str:
    """
    Fold a span to the form used to decide whether two mentions are the same.

    Case, accents, inner spacing and edge punctuation all vary between two
    mentions of one finding, and none of them makes it a different finding.
    """
    stripped = text.strip(EDGE_PUNCTUATION).casefold()
    collapsed = WHITESPACE.sub(" ", stripped)
    decomposed = unicodedata.normalize("NFKD", collapsed)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def is_worth_reporting(entity: EntityDetail) -> bool:
    """Reject what would be noise in a summary rather than a finding."""
    if entity.score < MIN_CONFIDENCE:
        return False

    cleaned = entity.text.strip(EDGE_PUNCTUATION)
    # A single character is a tokenizer artefact, never a clinical term, and a
    # span with no letter in it is a number or a symbol that lost its context.
    return len(cleaned) > 1 and any(char.isalpha() for char in cleaned)


class Finding:
    """One deduplicated finding and the support it has across the documents."""

    def __init__(self, display: str, document_index: int) -> None:
        self.display = display
        self.documents = {document_index}
        self.mentions = 1

    def add(self, display: str, document_index: int) -> None:
        self.documents.add(document_index)
        self.mentions += 1
        # Keep the longest surface form seen: the model truncates outer
        # mentions (see DECISION.md), so the longest is the most complete one.
        if len(display) > len(self.display):
            self.display = display

    def rank(self) -> Tuple[int, int, str]:
        """Most documents first, then most mentions, then stable alphabetical."""
        return (-len(self.documents), -self.mentions, comparison_key(self.display))


def collect_findings(
    documents: Iterable[Dict[str, List[EntityDetail]]], category: str
) -> List[str]:
    """Deduplicate one category across every document, most-supported first."""
    findings: Dict[str, Finding] = {}

    for document_index, entities in enumerate(documents):
        for entity in entities.get(category, []):
            if not is_worth_reporting(entity):
                continue

            display = WHITESPACE.sub(" ", entity.text.strip(EDGE_PUNCTUATION))
            key = comparison_key(display)
            if not key:
                continue

            existing = findings.get(key)
            if existing is None:
                findings[key] = Finding(display, document_index)
            else:
                existing.add(display, document_index)

    return [finding.display for finding in sorted(findings.values(), key=Finding.rank)]


def as_sentence(findings: List[str]) -> str:
    """Join findings into one readable sentence."""
    joined = ", ".join(findings)
    return joined[:1].upper() + joined[1:] + "."


def demographic_line(
    documents: Iterable[Dict[str, List[EntityDetail]]],
) -> Optional[str]:
    """
    Build the opening line from the age and sex the model marked.

    The model emits `age` and `genre`; anything else the mapping files under
    patient information is appended as it stands rather than dropped.
    """
    age: Optional[str] = None
    sex: Optional[str] = None
    extras: List[str] = []
    seen: set[str] = set()

    for entities in documents:
        for entity in entities.get(PATIENT_INFO_CATEGORY, []):
            if not is_worth_reporting(entity):
                continue

            value = WHITESPACE.sub(" ", entity.text.strip(EDGE_PUNCTUATION))
            label = entity.label.casefold()

            # First mention wins for age and sex: a document that later quotes
            # a family member's age must not overwrite the patient's.
            if label == "age" and age is None:
                age = value
            elif label == "genre" and sex is None:
                sex = value
            elif label not in {"age", "genre"}:
                key = comparison_key(value)
                if key and key not in seen:
                    seen.add(key)
                    extras.append(value)

    parts = [part for part in (age, sex) if part] + extras
    if not parts:
        return None

    return "Patient, " + ", ".join(parts) + "."


def summarize(documents: List[Dict[str, List[EntityDetail]]]) -> ClinicalSummary:
    """
    Assemble the summary of one or more documents about the same patient.

    :param documents: Categorised entities, one dictionary per document.
    :return: The summary, flagged empty when nothing clinical was found.
    """
    sections = []
    for key, heading in SECTION_ORDER:
        findings = collect_findings(documents, key)
        if not findings:
            continue

        sections.append(
            SummarySection(
                key=key,
                heading=heading,
                sentence=as_sentence(findings),
                findings=findings,
            )
        )

    patient = demographic_line(documents)

    return ClinicalSummary(
        patient=patient,
        sections=sections,
        document_count=len(documents),
        empty=not sections and patient is None,
    )
