"""
What a refusal writes to the log.

The refused path is caller-controlled. `covers()` matches the whole `/api`
prefix, so the gate fires before any routing and `/api/<anything>` reaches the
log line - and uvicorn percent-decodes the request target into `scope["path"]`,
so `%0A` arrives as a real newline and `%1B` as a real escape byte. Logged
verbatim, an unauthenticated caller forges log records and drives the terminal
of whoever reads them.

These drive the gate through a raw ASGI scope rather than through `TestClient`,
because an HTTP client refuses to put a newline in a URL - correctly. Uvicorn
does not refuse: it decodes one into the scope, which is the shape reproduced
here.
"""

import asyncio
import logging

import pytest

from app.core.gate import LOGGED_PATH_LIMIT, loggable
from app.core.origin import RequireKnownOrigin
from app.core.config import DEFAULT_ALLOWED_ORIGINS

FOREIGN = b"https://attacker.example"


def refuse(path: str) -> None:
    """Drive the origin gate to a refusal on a path uvicorn could produce."""
    gate = RequireKnownOrigin(None, allowed_origins=DEFAULT_ALLOWED_ORIGINS)
    scope = {
        "type": "http",
        "path": path,
        "root_path": "",
        "headers": [(b"origin", FOREIGN)],
    }

    sent = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    asyncio.run(gate(scope, receive, send))
    assert sent, "the gate did not answer"


def test_a_newline_in_the_path_cannot_forge_a_log_record(caplog):
    with caplog.at_level(logging.WARNING, logger="app.core.gate"):
        refuse("/api/analyze\nWARNING:app.main:the model is loaded")

    message = caplog.records[-1].getMessage()
    assert "\n" not in message
    assert "\\n" in message


def test_an_escape_byte_in_the_path_reaches_no_terminal(caplog):
    with caplog.at_level(logging.WARNING, logger="app.core.gate"):
        refuse("/api/analyze\x1b[31mred")

    message = caplog.records[-1].getMessage()
    assert "\x1b" not in message
    assert "\\x1b" in message


def test_a_long_path_is_capped(caplog):
    # The refusal is reachable without a credential and the container log
    # rotates on size, so one request must not write an unbounded line.
    with caplog.at_level(logging.WARNING, logger="app.core.gate"):
        refuse(f"/api/{'a' * 5000}")

    message = caplog.records[-1].getMessage()
    assert len(message) < LOGGED_PATH_LIMIT + 200
    assert message.endswith("...") or "..." in message


def test_an_ordinary_path_is_logged_unchanged(caplog):
    # The escaping must not make a normal refusal unreadable: an operator
    # looking at this line needs to see which route was refused.
    with caplog.at_level(logging.WARNING, logger="app.core.gate"):
        refuse("/api/analyze/stream")

    assert "/api/analyze/stream" in caplog.records[-1].getMessage()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/api/analyze", "/api/analyze"),
        ("/api/a\nb", "/api/a\\nb"),
        ("/api/a\tb", "/api/a\\tb"),
        ("/api/\x1b", "/api/\\x1b"),
    ],
)
def test_loggable_renders_one_line_of_printable_ascii(raw, expected):
    assert loggable(raw) == expected


def test_loggable_caps_and_marks_a_truncated_path():
    rendered = loggable("/api/" + "a" * 5000)

    assert len(rendered) == LOGGED_PATH_LIMIT + 3
    assert rendered.endswith("...")
