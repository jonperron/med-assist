"""
Turn categorised NER output into a summary a clinician can read.

Nothing here generates language. Every word in the result is either a fixed
heading or a span the model marked in the submitted documents, so the summary
cannot say anything the documents did not.
"""

import re
import unicodedata
from datetime import date
from typing import Dict, List, Optional, Sequence, Set, Tuple

from app.schemas.extraction import EntityDetail
from app.schemas.summary import ClinicalSummary, DateRange, Finding, SummarySection
from app.services.document_date import span_of

# One document's categorised entities, or None when the document could not be
# read. The position is kept either way: a finding names the documents it came
# from by index, and those indices are the caller's own submission order.
Document = Optional[Dict[str, List[EntityDetail]]]

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
# entity payload for callers that want them. A measurement does reach the
# summary when `pair_measurements` can attach it to the examination it sits
# beside, which is the context its exclusion was about.
SECTION_ORDER: Tuple[Tuple[str, str], ...] = (
    ("pathologies", "Pathologies"),
    ("symptoms", "Signes et symptômes"),
    ("examinations", "Examens"),
    ("treatments", "Traitements"),
    ("anatomy", "Localisations"),
)

# The two categories `pair_measurements` joins. A value only reaches the summary
# through this pairing, so both are named rather than inlined.
EXAMINATION_CATEGORY = "examinations"
MEASUREMENT_CATEGORY = "measurements"

# Measurement labels that are patient attributes rather than the outcome of an
# investigation, and so are never paired: a weight that happens to sit near an
# examination name is a wrong pairing, and putting either into the summary would
# add a quasi-identifier to the one page a clinician exports.
#
# Stated as what to exclude rather than as the one label to include, because the
# two fail in opposite directions across mappings. `fr.json` files `valeur`,
# `poids` and `taille` here; `es.json` files `valor` and `medida`, which are both
# results. An allow-list naming the French label would silently pair nothing at
# all under the Spanish mapping - every value gone from every summary, with
# nothing in the response to say so. Excluding the attributes leaves a mapping
# that names none of them fully working.
#
# Compared through `comparison_key`, like the demographic labels, since the
# extractor strips accents before categorising.
ATTRIBUTE_LABELS = frozenset({"poids", "taille"})

# How far after an examination span its value may start, in characters. A value
# that belongs to a test sits right against its name - "Troponine I : 1,10
# ng/mL", "TA 148/92 mmHg" - with only punctuation and a space or two between.
# Past that the next clause has begun, and the pairing would be a guess about
# which number belongs to which test. That guess is the reason loose
# measurements are kept out of the summary; making it here would only move it.
MEASUREMENT_GAP = 12

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


def tidy(text: str) -> str:
    """Trim a span to the form it is reported in: no edge punctuation, one space."""
    return WHITESPACE.sub(" ", text.strip(EDGE_PUNCTUATION))


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


class FindingSupport:
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

    def as_finding(self) -> Finding:
        """The reportable form: the span, and where it was found."""
        return Finding(text=self.display, documents=sorted(self.documents))


def collect_findings(documents: Sequence[Document], category: str) -> List[Finding]:
    """Deduplicate one category across every document, most-supported first."""
    findings: Dict[str, FindingSupport] = {}

    for document_index, entities in enumerate(documents):
        if entities is None:
            continue

        for entity in entities.get(category, []):
            if not is_worth_reporting(entity):
                continue

            display = tidy(entity.text)
            key = comparison_key(display)
            if not key:
                continue

            existing = findings.get(key)
            if existing is None:
                findings[key] = FindingSupport(display, document_index)
            else:
                existing.add(document_index)

    ranked = sorted(findings.values(), key=FindingSupport.rank)
    return [support.as_finding() for support in ranked]


