# pylint: disable=W0621
import pytest

from app.services.identifier_detector import DirectIdentifierDetector


@pytest.fixture
def detector():
    return DirectIdentifierDetector()


def labels_in(detector, text):
    return {item.label for item in detector.detect(text)}


def masked_surfaces(detector, text):
    return {text[item.start : item.end] for item in detector.detect(text)}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("M. Dupont présente une fièvre.", "Dupont"),
        ("Mme Jeanne Dupont, 42 ans.", "Jeanne Dupont"),
        ("Patient : Jean Martin", "Jean Martin"),
        ("Nom: Durand", "Durand"),
        ("Vu par le Dr Lefevre.", "Lefevre"),
    ],
)
def test_detects_names_behind_a_civility_or_a_field_label(detector, text, expected):
    assert expected in masked_surfaces(detector, text)


def test_the_civility_itself_is_not_part_of_the_span(detector):
    # Masking "M." too would make the sentence unreadable for no privacy gain.
    assert "M. Dupont" not in masked_surfaces(detector, "M. Dupont a de la fièvre.")


def test_detects_a_social_security_number(detector):
    text = "NIR 1 84 12 75 116 001 42 au dossier."
    assert "nir" in labels_in(detector, text)


def test_detects_contact_details(detector):
    text = "Joignable au 06 12 34 56 78 ou jean.martin@example.org"
    assert labels_in(detector, text) >= {"telephone", "email"}


@pytest.mark.parametrize(
    "text", ["Né le 12/03/1981.", "Admis le 3 février 2024.", "Le 01.09.2023"]
)
def test_detects_dates(detector, text):
    assert "date" in labels_in(detector, text)


def test_detects_a_record_number(detector):
    assert "dossier" in labels_in(detector, "IPP : A12345678")


def test_detects_a_postal_code_followed_by_a_town(detector):
    assert "35000 " in " ".join(masked_surfaces(detector, "35000 Rennes")) + " "


def test_leaves_a_bare_five_digit_value_alone(detector):
    # A clinical value is not an address.
    assert not detector.detect("Plaquettes 35000 par mm3")


def test_leaves_clinical_prose_alone(detector):
    text = "Le patient présente une fièvre à 39 degrés, traitée par paracétamol."
    assert detector.detect(text) == []


def test_overlapping_matches_keep_the_longest(detector):
    # The date-like run inside a NIR must not split the number.
    found = detector.detect("1 84 12 75 116 001 42")
    assert len(found) == 1
    assert found[0].label == "nir"


def test_results_do_not_overlap(detector):
    text = "Mme Jeanne Dupont, née le 12/03/1981, 06 12 34 56 78, 35000 Rennes"
    found = detector.detect(text)
    for earlier, later in zip(found, found[1:]):
        assert earlier.end <= later.start or later.end <= earlier.start
