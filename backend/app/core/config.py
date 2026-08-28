import re
from collections.abc import Sequence
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Where the frontend is served from in a local `docker compose up`. It is the
# fallback rather than a wildcard on purpose: see `normalise_origin`.
DEFAULT_ALLOWED_ORIGINS = ("http://localhost:3000",)

# The port a browser leaves out of the `Origin` header, per scheme. Configured
# explicitly, it would make the entry match nothing at all.
DEFAULT_PORTS = {"http": 80, "https": 443}

ORIGIN_SCHEMES = tuple(DEFAULT_PORTS)

WILDCARD = "*"

# A host as a browser sends it: ASCII, lowercase, no wildcard, no spaces. An
# international domain reaches the header in its punycode form, so that is the
# form to configure.
HOSTNAME_PATTERN = re.compile(r"[a-z0-9]([a-z0-9._-]*[a-z0-9])?")

IPV6_PATTERN = re.compile(r"[0-9a-f:.]+")


def is_host(host: str) -> bool:
    """
    Say whether a host is one a browser could put in an `Origin` header.

    :param host: The host part of an entry, as `urlsplit` reports it - already
        lowercased, and with the brackets of an IPv6 literal removed.
    :return: True when the host is usable as written.
    """
    pattern = IPV6_PATTERN if ":" in host else HOSTNAME_PATTERN
    return bool(pattern.fullmatch(host))


class CORSOriginError(RuntimeError):
    """
    Raised at startup when CORS_ALLOWED_ORIGINS cannot be read as origins.

    Deliberately not a `ValueError`: pydantic converts a `ValueError` raised in
    a validator into a `ValidationError` that quotes the input it rejected, and
    the input here is deployment configuration that can name an internal host.
    A `RuntimeError` propagates out of the validator as it was written, so the
    refusal carries nothing but the message `refusal` composed. A chained cause
    from the standard library can still name the fragment it choked on, which
    is why every path that can raise one goes through `refusal` rather than
    letting the original error out.
    """


def normalise_origin(entry: str, position: int) -> str:
    """
    Return one configured entry as a bare origin, or refuse it.

    An origin is a scheme, a host and an optional port - nothing else. Starlette
    compares the browser's `Origin` header against these strings literally, so
    an entry that is not exactly what the browser sends allows nothing at all,
    with no error anywhere to say why. Everything here exists to make that
    impossible: the two forms with one obvious reading are rewritten into the
    browser's own - a single trailing slash is dropped, and so is a port that
    the scheme makes implicit, since `https://host:443` is sent as
    `https://host`. Anything else that cannot be an origin, or that a browser
    would spell differently, is refused while the process is still starting.

    :param entry: One comma-separated entry, already stripped of whitespace.
    :param position: Its 1-based position in the variable, used to point at the
        offending entry without quoting it.
    :return: The origin as `scheme://host[:port]`, as a browser sends it.
    :raises CORSOriginError: If the entry is a wildcard or is not an origin.
    """
    if entry == WILDCARD:
        raise CORSOriginError(
            "CORS_ALLOWED_ORIGINS may not contain '*'. This API answers with "
            "credentials, and a browser rejects a credentialed response whose "
            "allowed origin is a wildcard - so the wildcard would not widen "
            "access, it would remove it. List each origin the frontend is "
            "served from."
        )

    try:
        # Both calls are inside the try. `urlsplit` raises on an unbalanced
        # IPv6 bracket and on a host that normalises into a delimiter, and it
        # parses the rest lazily, so a port that is not a number or is out of
        # range only raises on access. Every one of those messages quotes the
        # text it choked on, and letting a `ValueError` out of the validator
        # would hand pydantic the whole variable to echo.
        split = urlsplit(entry)
        host = split.hostname
        port = split.port
    except ValueError as exc:
        raise CORSOriginError(refusal(position)) from exc

    if (
        split.scheme not in ORIGIN_SCHEMES
        or not host
        or not is_host(host)
        or port == 0
        # `host:` parses as no port at all and keeps the dangling colon.
        or split.netloc.endswith(":")
        or split.username is not None
        or split.password is not None
        or split.path not in ("", "/")
        or split.query
        or split.fragment
    ):
        raise CORSOriginError(refusal(position))

    literal = f"[{host}]" if ":" in host else host
    if port is None or port == DEFAULT_PORTS[split.scheme]:
        return f"{split.scheme}://{literal}"
    return f"{split.scheme}://{literal}:{port}"


