#!/usr/bin/env python3
"""Reject underscore-prefixed names.

Python has no private members: a leading underscore hides nothing, it only asks
politely. This project spells names the same way whether or not they are meant
to be called from elsewhere, so the convention is not used at all.

Checked: function, method and class names; module-level assignments; and
attributes assigned on `self`. Dunders (`__init__`, `__all__`) are Python's own
protocol and are left alone, as is a bare `_` for a value being discarded.

Parsing is done with `ast` rather than a regex, so an underscore inside a
string or a comment is never mistaken for a name.
"""

import ast
import sys
from pathlib import Path
from typing import Iterator, List, Tuple

Finding = Tuple[int, str, str]


def is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def offends(name: str) -> bool:
    """True when a name leans on the leading-underscore convention."""
    if name == "_" or is_dunder(name):
        return False
    return name.startswith("_")


def assigned_names(node: ast.AST) -> Iterator[Tuple[str, str]]:
    """Yield (name, kind) for every name a statement binds."""
    targets: List[ast.expr] = []
    if isinstance(node, (ast.Assign,)):
        targets = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]

    for target in targets:
        for element in ast.walk(target):
            if isinstance(element, ast.Name):
                yield element.id, "name"
            elif isinstance(element, ast.Attribute):
                value = element.value
                if isinstance(value, ast.Name) and value.id == "self":
                    yield element.attr, "attribute"


def check(path: Path) -> List[Finding]:
    """Report every underscore-prefixed name defined in one file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        # Leave broken syntax to the tools that report it properly.
        print(f"{path}: skipped, could not parse ({exc.msg})", file=sys.stderr)
        return []

    findings: List[Finding] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if offends(node.name):
                findings.append((node.lineno, node.name, "definition"))
        else:
            for name, kind in assigned_names(node):
                if offends(name):
                    findings.append((getattr(node, "lineno", 0), name, kind))

    return sorted(set(findings))


def main(argv: List[str]) -> int:
    failed = False

    for filename in argv:
        path = Path(filename)
        for lineno, name, kind in check(path):
            failed = True
            print(f"{path}:{lineno}: underscore-prefixed {kind} `{name}`")

    if failed:
        print(
            "\nA leading underscore does not make a name private in Python. "
            "Drop it, or move the code somewhere its visibility is real.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
