"""Masking of detected patient identifiers.

The NER model already isolates a ``patient_info`` category. This service reuses
that signal to replace the matching spans with stable placeholders, so text that
is displayed or stored no longer carries the identifiers the model found.

Masking is driven by the surface forms of the detected identifiers, not only by
the offsets the model reported: the extractor deduplicates entities, so a name
that appears three times is reported once, and offset-only masking would leave
the other two in the clear.
"""

import re
from typing import Dict, List, Optional, Tuple

from app.schemas.extraction import EntityDetail

PATIENT_INFO_CATEGORY = "patient_info"

_LABEL_CLEANUP = re.compile(r"[^\w]+", re.UNICODE)

# (start, end) of a masked span -> its placeholder
Replacements = Dict[Tuple[int, int], str]


def _placeholder_label(label: str) -> str:
    """Turn a model label into a placeholder-safe token, e.g. ``B-age`` -> ``AGE``."""
    cleaned = _LABEL_CLEANUP.sub("_", label.upper()).strip("_")
    if cleaned.startswith(("B_", "I_")):
        cleaned = cleaned[2:]
    return cleaned or "PATIENT_INFO"


def _occurrence_pattern(surface: str) -> re.Pattern:
    """Match a surface form, without matching inside a longer word."""
    pattern = re.escape(surface)
    if surface[:1].isalnum():
        pattern = r"(?<!\w)" + pattern
    if surface[-1:].isalnum():
        pattern = pattern + r"(?!\w)"
    return re.compile(pattern, re.IGNORECASE | re.UNICODE)


class Pseudonymizer:
    """Replaces patient-identifying spans with placeholders."""

    def mask(
        self, text: str, entities: Dict[str, List[EntityDetail]]
    ) -> Tuple[str, Dict[str, List[EntityDetail]]]:
        """
        Mask every occurrence of every detected ``patient_info`` identifier.

        Offsets of the surviving entities are remapped onto the masked text, so
        the response stays internally consistent. Entities that overlap a masked
        span report the placeholder instead of their original text: the
        characters are gone from the text, so repeating them would defeat the mask.

        :param text: The text the entities were extracted from.
        :param entities: Categorised entities, as returned by the extractor.
        :return: The masked text and the entities rewritten against it.
        """
        placeholders = self._assign_placeholders(text, entities)
        if not placeholders:
            return text, entities

        spans = self._locate_spans(text, entities, placeholders)
        masked_text, replacements = self._apply(text, spans)

        return masked_text, {
            category: [
                self._remap(entity, replacements, placeholders) for entity in details
            ]
            for category, details in entities.items()
        }

    @staticmethod
    def _assign_placeholders(
        text: str, entities: Dict[str, List[EntityDetail]]
    ) -> Dict[str, str]:
        """Map each distinct identifier, lowercased, to its stable placeholder."""
        placeholders: Dict[str, str] = {}
        counters: Dict[str, int] = {}

        for entity in entities.get(PATIENT_INFO_CATEGORY, []):
            # Prefer the source text over the entity's own, which may already
            # have been rewritten by an earlier pass.
            if entity.start is not None and entity.end is not None:
                surface = text[entity.start : entity.end]
            else:
                surface = entity.text
            surface = surface.strip()

            if not surface or surface.lower() in placeholders:
                continue

            label = _placeholder_label(entity.label)
            counters[label] = counters.get(label, 0) + 1
            placeholders[surface.lower()] = f"[{label}_{counters[label]}]"

        return placeholders

    @staticmethod
    def _locate_spans(
        text: str,
        entities: Dict[str, List[EntityDetail]],
        placeholders: Dict[str, str],
    ) -> List[Tuple[int, int, str]]:
        """Find every span to mask: the reported ones and every repeat occurrence."""
        spans: List[Tuple[int, int, str]] = []

        for entity in entities.get(PATIENT_INFO_CATEGORY, []):
            if entity.start is None or entity.end is None:
                continue
            # The model sometimes includes surrounding whitespace in a span;
            # masking it would glue the placeholder to its neighbour.
            start, end = entity.start, entity.end
            while start < end and text[start].isspace():
                start += 1
            while end > start and text[end - 1].isspace():
                end -= 1
            surface = text[start:end].lower()
            if surface in placeholders:
                spans.append((start, end, placeholders[surface]))

        for surface, placeholder in placeholders.items():
            for match in _occurrence_pattern(surface).finditer(text):
                spans.append((match.start(), match.end(), placeholder))

        # Widest span first at an equal start, so a nested span never wins and
        # leaves the rest of a longer identifier behind.
        spans.sort(key=lambda span: (span[0], -span[1]))
        return spans

    @staticmethod
    def _apply(
        text: str, spans: List[Tuple[int, int, str]]
    ) -> Tuple[str, Replacements]:
        """Rewrite the text, returning it with the spans that were replaced."""
        replacements: Replacements = {}
        parts: List[str] = []
        cursor = 0

        for start, end, placeholder in spans:
            if start < cursor:
                # Overlaps a span that was already masked.
                continue
            parts.append(text[cursor:start])
            parts.append(placeholder)
            replacements[(start, end)] = placeholder
            cursor = end

        parts.append(text[cursor:])
        return "".join(parts), replacements

    @staticmethod
    def _remap(
        entity: EntityDetail,
        replacements: Replacements,
        placeholders: Dict[str, str],
    ) -> EntityDetail:
        """Rewrite one entity against the masked text."""
        if entity.start is None or entity.end is None:
            # No offsets to work from, e.g. an entity read back from storage.
            # Its text is still matched against the identifiers being masked.
            placeholder = placeholders.get(entity.text.strip().lower())
            if placeholder is None:
                return entity
            return entity.model_copy(update={"text": placeholder})

        shift = 0
        covering: Optional[str] = None
        exact = False

        for (start, end), placeholder in replacements.items():
            if end <= entity.start:
                shift += len(placeholder) - (end - start)
            if start < entity.end and entity.start < end:
                covering = covering or placeholder
                exact = exact or (start == entity.start and end == entity.end)

        if covering is None:
            if shift == 0:
                return entity
            return entity.model_copy(
                update={"start": entity.start + shift, "end": entity.end + shift}
            )

        if exact:
            return entity.model_copy(
                update={
                    "text": covering,
                    "start": entity.start + shift,
                    "end": entity.start + shift + len(covering),
                }
            )

        # Partially covered: the entity spans masked and unmasked characters, so
        # neither its text nor its offsets survive intact.
        return entity.model_copy(update={"text": covering, "start": None, "end": None})
