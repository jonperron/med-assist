"""
The summary is the product, so the rules that shape it are pinned here.

Every assertion is about what a clinician ends up reading: what is merged, what
is dropped, what order it arrives in, and what never appears at all.
"""

import pytest

from app.schemas.extraction import EntityDetail
from app.services.summarizer import (
    MIN_CONFIDENCE,
    comparison_key,
    summarize,
)


def entity(text, label="pathologie", score=0.9):
    return EntityDetail(text=text, label=label, score=score)


def document(**categories):
    return {category: list(details) for category, details in categories.items()}


def sections_of(summary):
    return {section.key: section for section in summary.sections}


def test_an_empty_input_is_flagged_rather_than_rendered():
    summary = summarize([])

    assert summary.empty is True
    assert summary.sections == []
    assert summary.patient is None
    assert summary.document_count == 0


def test_a_document_with_no_findings_is_flagged_empty():
    summary = summarize([document(temporal=[entity("hier", label="moment")])])

    # `temporal` is deliberately not a section, so this document says nothing.
    assert summary.empty is True
    assert summary.document_count == 1


@pytest.mark.parametrize(
    ("finding", "expected"),
    [
        ("cirrhose", "Cirrhose."),
        ("pH bas", "pH bas."),
        ("mmHg", "mmHg."),
        ("pCO2 abaissé", "pCO2 abaissé."),
    ],
)
def test_a_case_bearing_clinical_token_is_not_flattened(finding, expected):
    # Upper-casing the first letter of pH or mmHg makes it a different token.
    summary = summarize([document(pathologies=[entity(finding)])])

    assert sections_of(summary)["pathologies"].sentence == expected


def test_findings_become_a_readable_sentence():
    summary = summarize([document(pathologies=[entity("cirrhose")])])

    assert sections_of(summary)["pathologies"].sentence == "Cirrhose."


def test_the_sentence_and_the_list_carry_the_same_findings():
    summary = summarize([document(pathologies=[entity("cirrhose"), entity("diabète")])])

    section = sections_of(summary)["pathologies"]
    assert section.findings == ["cirrhose", "diabète"]
    assert section.sentence == "Cirrhose, diabète."


class TestDeduplication:
    def test_the_same_finding_in_two_documents_is_reported_once(self):
        summary = summarize(
            [
                document(pathologies=[entity("cirrhose")]),
                document(pathologies=[entity("cirrhose")]),
            ]
        )

        assert sections_of(summary)["pathologies"].findings == ["cirrhose"]

    @pytest.mark.parametrize(
        "variant",
        ["Cirrhose", "CIRRHOSE", "cirrhose.", " cirrhose ", "cirrhose,"],
    )
    def test_case_spacing_and_edge_punctuation_do_not_split_a_finding(self, variant):
        summary = summarize(
            [document(pathologies=[entity("cirrhose"), entity(variant)])]
        )

        assert len(sections_of(summary)["pathologies"].findings) == 1

    def test_accents_do_not_split_a_finding(self):
        summary = summarize(
            [document(pathologies=[entity("diabète"), entity("diabete")])]
        )

        assert len(sections_of(summary)["pathologies"].findings) == 1

    def test_the_first_surface_form_seen_is_the_one_reported(self):
        summary = summarize(
            [
                document(pathologies=[entity("Cirrhose")]),
                document(pathologies=[entity("cirrhose")]),
            ]
        )

        assert sections_of(summary)["pathologies"].findings == ["Cirrhose"]


class TestOrdering:
    def test_a_finding_in_more_documents_comes_first(self):
        summary = summarize(
            [
                document(pathologies=[entity("rare"), entity("commune")]),
                document(pathologies=[entity("commune")]),
                document(pathologies=[entity("commune")]),
            ]
        )

        assert sections_of(summary)["pathologies"].findings[0] == "commune"

    def test_sections_follow_the_reading_order_not_the_input_order(self):
        summary = summarize(
            [
                document(
                    anatomy=[entity("foie", label="anatomie")],
                    treatments=[entity("insuline", label="traitement")],
                    pathologies=[entity("cirrhose")],
                    symptoms=[entity("ictère", label="sosy")],
                    examinations=[entity("TDM", label="examen")],
                )
            ]
        )

        assert [section.key for section in summary.sections] == [
            "pathologies",
            "symptoms",
            "examinations",
            "treatments",
            "anatomy",
        ]

    def test_an_empty_section_is_omitted(self):
        summary = summarize([document(pathologies=[entity("cirrhose")])])

        assert list(sections_of(summary)) == ["pathologies"]


