"""
The one rule the gate depends on: which path the router will match.

`routed_path` decides whether a request is inside the guarded prefix, so a
disagreement between it and Starlette's own stripping is not a cosmetic bug -
it is a request the router sends to an analysis route and the gate declines to
judge. That has already happened once in this codebase, on a different mount
prefix, and the fix was to write the rule down in one place.

Writing it down is not enough on its own, because the rule belongs to Starlette
and this is a copy of it. So the copy is compared against the original here,
across a table that includes the cases where a careless implementation and a
correct one differ. If a Starlette upgrade changes the rule, this fails rather
than the control quietly narrowing.
"""

import pytest
from starlette._utils import get_route_path  # pylint: disable=C0415,W0212

from app.core.gate import PROTECTED_PREFIX, covers, routed_path

# (root_path, path). The interesting rows are the ones where `root_path` is a
# prefix of `path` but not a path-segment prefix of it: Starlette leaves those
# alone, and a `startswith` implementation would strip them.
CASES = [
    ("", "/api/analyze"),
    ("", "/"),
    ("/med-assist", "/med-assist/api/analyze"),
    ("/med-assist", "/med-assist"),
    ("/med-assist", "/med-assist/"),
    ("/med-assist", "/healthz"),
    # The bypass. `/a` is a string prefix of `/api/analyze`, so a `startswith`
    # strip yields `pi/analyze` - outside the guarded prefix - while Starlette
    # routes the request to `/api/analyze` and runs it.
    ("/a", "/api/analyze"),
    ("/ap", "/api/analyze"),
    ("/api", "/api/analyze"),
    ("/api/analyze", "/api/analyze"),
    ("/x", "/api/analyze"),
    ("/api", "/apiary"),
]


@pytest.mark.parametrize("root_path,path", CASES)
def test_the_gate_reads_the_path_the_router_reads(root_path, path):
    scope = {"type": "http", "path": path, "root_path": root_path}

    assert routed_path(scope) == get_route_path(scope)


@pytest.mark.parametrize(
    "root_path,path",
    [("/a", "/api/analyze"), ("/ap", "/api/analyze"), ("", "/api/analyze")],
)
def test_a_prefix_that_is_not_a_segment_boundary_stays_gated(root_path, path):
    # The regression this file exists for, stated as the security property
    # rather than as an equality: whatever the mount prefix, a request the
    # router will send to an analysis route is one the gate covers.
    scope = {"type": "http", "path": path, "root_path": root_path}

    assert covers(routed_path(scope))


def test_a_path_outside_the_prefix_is_not_covered():
    scope = {"type": "http", "path": "/healthz", "root_path": ""}

    assert not covers(routed_path(scope))


def test_the_guarded_prefix_itself_is_covered():
    assert covers(PROTECTED_PREFIX)
    assert covers(f"{PROTECTED_PREFIX}/analyze")
    assert not covers(f"{PROTECTED_PREFIX}ary")
