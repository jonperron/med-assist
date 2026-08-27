"""
Decide the date a document carries, and the span a batch of them covers.

A date is what a clinician places a document by: a letter written last week and
a letter written in 2019 mean different things, and a stack of documents about
one patient is read along the time it covers. Nothing in the entity payload
answers this. `ExtractedEntities.temporal` is every date-like span found
anywhere in the text, mixed with durations and relative moments, and the file's
own `lastModified` dates a 2019 letter to the day it was downloaded.

Picking the document's own date out of the text is a judgement, and a wrong
date on a clinical summary is worse than no date at all: it silently moves a
document on the timeline the clinician is reading. So the rules here are narrow
on purpose, and every one of them is a reason to answer `None` rather than to
guess:

- Only the head of the document is read. A letter is dated in its letterhead;
  a date deep in the body belongs to something the document reports, not to the
  document.
- Only a complete calendar date counts. A bare year, a month with no year, and
  "il y a trois jours" are all things this function does not resolve.
- The first complete date in the head wins. In "Le 4 mars 2024" it is the only
  one; in "Hospitalisation du 2 mars 2024 au 5 mars 2024" it is the start of
  what the document reports, which is where the document sits on a timeline.
  A range written in the elided form - "du 2 au 5 mars 2024" - holds only one
  complete date, its last, so such a document is placed at the end of the stay
  it reports rather than at the start. Reading the elided form would mean
  inferring a month for a bare number from the number after it, which is the
  kind of inference the rest of this module refuses.
- A date a birth marker points at is skipped rather than taken. A header
  carrying "Née le 12/05/1948" would otherwise date the document to 1948 - and
  a date of birth is a patient identifier, which is not something to surface as
  document metadata. The marker is only looked for before the date, and never
  past the previous date in the text: a date of birth written ahead of its own
  label, "12/05/1948, date de naissance", is therefore not caught. Looking
  after the date as well would cost the common one-line header its real date,
  since a marker anywhere later on the line would suppress it. The guard names
  the markers it knows, so a birth date introduced by wording it does not know
  is published as the document date - the accepted cost of dating documents
  whose letterhead carries a bare date with no wording at all.
- A date in the future, or older than `EARLIEST_YEAR`, is not a date this
  system will legitimately see and is skipped.

The result is a `datetime.date` or nothing. No span from the document is
returned: the caller renders a date in its own locale, and the summary stays
made of headings and marked spans.
"""

import re
import unicodedata
from datetime import date
from typing import Iterator, List, Optional, Sequence, Tuple

# How far into the document a date may sit and still be taken as the document's
# own. Wide enough for a letterhead, an address block and a subject line; short
# enough that the first line of the clinical narrative is already out of reach.
HEAD_CHARACTERS = 500

# The oldest year a document can plausibly be dated to here. Below this a
# four-digit number that parses as a date is a reference number, a dosage or a
# typo far more often than it is the date of the document in hand.
EARLIEST_YEAR = 1900

# What turns a nearby date into somebody's date of birth. Matched against the
# folded, whitespace-collapsed, dot-stripped text before it, so "Née le",
# "NEE  LE", "Date\tde\tnaissance" and "D.D.N." all read the same. On word
# boundaries, so the "ne le" inside "personne les" is not one.
BIRTH_MARKER = re.compile(r"\b(?:naissance|nee? le|ne\(e\) le|ddn)\b")

# How far back from a date a birth marker is looked for. Wide enough for the
# label and its value to sit at opposite ends of a padded table row, or on two
# lines of a two-column layout - both are how a header arrives out of a PDF -
# and bounded so that a marker several clauses back does not reach a date it
# has nothing to do with.
BIRTH_CONTEXT = 120

# Nothing else stops that backward look, and in particular a line break does
# not: the label of a two-column row lands on the line above its value often
# enough that cutting there would leave the commonest table layout unguarded.
# What does stop it is the previous date in the text, in `find_document_date`.
# In "Née le 12/05/1948\nConsultation du 4 mars 2024" the marker introduced the
# first date, not the second, and the second is still the document's own.

# French month names, folded. The deployment reads French clinical documents,
# which is also why a numeric date is read day-first below.
MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}

# 04/03/2024, 4-3-2024, 04.03.2024. The year is required in full: a two-digit
# year cannot be told from a day, and guessing the century is exactly the kind
# of quiet error this module exists to avoid.
NUMERIC_DATE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")

# 2024-03-04. Machine-written, and unambiguous wherever it appears.
ISO_DATE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")

# 4 mars 2024, 1er mars 2024. The month is matched as a word and looked up, so
# an unknown word simply yields no candidate.
TEXTUAL_DATE = re.compile(r"\b(\d{1,2})(?:er)?\s+([^\W\d_]+)\s+(\d{4})\b")

