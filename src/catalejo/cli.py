"""Command line interface: ``catalejo filings``, ``securities``, ``text`` and ``mcp``."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import os
import shutil
import sys
from collections.abc import Callable, Sequence
from datetime import date, datetime
from typing import Any, Literal

import catalejo
from catalejo._http import CNMVRequestError
from catalejo._parse import CNMVParseError
from catalejo.models import Filing, FilingKind, Security


def _start(value: str) -> date:
    """--since accepts a year ("2020", meaning 1 Jan) or a full date ("2020-03-15")."""
    if len(value) == 4 and value.isdigit():
        return date(int(value), 1, 1)
    return _iso(value)


def _end(value: str) -> date:
    """--until accepts a year ("2023", meaning 31 Dec) or a full date."""
    if len(value) == 4 and value.isdigit():
        return date(int(value), 12, 31)
    return _iso(value)


def _iso(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY or YYYY-MM-DD, got {value!r}") from None


def _plain(item: Filing | Security) -> dict[str, Any]:
    d = dataclasses.asdict(item)
    return {k: v.isoformat() if isinstance(v, (date, datetime)) else v for k, v in d.items()}


def _cut(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _filings_table(found: Sequence[Filing]) -> None:
    width = shutil.get_terminal_size((120, 20)).columns
    for f in found:
        head = f"{f.registered_at:%Y-%m-%d %H:%M}  {f.kind:<3}  {_cut(f.issuer, 28):<28}  "
        print(head + _cut(f.title, max(width - len(head), 20)))


def _securities_table(found: Sequence[Security]) -> None:
    for s in found:
        outstanding = f"{s.outstanding:,.0f}" if s.outstanding is not None else ""
        print(
            f"{s.isin}  {s.fisn or '':<24}  {s.cfi or '':<6}  {s.currency or '':<3}  {outstanding}"
        )


def _emit(
    items: Sequence[Any],
    fmt: str,
    cls: type[Filing] | type[Security],
    table: Callable[[Sequence[Any]], None],
) -> None:
    if fmt == "json":
        json.dump([_plain(x) for x in items], sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif fmt == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=[f.name for f in dataclasses.fields(cls)])
        writer.writeheader()
        writer.writerows(_plain(x) for x in items)
    else:
        table(items)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catalejo", description="Spanish CNMV public data from the command line."
    )
    parser.add_argument("--version", action="version", version=f"catalejo {catalejo.__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    p = sub.add_parser(
        "filings", help="price-sensitive (IP) and other regulatory (OIR) announcements"
    )
    p.add_argument("--days", type=int, default=7, help="last N days (default: 7)")
    p.add_argument("--kind", type=str.upper, choices=["IP", "OIR", "ALL"], default="ALL")
    p.add_argument("--issuer", help="NIF (fast) or part of the company name (scans everything)")
    p.add_argument("--since", type=_start, help="YYYY or YYYY-MM-DD, instead of --days")
    p.add_argument("--until", type=_end, help="YYYY or YYYY-MM-DD")
    p.add_argument("--limit", type=int, help="only the N newest")
    p.add_argument("--format", choices=["table", "csv", "json"], default="table")

    p = sub.add_parser("securities", help="ISINs registered under an issuer")
    p.add_argument("nif", help='Spanish tax id, e.g. "A64907306"')
    p.add_argument("--shares", action="store_true", help="only shares")
    p.add_argument("--format", choices=["table", "csv", "json"], default="table")

    p = sub.add_parser("text", help="text of a filed document (needs catalejo[pdf])")
    p.add_argument("url", help="the document_url of a filing")

    sub.add_parser("mcp", help="run the MCP server over stdio (needs catalejo[mcp])")
    return parser


def _run_mcp() -> int:
    try:
        from catalejo import mcp_server
    except ImportError:
        print(
            'catalejo: the MCP server needs an extra: pip install "catalejo[mcp]"', file=sys.stderr
        )
        return 1
    mcp_server.main()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "mcp":
        return _run_mcp()
    try:
        if args.command == "filings":
            kind: FilingKind | Literal["all"] = "all" if args.kind == "ALL" else args.kind
            found = catalejo.filings(
                days=args.days, kind=kind, issuer=args.issuer, since=args.since, until=args.until
            )
            _emit(found[: args.limit], args.format, Filing, _filings_table)
        elif args.command == "securities":
            secs = catalejo.securities(args.nif)
            if args.shares:
                secs = [s for s in secs if s.is_share]
            _emit(secs, args.format, Security, _securities_table)
        else:
            print(catalejo.document_text(args.url))
    except (CNMVRequestError, CNMVParseError, ValueError, ImportError) as e:
        print(f"catalejo: {e}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        # `catalejo filings | head`: the reader went away, that's fine
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return 0


if __name__ == "__main__":
    sys.exit(main())
