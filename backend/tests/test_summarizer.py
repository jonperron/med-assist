"""
The summary is the product, so the rules that shape it are pinned here.

Every assertion is about what a clinician ends up reading: what is merged, what
is dropped, what order it arrives in, and what never appears at all.
"""

import pytest

from app.schemas.extraction import EntityDetail
from app.services.summarizer import (
    MEASUREMENT_GAP,
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


def findings_in(summary, key):
    """The spans of one section, without the provenance pinned separately."""
    return [finding.text for finding in sections_of(summary)[key].findings]


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
    assert [finding.text for finding in section.findings] == [
        "cirrhose",
        "diabète",
    ]
    assert section.sentence == "Cirrhose, diabète."


class TestDeduplication:
    def test_the_same_finding_in_two_documents_is_reported_once(self):
        summary = summarize(
            [
                document(pathologies=[entity("cirrhose")]),
                document(pathologies=[entity("cirrhose")]),
            ]
        )

        assert findings_in(summary, "pathologies") == ["cirrhose"]

    @pytest.mark.parametrize(
        "variant",
        ["Cirrhose", "CIRRHOSE", "cirrhose.", " cirrhose ", "cirrhose,"],
    )
    def test_case_spacing_and_edge_punctuation_do_not_split_a_finding(self, variant):
        summary = summarize(
            [document(pathologies=[entity("cirrhose"), entity(variant)])]
        )

        assert len(findings_in(summary, "pathologies")) == 1

    def test_accents_do_not_split_a_finding(self):
        summary = summarize(
            [document(pathologies=[entity("diabète"), entity("diabete")])]
        )

        assert len(findings_in(summary, "pathologies")) == 1

    def test_the_first_surface_form_seen_is_the_one_reported(self):
        summary = summarize(
            [
                document(pathologies=[entity("Cirrhose")]),
                document(pathologies=[entity("cirrhose")]),
            ]
        )

        assert findings_in(summary, "pathologies") == ["Cirrhose"]


class TestOrdering:
    def test_a_finding_in_more_documents_comes_first(self):
        summary = summarize(
            [
                document(pathologies=[entity("rare"), entity("commune")]),
                document(pathologies=[entity("commune")]),
                document(pathologies=[entity("commune")]),
            ]
        )

        assert findings_in(summary, "pathologies")[0] == "commune"

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

        assert findings_in(summary, "pathologies") == ["cirrhose"]

    @pytest.mark.parametrize("noise", ["a", ".", "  ", "12", "3,5", "-"])
    def test_a_span_that_is_not_a_term_is_dropped(self, noise):
        summary = summarize([document(pathologies=[entity("cirrhose"), entity(noise)])])

        assert findings_in(summary, "pathologies") == ["cirrhose"]

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


class TestProvenance:
    """
    A finding says which documents it came from.

    With a stack of documents about one patient, where a finding was written is
    a clinical fact rather than a mechanism: it separates something three
    letters agree on from something one of them says alone. The indices are the
    caller's own submission order, so naming the source costs no filename.
    """

    def test_a_finding_names_the_document_it_came_from(self):
        summary = summarize(
            [
                document(pathologies=[entity("cirrhose")]),
                document(pathologies=[entity("diabète")]),
            ]
        )

        provenance = {
            finding.text: finding.documents
            for finding in sections_of(summary)["pathologies"].findings
        }
        assert provenance == {"cirrhose": [0], "diabète": [1]}

    def test_a_finding_several_documents_agree_on_names_them_all(self):
        summary = summarize(
            [
                document(pathologies=[entity("cirrhose")]),
                document(pathologies=[entity("cirrhose")]),
            ]
        )

        assert sections_of(summary)["pathologies"].findings[0].documents == [0, 1]

    def test_the_indices_are_ascending_whatever_order_the_mentions_arrive_in(self):
        summary = summarize(
            [
                document(pathologies=[entity("cirrhose")]),
                document(),
                document(pathologies=[entity("cirrhose")]),
            ]
        )

        assert sections_of(summary)["pathologies"].findings[0].documents == [0, 2]

    def test_a_repeated_mention_in_one_document_names_it_once(self):
        summary = summarize(
            [document(pathologies=[entity("cirrhose"), entity("cirrhose")])]
        )

        assert sections_of(summary)["pathologies"].findings[0].documents == [0]


class TestUnreadDocuments:
    """
    A document that could not be read keeps its position and contributes nothing.

    Dropping it instead would renumber every document after it, and the numbers
    are what a caller resolves back to its own files.
    """

    def test_an_unread_document_does_not_shift_the_indices_after_it(self):
        summary = summarize([None, document(pathologies=[entity("cirrhose")])])

        assert sections_of(summary)["pathologies"].findings[0].documents == [1]

    def test_the_document_count_is_what_was_read_not_what_was_sent(self):
        summary = summarize([document(pathologies=[entity("cirrhose")]), None])

        assert summary.document_count == 1

    def test_a_summary_is_still_built_from_the_documents_that_read(self):
        summary = summarize([None, document(pathologies=[entity("cirrhose")]), None])

        assert summary.empty is False
        assert findings_in(summary, "pathologies") == ["cirrhose"]

    def test_nothing_read_at_all_is_an_empty_summary(self):
        summary = summarize([None, None])

        assert summary.empty is True
        assert summary.document_count == 0

    def test_an_unread_document_carries_no_demographic_line(self):
        summary = summarize([None])

        assert summary.patient is None


def examination(text, start, end, score=0.9):
    return EntityDetail(text=text, label="examen", score=score, start=start, end=end)


def measurement(text, start, end, score=0.9):
    return EntityDetail(text=text, label="valeur", score=score, start=start, end=end)


class TestMeasurementPairing:
    """
    A value reaches the summary only when it is attached to the test it belongs to.

    "Troponine I" with no result and "1,10 ng/mL" with no test are each worth
    less than the pair, which is why loose measurements are not a section of
    their own. The pairing is positional and deliberately short-sighted: past
    `MEASUREMENT_GAP` the next clause has begun and the pair would be a guess.
    """

    def test_a_value_beside_its_test_is_reported_with_it(self):
        # "Troponine I : 1,10 ng/mL"
        summary = summarize(
            [
                document(
                    examinations=[examination("Troponine I", 0, 11)],
                    measurements=[measurement("1,10 ng/mL", 14, 24)],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Troponine I 1,10 ng/mL"]

    def test_a_value_with_no_letters_is_still_a_value(self):
        # A blood pressure is digits and a slash, which the noise floor for a
        # clinical term would otherwise drop.
        summary = summarize(
            [
                document(
                    examinations=[examination("Tension artérielle", 0, 18)],
                    measurements=[measurement("148/92", 21, 27)],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Tension artérielle 148/92"]

    def test_a_value_further_off_than_the_gap_is_not_attached(self):
        summary = summarize(
            [
                document(
                    examinations=[examination("Troponine I", 0, 11)],
                    measurements=[measurement("1,10 ng/mL", 60, 70)],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Troponine I"]

    def test_a_value_starting_right_at_the_examination_s_end_is_attached(self):
        # Gap 0: the value starts exactly where the test name ends.
        summary = summarize(
            [
                document(
                    examinations=[examination("Troponine I", 0, 11)],
                    measurements=[measurement("1,10 ng/mL", 11, 21)],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Troponine I 1,10 ng/mL"]

    def test_a_value_exactly_at_the_gap_boundary_is_still_attached(self):
        summary = summarize(
            [
                document(
                    examinations=[examination("Troponine I", 0, 11)],
                    measurements=[
                        measurement(
                            "1,10 ng/mL", 11 + MEASUREMENT_GAP, 21 + MEASUREMENT_GAP
                        )
                    ],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Troponine I 1,10 ng/mL"]

    def test_a_value_one_character_past_the_gap_boundary_is_not_attached(self):
        summary = summarize(
            [
                document(
                    examinations=[examination("Troponine I", 0, 11)],
                    measurements=[
                        measurement(
                            "1,10 ng/mL",
                            11 + MEASUREMENT_GAP + 1,
                            21 + MEASUREMENT_GAP + 1,
                        )
                    ],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Troponine I"]

    def test_an_unattached_value_never_becomes_a_finding_of_its_own(self):
        summary = summarize(
            [document(measurements=[measurement("1,10 ng/mL", 60, 70)])]
        )

        assert summary.empty is True

    def test_a_value_is_claimed_by_one_test_only(self):
        summary = summarize(
            [
                document(
                    examinations=[
                        examination("Troponine I", 0, 11),
                        examination("Créatinine", 12, 22),
                    ],
                    measurements=[measurement("1,10 ng/mL", 24, 34)],
                )
            ]
        )

        assert findings_in(summary, "examinations") == [
            "Créatinine 1,10 ng/mL",
            "Troponine I",
        ]

    def test_a_value_before_its_test_is_not_attached_backwards(self):
        # Reading "1,10 ng/mL Troponine I" as a pair would also read the value
        # of the previous test as belonging to this one.
        summary = summarize(
            [
                document(
                    examinations=[examination("Troponine I", 11, 22)],
                    measurements=[measurement("1,10 ng/mL", 0, 10)],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Troponine I"]

    def test_spans_with_no_offsets_are_never_paired(self):
        # The shape stored entities have once the document text is gone: there
        # is nothing left to measure the distance in.
        summary = summarize(
            [
                document(
                    examinations=[entity("Troponine I", label="examen")],
                    measurements=[entity("1,10 ng/mL", label="valeur")],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Troponine I"]

    def test_the_same_pair_in_two_documents_is_reported_once(self):
        paired = dict(
            examinations=[examination("Troponine I", 0, 11)],
            measurements=[measurement("1,10 ng/mL", 14, 24)],
        )
        summary = summarize([document(**paired), document(**paired)])

        section = sections_of(summary)["examinations"]
        assert len(section.findings) == 1
        assert section.findings[0].documents == [0, 1]

    def test_the_test_name_is_tidied_before_the_value_is_joined_to_it(self):
        summary = summarize(
            [
                document(
                    examinations=[examination("Troponine I :", 0, 13)],
                    measurements=[measurement("1,10 ng/mL", 14, 24)],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Troponine I 1,10 ng/mL"]

    def test_a_low_confidence_value_is_not_attached(self):
        summary = summarize(
            [
                document(
                    examinations=[examination("Troponine I", 0, 11)],
                    measurements=[
                        measurement("1,10 ng/mL", 14, 24, score=MIN_CONFIDENCE - 0.01)
                    ],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Troponine I"]


class TestMeasurementPairingInteractsWithDeduplication:
    """
    Pairing happens per document, before findings are deduplicated across them.

    A finding's identity is the text it ends up displayed as, so two documents
    naming the same test only merge into one finding when the value joined to
    it - if any - reads the same in both. That is a consequence of where
    `pair_measurements` sits in `summarize`, not a rule of its own, and worth
    pinning so a reordering of the two steps is caught here rather than in a
    clinician's summary.
    """

    def test_the_same_test_with_a_different_value_in_each_document_is_not_merged(
        self,
    ):
        summary = summarize(
            [
                document(
                    examinations=[examination("Troponine I", 0, 11)],
                    measurements=[measurement("1,10 ng/mL", 14, 24)],
                ),
                document(
                    examinations=[examination("Troponine I", 0, 11)],
                    measurements=[measurement("2,00 ng/mL", 14, 24)],
                ),
            ]
        )

        provenance = {
            finding.text: finding.documents
            for finding in sections_of(summary)["examinations"].findings
        }
        assert provenance == {
            "Troponine I 1,10 ng/mL": [0],
            "Troponine I 2,00 ng/mL": [1],
        }

    def test_a_paired_mention_does_not_merge_with_the_same_test_left_bare_elsewhere(
        self,
    ):
        summary = summarize(
            [
                # No measurement in this document: the test stands alone.
                document(examinations=[examination("Troponine I", 0, 11)]),
                document(
                    examinations=[examination("Troponine I", 0, 11)],
                    measurements=[measurement("1,10 ng/mL", 14, 24)],
                ),
            ]
        )

        provenance = {
            finding.text: finding.documents
            for finding in sections_of(summary)["examinations"].findings
        }
        assert provenance == {
            "Troponine I": [0],
            "Troponine I 1,10 ng/mL": [1],
        }

    def test_a_pair_two_documents_agree_on_still_outranks_a_pair_named_once(self):
        agreed = dict(
            examinations=[examination("Troponine I", 0, 11)],
            measurements=[measurement("1,10 ng/mL", 14, 24)],
        )
        summary = summarize(
            [
                document(**agreed),
                document(**agreed),
                document(
                    examinations=[examination("Créatinine", 0, 10)],
                    measurements=[measurement("90 µmol/L", 12, 21)],
                ),
            ]
        )

        assert findings_in(summary, "examinations") == [
            "Troponine I 1,10 ng/mL",
            "Créatinine 90 µmol/L",
        ]


class TestPairingClaimsTheRightTest:
    """
    When two tests are in reach of one value, the nearer one takes it.

    Served the other way round, "Troponine, BNP : 900 pg/mL" reports the BNP
    result against the troponine - a confidently worded, clinically wrong
    sentence, which is worse than the dropped value the gap rule exists to
    avoid in the first place.
    """

    def test_the_nearest_preceding_test_claims_the_value(self):
        # "Troponine, BNP : 900 pg/mL" - both ends are inside the gap.
        summary = summarize(
            [
                document(
                    examinations=[
                        examination("Troponine", 0, 9),
                        examination("BNP", 11, 14),
                    ],
                    measurements=[measurement("900 pg/mL", 17, 26)],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["BNP 900 pg/mL", "Troponine"]

    def test_each_test_still_keeps_its_own_value(self):
        # "TA 148/92 mmHg, FC 92/min" - two tests, two values, no crossing.
        summary = summarize(
            [
                document(
                    examinations=[
                        examination("TA", 0, 2),
                        examination("FC", 18, 20),
                    ],
                    measurements=[
                        measurement("148/92 mmHg", 3, 14),
                        measurement("92/min", 21, 27),
                    ],
                )
            ]
        )

        assert sorted(findings_in(summary, "examinations")) == [
            "FC 92/min",
            "TA 148/92 mmHg",
        ]


class TestOnlyResultsArePaired:
    """
    `measurements` also holds `poids` and `taille`, which are not test results.

    A weight beside an examination name is a coincidence, not its outcome - and
    weight and height are quasi-identifiers, which do not belong on the one page
    a clinician exports beside an age and a sex. Everything else in the category
    is pairable, so a mapping naming neither attribute keeps working.
    """

    @pytest.mark.parametrize("label", ["poids", "taille"])
    def test_a_patient_attribute_is_not_attached_to_a_test(self, label):
        summary = summarize(
            [
                document(
                    examinations=[examination("Consultation", 0, 12)],
                    measurements=[
                        EntityDetail(
                            text="72 kg", label=label, score=0.9, start=14, end=19
                        )
                    ],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Consultation"]

    @pytest.mark.parametrize("label", ["valeur", "valor", "medida"])
    def test_a_result_label_from_any_shipped_mapping_is_paired(self, label):
        # `fr.json` names the result `valeur`; `es.json` names it `valor` or
        # `medida`. A rule that recognised only the French one would drop every
        # value from every summary under the Spanish mapping, silently.
        summary = summarize(
            [
                document(
                    examinations=[examination("Troponine I", 0, 11)],
                    measurements=[
                        EntityDetail(
                            text="1,10 ng/mL", label=label, score=0.9, start=14, end=24
                        )
                    ],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Troponine I 1,10 ng/mL"]

    def test_the_excluded_label_is_matched_past_its_case(self):
        # The label is folded before it is compared, as the demographic labels
        # are: an exclusion that a capital defeats excludes nothing.
        summary = summarize(
            [
                document(
                    examinations=[examination("Consultation", 0, 12)],
                    measurements=[
                        EntityDetail(
                            text="72 kg", label="Poids", score=0.9, start=14, end=19
                        )
                    ],
                )
            ]
        )

        assert findings_in(summary, "examinations") == ["Consultation"]
