"""Detection of direct identifiers the clinical NER model does not label.

The French clinical model isolates age and gender, and nothing else about a
person: it has no label for a name, a social-security number, a phone number or
an address. Those are exactly the direct identifiers that matter for GDPR
Art. 4(5), so they are found here by pattern rather than by the model, and fed
into the same masking pass.

Patterns are deliberately conservative in shape but permissive in what they
mask: over-masking costs a clinician a detail they can find in the source
document, under-masking leaks an identifier that was supposed to be gone.
"""

import re
from dataclasses import dataclass
from typing import List, Pattern, Tuple

# A person's name never appears alone in a clinical note reliably enough to
# detect it, so names are anchored to what precedes them: a civility, or a
# field label. The capture group is the name, never the anchor.
_NAME_ANCHOR = (
    r"(?:M\.|MM\.|Mme|Mmes|Mlle|Monsieur|Madame|Mademoiselle|"
    r"Dr\.?|Docteur|Pr\.?|Professeur|"
    r"Patient(?:e)?|Nom|Pr[ée]nom|N[ée]\(?e\)?)"
)
_NAME = r"[A-ZÀ-ÖØ-Þ][\w'’-]+(?:\s+[A-ZÀ-ÖØ-Þ][\w'’-]+)?"

_MONTHS = (
    r"(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|"
    r"septembre|octobre|novembre|d[ée]cembre)"
)


@dataclass(frozen=True)
class DetectedIdentifier:
    """A direct identifier located in the text."""

    start: int
    end: int
    label: str

    @property
    def length(self) -> int:
        return self.end - self.start


def _compile(pattern: str) -> Pattern[str]:
    return re.compile(pattern, re.IGNORECASE | re.UNICODE)


def _compile_cased(pattern: str) -> Pattern[str]:
    """Compile case-sensitively.

    Capitalisation is what separates a name from ordinary prose: with
    ``IGNORECASE``, ``Patient présente une`` reads as a two-word name.
    """
    return re.compile(pattern, re.UNICODE)


# (label, pattern, group holding the identifier itself)
_PATTERNS: List[Tuple[str, Pattern[str], int]] = [
    # NIR: 13 digits plus a 2-digit key, commonly written in groups.
    (
        "nir",
        _compile(r"\b[12][\s.]?\d{2}[\s.]?\d{2}[\s.]?\d{2,3}[\s.]?\d{3}[\s.]?\d{3}"
                 r"(?:[\s.]?\d{2})?\b"),
        0,
    ),
    (
        "email",
        _compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
        0,
    ),
    (
        "telephone",
        _compile(r"(?:\+33[\s.-]?\(?0?\)?|\b0)[1-9](?:[\s.-]?\d{2}){4}\b"),
        0,
    ),
    (
        "dossier",
        _compile(r"\b(?:IPP|NIP|NDA|dossier)\s*(?:n[o°]?)?\s*:?\s*([A-Z0-9][A-Z0-9-]{3,})\b"),
        1,
    ),
    (
        "nom",
        _compile_cased(rf"\b(?i:{_NAME_ANCHOR})\s*:?\s+({_NAME})"),
        1,
    ),
    (
        "date",
        _compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"),
        0,
    ),
    (
        "date",
        _compile(rf"\b\d{{1,2}}(?:er)?\s+{_MONTHS}\s+\d{{4}}\b"),
        0,
    ),
    # A postal code is only masked when a town plausibly follows it, so ordinary
    # five-digit clinical values are left alone.
    (
        "adresse",
        _compile_cased(r"\b\d{5}\b(?=\s+[A-ZÀ-ÖØ-Þ])"),
        0,
    ),
]


class DirectIdentifierDetector:
    """Finds direct identifiers by pattern, where the model has no label."""

    def detect(self, text: str) -> List[DetectedIdentifier]:
        """
        Locate every direct identifier in the text.

        Overlapping matches are resolved in favour of the longest, so a date
        inside a social-security number does not split the number in two.

        :param text: The text to scan.
        :return: Identifiers ordered by position, without overlaps.
        """
        found: List[DetectedIdentifier] = []

        for label, pattern, group in _PATTERNS:
            for match in pattern.finditer(text):
                start, end = match.span(group)
                if start >= 0 and end > start:
                    found.append(DetectedIdentifier(start, end, label))

        # Longest first at an equal start, and longest wins any overlap.
        found.sort(key=lambda item: (item.start, -item.length))

        kept: List[DetectedIdentifier] = []
        for candidate in found:
            if any(
                candidate.start < existing.end and existing.start < candidate.end
                for existing in kept
            ):
                continue
            kept.append(candidate)

        return kept
