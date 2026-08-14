# pylint: disable=W0621
import pytest

from app.schemas.extraction import EntityDetail
from app.services.pseudonymizer import Pseudonymizer

TEXT = "Le patient, homme de 42 ans, présente une fièvre."
#       0         1         2         3         4
#       0123456789012345678901234567890123456789012345678


@pytest.fixture
def pseudonymizer():
    return Pseudonymizer()


def entities_for_text():
    return {
        "patient_info": [
            EntityDetail(text="homme", label="genre", score=0.9, start=12, end=17),
            EntityDetail(text="42 ans", label="age", score=0.9, start=21, end=27),
        ],
        "symptoms": [
            EntityDetail(text="fièvre", label="sosy", score=0.8, start=42, end=48)
        ],
    }


def test_masks_patient_information_in_the_text(pseudonymizer):
    masked, _ = pseudonymizer.mask(TEXT, entities_for_text())

    assert "homme" not in masked
    assert "42 ans" not in masked
    assert "[GENRE_1]" in masked
    assert "[AGE_1]" in masked


def test_leaves_clinical_content_untouched(pseudonymizer):
    masked, entities = pseudonymizer.mask(TEXT, entities_for_text())

    assert "fièvre" in masked
    assert entities["symptoms"][0].text == "fièvre"


def test_remaps_offsets_of_surviving_entities(pseudonymizer):
    masked, entities = pseudonymizer.mask(TEXT, entities_for_text())

    symptom = entities["symptoms"][0]
    assert masked[symptom.start : symptom.end] == "fièvre"


def test_masked_entities_point_at_their_placeholder(pseudonymizer):
    masked, entities = pseudonymizer.mask(TEXT, entities_for_text())

    for entity in entities["patient_info"]:
        assert masked[entity.start : entity.end] == entity.text
        assert entity.text.startswith("[")


def test_masks_every_occurrence_not_only_the_reported_one(pseudonymizer):
    # The extractor deduplicates entities, so a repeated identifier is reported
    # once. Masking by offset alone would leave the other occurrences in place.
    text = "Mme Dupont, femme de 42 ans. La femme se plaint de fièvre."
    entities = {
        "patient_info": [
            EntityDetail(text="femme", label="genre", score=0.9, start=12, end=17),
        ]
    }

    masked, _ = pseudonymizer.mask(text, entities)

    assert "femme" not in masked
    assert masked.count("[GENRE_1]") == 2


def test_does_not_mask_inside_a_longer_word(pseudonymizer):
    text = "age 42. Le dosage est stable."
    entities = {
        "patient_info": [
            EntityDetail(text="age", label="age", score=0.9, start=0, end=3)
        ]
    }

    masked, _ = pseudonymizer.mask(text, entities)

    assert "dosage" in masked
    assert masked.startswith("[AGE_1] 42.")


def test_same_surface_form_gets_the_same_placeholder(pseudonymizer):
    text = "homme, puis homme"
    entities = {
        "patient_info": [
            EntityDetail(text="homme", label="genre", score=0.9, start=0, end=5),
            EntityDetail(text="homme", label="genre", score=0.9, start=12, end=17),
        ]
    }

    masked, _ = pseudonymizer.mask(text, entities)

    assert masked == "[GENRE_1], puis [GENRE_1]"


def test_distinct_surface_forms_are_numbered(pseudonymizer):
    text = "homme femme"
    entities = {
        "patient_info": [
            EntityDetail(text="homme", label="genre", score=0.9, start=0, end=5),
            EntityDetail(text="femme", label="genre", score=0.9, start=6, end=11),
        ]
    }

    masked, _ = pseudonymizer.mask(text, entities)

    assert masked == "[GENRE_1] [GENRE_2]"