# Runs of spaces, tabs and newlines, collapsed before a marker is looked for:
# a PDF puts any of them between a label and its value.
WHITESPACE = re.compile(r"\s+")


def fold(text: str) -> str:
    """
    Lower-case and strip accents, for looking a word up rather than comparing spans.

    Deliberately local and deliberately smaller than `summarizer.comparison_key`:
    that one decides whether two clinical mentions are the same finding, this one
    only has to make "Décembre" and "decembre" the same dictionary key.
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )


def on_calendar(year: int, month: int, day: int) -> Optional[date]:
    """The date, or nothing when those numbers are not one - 31 February included."""
    try:
        return date(year, month, day)
    except ValueError:
        return None


def read_numeric(match: "re.Match[str]") -> Optional[date]:
    """
    Read a numeric date day-first, the way the documents this system reads write it.

    Day-first is the convention wherever the deployment runs, so "04/03/2024" is
    4 March, and "13/04/2024" says the same thing more loudly. The reversed
    arrangement - "03/13/2024", month-first with a day above twelve - is
    refused rather than swapped: reading it as written would need the reader to
    switch conventions mid-document, and a date silently swapped between the
    fourth of March and the third of April is exactly the wrong answer this
    module would rather not give.
    """
    day, month, year = (int(group) for group in match.groups())
    if month > 12:
        return None
    return on_calendar(year, month, day)


def read_iso(match: "re.Match[str]") -> Optional[date]:
    """Read an ISO date, where nothing is ambiguous."""
    year, month, day = (int(group) for group in match.groups())
    return on_calendar(year, month, day)


def read_textual(match: "re.Match[str]") -> Optional[date]:
    """Read a date whose month is spelled out, or nothing when the word is not a month."""
    day, month_word, year = match.groups()
    month = MONTHS.get(fold(month_word))
    if month is None:
        return None
    return on_calendar(int(year), month, int(day))


def candidates(head: str) -> Iterator[Tuple[int, int, date]]:
    """
    Every complete date written in the head, in the order it is written.

    Each is reported with where it starts and where it ends: the start decides
    which one wins, and the end bounds how far back the next one may look for
    what introduced it.
    """
    readers = (
        (NUMERIC_DATE, read_numeric),
        (ISO_DATE, read_iso),
        (TEXTUAL_DATE, read_textual),
    )

    found: List[Tuple[int, int, date]] = []
    for pattern, read in readers:
        for match in pattern.finditer(head):
            written = read(match)
            if written is not None:
                found.append((match.start(), match.end(), written))

    return iter(sorted(found, key=lambda candidate: candidate[0]))


def follows_a_birth_marker(head: str, position: int, floor: int) -> bool:
    """
    Whether the date at `position` is introduced as a date of birth.

    :param head: The head of the document.
    :param position: Where the date starts.
    :param floor: Where the previous date in the head ended. The look never
        reaches past it: a marker on the far side of another date introduced
        that one, and has nothing to say about this one.
    """
    start = max(floor, position - BIRTH_CONTEXT)
    window = fold(head[start:position]).replace(".", "")
    return bool(BIRTH_MARKER.search(WHITESPACE.sub(" ", window)))


def find_document_date(text: str, today: Optional[date] = None) -> Optional[date]:
    """
    Decide the date a document carries, or answer that it carries none.

    :param text: The document's extracted text.
    :param today: The day to measure "in the future" against. Defaults to the
        real one; passed explicitly by tests, which must not change meaning
        depending on when they run.
    :return: The document's own date, or `None` when the head holds no date
        this can be sure of. The rules are in the module docstring, and every
        one of them prefers `None` to a guess.
    """
    limit = today or date.today()
    head = text[:HEAD_CHARACTERS]

    # Where the last date seen ended, whether or not it was taken. A date this
    # refused is still a date somebody wrote, and it still bounds what the next
    # one may be read as following.
    floor = 0
    for position, end, written in candidates(head):
        if written.year >= EARLIEST_YEAR and written <= limit:
            if not follows_a_birth_marker(head, position, floor):
                return written
        floor = end

    return None


def span_of(dates: Sequence[Optional[date]]) -> Optional[Tuple[date, date]]:
    """
    The earliest and latest date across a batch, or nothing when none is dated.

    A batch where one document is dated answers with that date twice: the span
    a single document covers is the day it carries, and a caller rendering a
    range can see that the two ends are equal.

    :param dates: One entry per submitted document, `None` where the document
        carries no date or could not be read.
    :return: The earliest and the latest date found, or `None`.
    """
    known = [written for written in dates if written is not None]
    if not known:
        return None

    return min(known), max(known)
