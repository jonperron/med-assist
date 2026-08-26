"""
Turn categorised NER output into a summary a clinician can read.

Nothing here generates language. Every word in the result is either a fixed
heading or a span the model marked in the submitted documents, so the summary
cannot say anything the documents did not.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Sequence, Tuple

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

# The two labels the opening line is built from. Compared through
# `comparison_key`, because `EntityExtractor.normalize_label` strips accents
# before categorising: a model emitting `âge` lands in patient information, and
# a raw `== "age"` here would then miss it.
AGE_LABEL = "age"
SEX_LABEL = "genre"

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


def is_worth_reporting(entity: EntityDetail, require_letter: bool = True) -> bool:
    """
    Reject what would be noise in a summary rather than a finding.

    `require_letter` is off for demographics: in a clinical section a span with
    no letter is a number that lost its context, but an age annotated as `67`
    rather than `67 ans` is the patient's age, and dropping it costs the
    summary its opening line with nowhere to fall back to.
    """
    if entity.score < MIN_CONFIDENCE:
        return False

    cleaned = entity.text.strip(EDGE_PUNCTUATION)
    if not cleaned:
        return False

    # A single character is a tokenizer artefact, never a clinical term.
    if require_letter:
        return len(cleaned) > 1 and any(char.isalpha() for char in cleaned)
    return True


class Finding:
    """One deduplicated finding and the support it has across the documents."""

    def __init__(self, display: str, document_index: int) -> None:
        self.display = display
        self.documents = {document_index}
        self.mentions = 1

    def add(self, document_index: int) -> None:
        # The first surface form seen is the one reported. A later mention
        # cannot be a better one: two mentions only merge when they share a
        # comparison key, and that key already folds away the case, accents,
        # spacing and edge punctuation they could differ by.
        self.documents.add(document_index)
        self.mentions += 1

    def rank(self) -> Tuple[int, int, str]:
        """Most documents first, then most mentions, then stable alphabetical."""
        return (-len(self.documents), -self.mentions, comparison_key(self.display))


def collect_findings(
    documents: Sequence[Dict[str, List[EntityDetail]]], category: str
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
                existing.add(document_index)

    return [finding.display for finding in sorted(findings.values(), key=Finding.rank)]


def as_sentence(findings: List[str]) -> str:
    """
    Join findings into one readable sentence.

    The first finding is capitalised only when it reads as ordinary prose.
    Clinical vocabulary carries meaningful case - `pH`, `mmHg`, `pCO2` - and
    upper-casing the first letter of those turns a measurement into a different
    token, so a first word that already holds an uppercase letter is left alone.
    """
    joined = ", ".join(findings)
    first_word = joined.split(" ", 1)[0]
    if any(char.isupper() for char in first_word[1:]):
        return joined + "."

    return joined[:1].upper() + joined[1:] + "."


def demographic_line(
    documents: Sequence[Dict[str, List[EntityDetail]]],
) -> Optional[str]:
    """
    Build the opening line from the age and sex the model marked.

    Only `age` and `genre` are read. Everything else the mapping happens to
    file under patient information is left out on purpose: `fr.json` also files
    the MeSH axes `homme` and `femme` there, and those are male and female
    urogenital *diseases*, not demographics. An open-ended branch here would
    render a disease as a patient attribute in the summary's first line. The
    served model does not emit those axes, so this is a guard, not a live bug -
    but the guard belongs in the code rather than in the weights.
    """
    age: Optional[str] = None
    sex: Optional[str] = None

    for entities in documents:
        for entity in entities.get(PATIENT_INFO_CATEGORY, []):
            if not is_worth_reporting(entity, require_letter=False):
                continue

            value = WHITESPACE.sub(" ", entity.text.strip(EDGE_PUNCTUATION))
            label = comparison_key(entity.label)

            # First mention wins for both: a document that later quotes a
            # family member's age or sex must not overwrite the patient's.
            if label == AGE_LABEL and age is None:
                age = value
            elif label == SEX_LABEL and sex is None:
                sex = value

    parts = [part for part in (age, sex) if part]
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