def test_bio_prefixes_are_stripped_from_placeholders(pseudonymizer):
    entities = {
        "patient_info": [
            EntityDetail(text="42 ans", label="B-age", score=0.9, start=0, end=6)
        ]
    }

    masked, _ = pseudonymizer.mask("42 ans plus tard", entities)

    assert masked.startswith("[AGE_1]")


def test_accented_labels_survive_the_placeholder(pseudonymizer):
    entities = {
        "patient_info": [
            EntityDetail(text="42 ans", label="âge", score=0.9, start=0, end=6)
        ]
    }

    masked, _ = pseudonymizer.mask("42 ans plus tard", entities)

    assert masked.startswith("[ÂGE_1]")


def test_whitespace_inside_a_span_is_preserved(pseudonymizer):
    # The model sometimes reports a span with surrounding whitespace.
    text = "Le homme a de la fièvre"
    entities = {
        "patient_info": [
            EntityDetail(text="homme", label="genre", score=0.9, start=2, end=9)
        ]
    }

    masked, _ = pseudonymizer.mask(text, entities)

    assert masked == "Le [GENRE_1] a de la fièvre"


def test_entities_without_offsets_are_masked_by_their_text(pseudonymizer):
    entities = {
        "patient_info": [EntityDetail(text="homme", label="genre", score=0.9)],
    }

    masked, result = pseudonymizer.mask(TEXT, entities)

    assert "homme" not in masked
    assert result["patient_info"][0].text == "[GENRE_1]"


def test_nothing_detected_leaves_everything_alone(pseudonymizer):
    entities = {
        "patient_info": [],
        "symptoms": [
            EntityDetail(text="fièvre", label="sosy", score=0.8, start=42, end=48)
        ],
    }

    masked, result = pseudonymizer.mask(TEXT, entities)

    assert masked == TEXT
    assert result["symptoms"][0].start == 42


def test_nested_spans_mask_the_widest_one(pseudonymizer):
    # A short span winning would leave the rest of the identifier behind.
    text = "Patient Jean Dupont, 42 ans."
    entities = {
        "patient_info": [
            EntityDetail(text="Jean", label="genre", score=0.5, start=8, end=12),
            EntityDetail(text="Jean Dupont", label="genre", score=0.9, start=8, end=19),
        ]
    }

    masked, _ = pseudonymizer.mask(text, entities)

    assert "Dupont" not in masked
    assert "Jean" not in masked


def test_overlapping_spans_are_masked_once(pseudonymizer):
    entities = {
        "patient_info": [
            EntityDetail(text="42 ans", label="age", score=0.9, start=21, end=27),
            EntityDetail(text="ans", label="age", score=0.5, start=24, end=27),
        ]
    }

    masked, _ = pseudonymizer.mask(TEXT, entities)

    assert masked.count("[AGE_1]") == 1
    assert "42 ans" not in masked


def test_entity_overlapping_a_placeholder_never_reports_the_raw_text(pseudonymizer):
    # The characters are gone from the masked text, so repeating them in an
    # entity would defeat the mask.
    entities = {
        "patient_info": [
            EntityDetail(text="42 ans", label="age", score=0.9, start=21, end=27)
        ],
        "measurements": [
            EntityDetail(text="42", label="valeur", score=0.7, start=21, end=23)
        ],
    }

    _, result = pseudonymizer.mask(TEXT, entities)

    measurement = result["measurements"][0]
    assert measurement.text == "[AGE_1]"
    assert measurement.start is None
    assert measurement.end is None


def test_no_category_keeps_a_masked_identifier(pseudonymizer):
    text = "Le patient homme a de la fièvre"
    entities = {
        "patient_info": [
            EntityDetail(text="homme", label="genre", score=0.9, start=11, end=16)
        ],
        "other": [
            EntityDetail(text="homme", label="chimiques", score=0.4, start=11, end=16)
        ],
    }

    masked, result = pseudonymizer.mask(text, entities)

    assert "homme" not in masked
    for details in result.values():
        for entity in details:
            assert "homme" not in entity.text
