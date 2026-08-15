"""The shipped label mappings decide what the API answers, so they are tested.

Every other extractor test builds a synthetic three-category mapping, which is
why nothing noticed that `fr.json` and `es.json` themselves were never loaded.
A label the mapping does not recognise costs an entity its category - and in
`patient_info`, an identifier its mask.
"""

# pylint: disable=W0621
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.extraction import ExtractedEntities
from app.services.entity_extractor import EntityExtractor
from app.services.entity_extractor import entity_extractor as entity_extractor_module
from app.services.pseudonymizer import PATIENT_INFO_CATEGORY

# Located from the package rather than the working directory: these are the
# files that ship, wherever pytest was started from.
MAPPINGS = Path(entity_extractor_module.__file__).parent / "label_mappings"

# The label set of the CAS corpus of French clinical cases, which the shipped
# model is trained on. See the references in the root README.
CAS_LABELS = [
    "anatomie",
    "date",
    "dose",
    "duree",
    "examen",
    "frequence",
    "mode",
    "moment",
    "pathologie",
    "sosy",
    "substance",
    "traitement",
    "valeur",
]


@pytest.fixture
def mock_ner_pipeline():
    with patch(
        "app.services.entity_extractor.entity_extractor.pipeline"
    ) as mock_pipeline:
        yield mock_pipeline


def build_extractor(language: str) -> EntityExtractor:
    return EntityExtractor(
        model_name="Dummy/Model",
        label_mapping_file=str(MAPPINGS / f"{language}.json"),
        language=language,
    )


@pytest.mark.parametrize("language", ["fr", "es"])
def test_every_shipped_category_exists_on_the_response_model(
    mock_ner_pipeline, language
):
    # ExtractedEntities(**entities) ignores unknown keys, so a category name the
    # model does not have deletes those entities without an error anywhere.
    extractor = build_extractor(language)

    categories = set(extractor.get_available_categories())

    assert categories <= set(ExtractedEntities.model_fields)


@pytest.mark.parametrize("language", ["fr", "es"])
def test_the_masked_category_is_one_the_pseudonymizer_looks_for(
    mock_ner_pipeline, language
):
    extractor = build_extractor(language)

    assert PATIENT_INFO_CATEGORY in extractor.get_available_categories()


@pytest.mark.parametrize("label", CAS_LABELS)
def test_every_corpus_label_lands_in_a_real_category(mock_ner_pipeline, label):
    extractor = build_extractor("fr")

    assert extractor.categorize_entity(label) != "other"
    assert extractor.categorize_entity(f"B-{label.upper()}") != "other"


@pytest.mark.parametrize(
    "label, category",
    [
        # The corpus writes accents that a mapping file may not.
        ("âge", "patient_info"),
        ("durée", "temporal"),
        # MeSH disease families reach the model as compound names.
        ("maladies cardiovasculaires", "pathologies"),
        ("maladies_de_la_peau", "pathologies"),
        ("B-MALADIES-VIRALES", "pathologies"),
    ],
)
def test_a_label_written_differently_still_finds_its_category(
    mock_ner_pipeline, label, category
):
    extractor = build_extractor("fr")

    assert extractor.categorize_entity(label) == category


@pytest.mark.parametrize("label", ["dosage", "message", "genome", "ages"])
def test_a_word_merely_containing_a_label_is_not_that_category(
    mock_ner_pipeline, label
):
    # The old substring scan read "dosage" as a dose and, because "age" is a
    # patient_info label, "dosage" and "message" as patient information.
    extractor = build_extractor("fr")

    assert extractor.categorize_entity(label) == "other"


def test_labels_the_mapping_does_not_know_are_reported(mock_ner_pipeline, caplog):
    mock_ner_pipeline.return_value.model.config.id2label = {
        0: "O",
        1: "B-sosy",
        2: "B-inconnu",
    }

    extractor = build_extractor("fr")

    assert extractor.unmapped_model_labels() == ["B-inconnu"]
    assert "inconnu" in caplog.text
    # The warning names labels, which are model metadata, and nothing else.
    assert "sosy" not in caplog.text


def test_nothing_is_reported_when_the_model_declares_no_labels(
    mock_ner_pipeline, caplog
):
    # A pipeline without id2label must not break startup.
    mock_ner_pipeline.return_value.model.config = MagicMock(spec=[])

    extractor = build_extractor("fr")

    assert extractor.unmapped_model_labels() == []
    assert not caplog.text
