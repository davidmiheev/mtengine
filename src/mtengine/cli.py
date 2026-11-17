"""Command line: `mte list`, `mte versions`, `mte call <function> '<json arguments>'`,
`mte lean-init [DIR]` (set up the standard Lake project with Mathlib for lean_check),
`mte lean-status` (which Lake project lean_check uses, and whether it is ready)."""
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
    li = sub.add_parser("lean-init", help="set up the standard Lake project with Mathlib for lean_check")
    li.add_argument("directory", nargs="?", help="default: $XDG_DATA_HOME/mtengine/lean")
    li.add_argument("--mathlib", default=None,
                    help="Mathlib tag or commit instead of the pinned one (the project is then not the standard one)")
    li.add_argument("--no-cache", action="store_true", help="skip `lake exe cache get`")
    sub.add_parser("lean-status", help="which Lake project lean_check uses, and whether it is ready")
    a = p.parse_args(argv)
    if a.cmd == "lean-init":
        from .backends import lean
        r = lean.init(a.directory, a.mathlib, not a.no_cache)
        print(json.dumps(r, indent=2))
        st = lean.status()
        if st["project"] != r["project"]:
            print(f"note: lean_check uses {st['project']} ({st['source']}); "
                  f"set MTENGINE_LEAN_PROJECT={r['project']} to use this one", file=sys.stderr)
        return 0
    if a.cmd == "lean-status":
        print(json.dumps(api.lean_status(), indent=2))
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
