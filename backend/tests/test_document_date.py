"""
A date placed on a clinical summary is read as a fact, so the rules are pinned here.

Every assertion is about one of two things: the date a document really carries,
and the far larger set of dates that must not be mistaken for it. The second is
the point of the module - a document with no date answers `None`, and so does a
document whose head only holds dates that belong to something else.
"""

from datetime import date

import pytest

from app.services.document_date import (
    BIRTH_CONTEXT,
    EARLIEST_YEAR,
    HEAD_CHARACTERS,
    find_document_date,
    span_of,
)

# Fixed so that "in the future" means the same thing whenever these run.
TODAY = date(2026, 8, 27)


def dated(text):
    return find_document_date(text, today=TODAY)


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        ("Le 4 mars 2024\nCompte rendu", date(2024, 3, 4)),
        ("Le 1er mars 2024\nCompte rendu", date(2024, 3, 1)),
        ("Fait le 12 décembre 2023.", date(2023, 12, 12)),
        ("Date : 04/03/2024", date(2024, 3, 4)),
        ("Date : 4-3-2024", date(2024, 3, 4)),
        ("Date : 04.03.2024", date(2024, 3, 4)),
        ("Date : 13/04/2024", date(2024, 4, 13)),
        ("Date: 2024-03-04", date(2024, 3, 4)),
        ("LE 4 MARS 2024", date(2024, 3, 4)),
        ("Le 4 Août 2024", date(2024, 8, 4)),
    ],
)
def test_a_date_in_the_head_is_the_document_date(head, expected):
    assert dated(head) == expected


def test_a_numeric_date_is_read_day_first():
    # The convention the documents are written in. Read the other way round,
    # this would be 3 April.
    assert dated("Date : 04/03/2024") == date(2024, 3, 4)


@pytest.mark.parametrize(
    "head",
    [
        "Compte rendu de consultation",
        "Le patient de 67 ans",
        "Consultation du 4 mars",
        "Exercice 2024",
        "Le 4 mars 24",
        "Le 31 février 2024",
        "Le 04/13/2024",
        "Le 32/03/2024",
        "Réf. 2024-99-01",
        "Réf. 2024-02-30",  # a calendar date ISO could not resolve either
        "Le 00/03/2024",  # day zero
        "Le 04/00/2024",  # month zero
    ],
)
def test_what_is_not_a_complete_date_is_no_date_at_all(head):
    assert dated(head) is None


def test_a_date_in_the_body_does_not_date_the_document():
    body = "x" * HEAD_CHARACTERS + " Antécédent d'infarctus le 4 mars 2019."

    assert dated(body) is None


def test_a_date_straddling_the_head_boundary_is_not_found():
    # The head is a hard character cut, not a word boundary: a date whose
    # first character falls inside it but whose last one does not is truncated
    # mid-pattern, and a truncated pattern matches nothing rather than
    # something read halfway.
    head = "x" * (HEAD_CHARACTERS - 6) + " 04/03/2024 suite du compte rendu"

    assert dated(head) is None


def test_the_first_complete_date_in_the_head_wins():
    head = "Hospitalisation du 2 mars 2024 au 5 mars 2024"

    assert dated(head) == date(2024, 3, 2)


def test_a_range_written_the_elided_way_is_read_at_its_closing_date():
    # "du 2 au 5 mars" holds one complete date, its last: the bare 2 has no
    # month of its own, and inferring one from the number after it is the kind
    # of guess this module refuses. The document is placed at the end of the
    # stay it reports rather than at the start.
    head = "Hospitalisation du 2 au 5 mars 2024"

    assert dated(head) == date(2024, 3, 5)


def test_the_first_date_wins_regardless_of_which_format_it_is_written_in():
    # The textual date is written first but read by the last regex tried; the
    # ordering has to come from where each candidate sits in the text, not
    # from the order the readers are tried in.
    head = "Le 4 mars 2024, référence de suivi 2024-01-09."

    assert dated(head) == date(2024, 3, 4)


