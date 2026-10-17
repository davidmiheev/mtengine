"""Command line: `mte list`, `mte versions`, `mte call <function> '<json arguments>'`."""
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
    a = p.parse_args(argv)
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