class TestNoise:
    def test_a_low_confidence_span_is_dropped(self):
        summary = summarize(
            [
                document(
                    pathologies=[
                        entity("cirrhose", score=0.9),
                        entity("hasard", score=MIN_CONFIDENCE - 0.01),
                    ]
                )
            ]
        )

        assert sections_of(summary)["pathologies"].findings == ["cirrhose"]

    @pytest.mark.parametrize("noise", ["a", ".", "  ", "12", "3,5", "-"])
    def test_a_span_that_is_not_a_term_is_dropped(self, noise):
        summary = summarize([document(pathologies=[entity("cirrhose"), entity(noise)])])

        assert sections_of(summary)["pathologies"].findings == ["cirrhose"]

    def test_temporal_and_loose_values_never_reach_the_summary(self):
        summary = summarize(
            [
                document(
                    pathologies=[entity("cirrhose")],
                    temporal=[entity("trois jours", label="duree")],
                    measurements=[entity("12 g/dL", label="valeur")],
                    other=[entity("chose", label="chimiques")],
                )
            ]
        )

        assert list(sections_of(summary)) == ["pathologies"]

    def test_no_percentage_or_score_appears_anywhere(self):
        summary = summarize([document(pathologies=[entity("cirrhose", score=0.873)])])

        rendered = summary.model_dump_json()
        assert "%" not in rendered
        assert "0.87" not in rendered
        assert "score" not in rendered


class TestDemographics:
    def test_age_and_sex_open_the_summary(self):
        summary = summarize(
            [
                document(
                    patient_info=[
                        entity("67 ans", label="age"),
                        entity("homme", label="genre"),
                    ]
                )
            ]
        )

        assert summary.patient == "Patient, 67 ans, homme."

    def test_the_order_is_fixed_regardless_of_the_order_found(self):
        summary = summarize(
            [
                document(
                    patient_info=[
                        entity("femme", label="genre"),
                        entity("52 ans", label="age"),
                    ]
                )
            ]
        )

        assert summary.patient == "Patient, 52 ans, femme."

    def test_a_later_age_does_not_overwrite_the_patient_s_own(self):
        # A clinical case routinely names a relative's age further down.
        summary = summarize(
            [
                document(patient_info=[entity("67 ans", label="age")]),
                document(patient_info=[entity("34 ans", label="age")]),
            ]
        )

        assert summary.patient == "Patient, 67 ans."

    def test_a_later_sex_does_not_overwrite_the_patient_s_own(self):
        summary = summarize(
            [
                document(patient_info=[entity("homme", label="genre")]),
                document(patient_info=[entity("femme", label="genre")]),
            ]
        )

        assert summary.patient == "Patient, homme."

    @pytest.mark.parametrize("label", ["homme", "femme"])
    def test_a_mesh_disease_axis_never_becomes_a_patient_attribute(self, label):
        # fr.json files the MeSH axes `homme` and `femme` under patient_info,
        # but those are male and female urogenital diseases. Reading them as
        # demographics would print a disease as the summary's opening line.
        summary = summarize(
            [document(patient_info=[entity("prostatite", label=label)])]
        )

        assert summary.patient is None

    def test_an_age_written_as_digits_alone_is_still_the_age(self):
        # The has-a-letter rule rejects loose numbers in a clinical section.
        # Applied here it would cost the summary its opening line, with no
        # section to fall back to.
        summary = summarize([document(patient_info=[entity("67", label="age")])])

        assert summary.patient == "Patient, 67."

    @pytest.mark.parametrize("label", ["âge", "AGE", "Âge"])
    def test_an_accented_or_upper_case_label_still_reaches_the_age_slot(self, label):
        # The extractor strips accents before categorising, so a span labelled
        # `âge` lands in patient_info; a raw == "age" here would miss it and
        # the age would vanish.
        summary = summarize([document(patient_info=[entity("67 ans", label=label)])])

        assert summary.patient == "Patient, 67 ans."

    def test_no_demographic_mention_means_no_opening_line(self):
        summary = summarize([document(pathologies=[entity("cirrhose")])])

        assert summary.patient is None
        assert summary.empty is False


def test_document_count_reports_what_was_read():
    summary = summarize([document(), document(), document()])

    assert summary.document_count == 3


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Cirrhose", "cirrhose"),
        ("diabète", "diabete"),
        ("insuffisance  rénale", "insuffisance rénale"),
        ("(tumeur)", "tumeur"),
    ],
)
def test_comparison_key_folds_what_should_not_split_a_finding(left, right):
    assert comparison_key(left) == comparison_key(right)