@pytest.mark.parametrize(
    "head",
    [
        "Née le 12/05/1948\nConsultation",
        "Ne le 12/05/1948\nConsultation",
        "Date de naissance : 12/05/1948",
        "DDN 12/05/1948",
        # A padded table row, which is how a header arrives out of a PDF.
        "Date de naissance" + " " * 30 + "12/05/1948",
        # A two-column row whose label and value land on separate lines, which
        # is the same header out of a different extractor.
        "Date de naissance\n12/05/1948",
        # The same label tab-separated, and abbreviated with stops.
        "Date\tde\tnaissance\t12/05/1948",
        "D.D.N. 12/05/1948",
        "Née  le  12/05/1948",
    ],
)
def test_a_date_of_birth_is_never_the_document_date(head):
    # Twice wrong: it would date the document decades early, and it would
    # publish a patient identifier as document metadata.
    assert dated(head) is None


@pytest.mark.parametrize(
    "head",
    [
        "Née le 12/05/1948. Consultation du 4 mars 2024.",
        "Née le 12/05/1948\nConsultation du 4 mars 2024",
        "Date de naissance\n12/05/1948\nConsultation du 4 mars 2024",
    ],
)
def test_a_date_of_birth_does_not_hide_the_date_that_follows_it(head):
    # The marker introduced the date next to it, and says nothing about the one
    # on the far side of that date - whatever separates the two.
    assert dated(head) == date(2024, 3, 4)


def test_a_marker_inside_another_word_is_not_a_birth_marker():
    # "personne les" holds "ne le", and introduces nothing.
    head = "Le médecin informe personne les 4 mars 2024"

    assert dated(head) == date(2024, 3, 4)


def test_a_birth_marker_further_back_than_the_context_window_no_longer_applies():
    # BIRTH_CONTEXT is a fixed lookback, not a lookback to the last marker seen
    # anywhere earlier in the sentence. A marker further back than that window
    # no longer reaches the date - the date is then read as the document's own,
    # which is the accepted trade-off the module's docstring names rather than
    # an oversight.
    head = "Naissance " + "x" * (BIRTH_CONTEXT + 5) + " 12/05/1948"

    assert dated(head) == date(1948, 5, 12)


def test_a_birth_marker_that_follows_the_date_does_not_hide_it():
    # The lookback only ever looks backward. A birth date written before its
    # own marker - "12/05/1948, date de naissance" - is read as the document's
    # date rather than skipped, since nothing about the date it already
    # matched is re-examined once a marker turns up after it.
    head = "12/05/1948, date de naissance."

    assert dated(head) == date(1948, 5, 12)


def test_a_date_in_the_future_is_not_a_document_date():
    assert dated("Le 4 mars 2027") is None


def test_a_date_today_is_a_document_date():
    assert dated("Le 27 août 2026") == TODAY


def test_a_date_before_the_earliest_plausible_year_is_refused():
    assert dated(f"Le 4 mars {EARLIEST_YEAR - 1}") is None


def test_an_empty_document_carries_no_date():
    assert dated("") is None


def test_the_real_today_is_used_when_none_is_given():
    # The default has to be the day the request is served, not a fixed one.
    assert find_document_date("Le 1er janvier 2020") == date(2020, 1, 1)


class TestTheSpanAcrossABatch:
    def test_an_undated_batch_has_no_span(self):
        assert span_of([None, None]) is None

    def test_an_empty_batch_has_no_span(self):
        assert span_of([]) is None

    def test_one_dated_document_spans_its_own_day(self):
        assert span_of([None, date(2024, 3, 4)]) == (date(2024, 3, 4), date(2024, 3, 4))

    def test_the_span_runs_from_the_earliest_to_the_latest(self):
        dates = [date(2024, 4, 2), None, date(2024, 3, 4), date(2024, 3, 20)]

        assert span_of(dates) == (date(2024, 3, 4), date(2024, 4, 2))
