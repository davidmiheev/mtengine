"""Command line: `mte list`, `mte versions`, `mte call <function> '<json arguments>'`,
`mte lean-init [DIR]` (set up a Lake project with Mathlib for lean_check)."""
from __future__ import annotations

import argparse
import inspect
import json
import sys

from . import api


def main(argv: list[str] | None = None) -> int:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # behave like a Unix tool under `| head`
    p = argparse.ArgumentParser(prog="mte", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list functions")
    sub.add_parser("versions", help="backend versions")
    c = sub.add_parser("call", help="call a function with JSON keyword arguments")
    c.add_argument("function")
    c.add_argument("arguments", nargs="?", default="{}")
    li = sub.add_parser("lean-init", help="create a Lake project with Mathlib for lean_check")
    li.add_argument("directory", nargs="?", help="default: $XDG_DATA_HOME/mtengine/lean")
    li.add_argument("--mathlib", default=None, help="Mathlib tag or commit (default: %(default)s)")
    li.add_argument("--no-cache", action="store_true", help="skip `lake exe cache get`")
    a = p.parse_args(argv)
    if a.cmd == "lean-init":
        from .backends import lean
        r = lean.init(a.directory, a.mathlib or lean.DEFAULT_MATHLIB, not a.no_cache)
        print(json.dumps(r, indent=2))
        if a.directory and a.directory != str(lean.DATA_PROJECT):
            print(f"set MTENGINE_LEAN_PROJECT={r['project']} to use it", file=sys.stderr)
        return 0
    if a.cmd == "list":
        for name, f in api.FUNCTIONS.items():
            doc = (inspect.getdoc(f) or "").splitlines()[0]
            print(f"{name}{inspect.signature(f)}\n    {doc}")
        return 0
    if a.cmd == "versions":
        print(json.dumps(api.versions(), indent=2)); return 0
    if a.function not in api.FUNCTIONS:
        print(f"unknown function {a.function}; see `mte list`", file=sys.stderr); return 2
    result = api.FUNCTIONS[a.function](**json.loads(a.arguments))
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