def refusal(position: int) -> str:
    """
    Say which entry is wrong and what one looks like, without quoting it.

    :param position: The entry's 1-based position in the variable.
    :return: The message carried by `CORSOriginError`.
    """
    return (
        f"CORS_ALLOWED_ORIGINS entry {position} is not an origin. Every entry "
        "is scheme://host[:port] - http or https, no path, no query, no "
        "fragment, no credentials, no wildcard in the host, and an "
        "international domain in its punycode form. The value is left out of "
        "this message because a deployment's origins can name an internal host."
    )


class CORSConfiguration(BaseSettings):
    """Which browser origins may call this API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
        # With the alias alone, `CORSConfiguration(allowed_origins=[...])` is
        # dropped as an extra field and the caller silently gets the default -
        # the one field here that would fail quietly rather than loudly.
        populate_by_name=True,
    )

    # `NoDecode` is what makes the plain comma-separated form work.
    # pydantic-settings reads a variable typed as a collection by running
    # `json.loads` on it first, so `http://localhost:3000` - not JSON - would
    # fail before any validator here ran, and the only spelling that worked
    # would be a JSON array. This turns that decoding off and hands the raw
    # string to the validator below.
    allowed_origins: Annotated[tuple[str, ...], NoDecode] = Field(
        default=DEFAULT_ALLOWED_ORIGINS,
        alias="CORS_ALLOWED_ORIGINS",
        description=(
            "Comma-separated browser origins allowed to call the API, each "
            "written as scheme://host[:port]. Unset or empty keeps the local "
            "frontend origin rather than opening up: this API answers with "
            "credentials, so widening the set is always deliberate."
        ),
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def read_the_configured_origins(cls, raw: str | Sequence[str]) -> tuple[str, ...]:
        """
        Split the variable, normalise each entry and refuse what is not one.

        Whitespace around an entry is trimmed and an empty entry is dropped, so
        a trailing comma or a value wrapped over two lines still reads. A value
        that holds nothing at all falls back to the default: an empty allow-list
        would refuse the local frontend, which looks like the service is broken
        rather than like a configuration mistake.

        :param raw: The variable's value, or the default already as a sequence.
        :return: The origins, in the order they were configured.
        """
        entries = raw.split(",") if isinstance(raw, str) else list(raw)
        origins = tuple(
            normalise_origin(entry.strip(), position)
            for position, entry in enumerate(entries, start=1)
            if entry.strip()
        )
        return origins or DEFAULT_ALLOWED_ORIGINS


class NERModelConfiguration(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )

    model_name: str = Field(..., alias="NER_MODEL_NAME")
    inference_threads: int = Field(
        default=0,
        alias="NER_INFERENCE_THREADS",
        ge=0,
        description=(
            "Threads torch may use for one CPU inference. Zero keeps torch's "
            "own default, which is one thread per core."
        ),
    )
    max_concurrent_inferences: int = Field(
        default=1,
        alias="NER_MAX_CONCURRENT_INFERENCES",
        gt=0,
        le=8,
        description=(
            "How many documents may be inside the model at once. One by "
            "default: a second copy of the activations is what puts a small "
            "machine into swap. Above one, the same transformers pipeline is "
            "called from several threads, which transformers does not document "
            "as safe - prefer more worker processes. Bounded because the "
            "threadpool behind it has a ceiling of its own."
        ),
    )