def pair_measurements(
    entities: Dict[str, List[EntityDetail]],
) -> Dict[str, List[EntityDetail]]:
    """
    Rewrite each examination that has a value beside it to carry both.

    "Troponine I" and "1,10 ng/mL" are two spans in two categories, and either
    one alone is worth less to a clinician than the pair: a test with no result,
    or a number with no test. Joining them is the only way a measurement reaches
    the summary - an unclaimed value stays out, for the reason `SECTION_ORDER`
    gives.

    The pairing is positional, not semantic. A value is attached only when it
    starts within `MEASUREMENT_GAP` characters after the end of an examination
    span, and only the test nearest before it can claim it, so one value is
    never reported against two tests. A span with no offsets - the shape stored
    entities have once the text is gone - is never paired, since there is
    nothing to measure the distance in.

    It also inherits the extractor's per-document deduplication, which keeps the
    first occurrence of a repeated span and its offsets. A test named once in
    prose and again beside its result is therefore held at the first position,
    and the value goes unclaimed rather than being attached to the wrong test.

    :param entities: One document's categorised entities.
    :return: The same mapping, with paired examinations carrying their value.
        The input is not modified.
    """
    examinations = entities.get(EXAMINATION_CATEGORY, [])
    measurements = entities.get(MEASUREMENT_CATEGORY, [])
    if not examinations or not measurements:
        return entities

    # Values are read in text order so that "nearest" can stop looking early.
    # `require_letter` is off: "148/92" is a blood pressure, not noise.
    available = sorted(
        (
            measurement
            for measurement in measurements
            if measurement.start is not None
            and comparison_key(measurement.label) not in ATTRIBUTE_LABELS
            and is_worth_reporting(measurement, require_letter=False)
        ),
        key=lambda measurement: measurement.start or 0,
    )
    if not available:
        return entities

    pairable = [
        index
        for index, examination in enumerate(examinations)
        if examination.end is not None and is_worth_reporting(examination)
    ]
    claimed: Set[int] = set()
    values: Dict[int, str] = {}

    # Latest-ending test first, so that in "Troponine, BNP : 900 pg/mL" the value
    # goes to BNP. Served the other way round, Troponine is inside the gap too
    # and claims it first, and the summary then states a result against a test
    # that did not produce it - a confident, wrong sentence, which is worse than
    # the dropped value the whole gap rule exists to avoid.
    #
    # This is the better default, not a rule that settles the construction. A
    # document enumerating its tests before the value - "TA et FC : 148/92 mmHg"
    # - reads the same way and means the opposite, and no ordering answers both.
    # `Test : valeur` is the dominant layout, and nearest-preceding matches it.
    for index in sorted(
        pairable, key=lambda position: examinations[position].end or 0, reverse=True
    ):
        end = examinations[index].end or 0
        for position, measurement in enumerate(available):
            gap = (measurement.start or 0) - end
            if gap < 0:
                continue
            if gap > MEASUREMENT_GAP:
                break
            if position in claimed:
                continue
            claimed.add(position)
            values[index] = tidy(measurement.text)
            break

    if not values:
        return entities

    paired = dict(entities)
    paired[EXAMINATION_CATEGORY] = [
        (
            examination.model_copy(
                update={"text": f"{tidy(examination.text)} {values[index]}"}
            )
            if index in values
            else examination
        )
        for index, examination in enumerate(examinations)
    ]
    return paired


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


def demographic_line(documents: Sequence[Document]) -> Optional[str]:
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
        if entities is None:
            continue

        for entity in entities.get(PATIENT_INFO_CATEGORY, []):
            if not is_worth_reporting(entity, require_letter=False):
                continue

            value = tidy(entity.text)
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


def summarize(
    documents: Sequence[Document],
    dates: Optional[Sequence[Optional[date]]] = None,
) -> ClinicalSummary:
    """
    Assemble the summary of one or more documents about the same patient.

    :param documents: Categorised entities, one entry per submitted document in
        submission order, with `None` where a document could not be read. The
        unread entry is kept rather than dropped so that the indices a finding
        reports stay the caller's own file order.
    :param dates: The date each of those documents carries, in the same order,
        with `None` where it carries none. Only the range across them reaches
        the summary; each document reports its own date beside its entities.
        Omitted by a caller that holds entities and no text to date them from,
        which reads the same way as a batch where nothing was dated.
    :return: The summary, flagged empty when nothing clinical was found.
    :raises ValueError: If `dates` is given and does not line up with
        `documents`. The two are positional, and a shifted list would put a
        plausible range on the summary with nothing to say it is wrong.
    """
    if dates is not None and len(dates) != len(documents):
        raise ValueError("A date per document is required")

    prepared = [
        pair_measurements(entities) if entities is not None else None
        for entities in documents
    ]

    sections = []
    for key, heading in SECTION_ORDER:
        findings = collect_findings(prepared, key)
        if not findings:
            continue

        sections.append(
            SummarySection(
                key=key,
                heading=heading,
                sentence=as_sentence([finding.text for finding in findings]),
                findings=findings,
            )
        )

    patient = demographic_line(prepared)
    span = span_of(dates or [])

    return ClinicalSummary(
        patient=patient,
        sections=sections,
        date_range=DateRange(start=span[0], end=span[1]) if span else None,
        document_count=sum(1 for entities in documents if entities is not None),
        empty=not sections and patient is None,
    )
