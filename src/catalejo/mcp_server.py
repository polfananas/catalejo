"""MCP server exposing CNMV filings to AI agents."""

from __future__ import annotations

import dataclasses
import logging
from datetime import date
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

import catalejo

mcp = FastMCP("catalejo")


def _as_dict(f: catalejo.Filing) -> dict[str, Any]:
    d = dataclasses.asdict(f)
    d["registered_at"] = f.registered_at.isoformat()  # datetime isn't JSON
    return d


@mcp.tool()
def latest_filings(
    days: int = 3, kind: Literal["IP", "OIR", "all"] = "all"
) -> list[dict[str, Any]]:
    """Latest filings published at the Spanish CNMV, newest first.

    kind: "IP" = inside information (price-sensitive), "OIR" = other relevant information.
    """
    return [_as_dict(f) for f in catalejo.filings(days=days, kind=kind)]


@mcp.tool()
def issuer_filings(
    issuer: str,
    days: int = 7,
    kind: Literal["IP", "OIR", "all"] = "all",
    since: date | None = None,
    until: date | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Filings from one specific company at the Spanish CNMV, newest first.

    issuer: its Spanish tax id / NIF ("A64907306") is best: the CNMV filters by it
    directly, so even years of history come back in seconds. A company name or part
    of it ("Cellnex", "telefonica") also works but scans every filing, so keep
    `days` small (7-14) when searching by name.
    since / until: optional date range (YYYY-MM-DD) for history; overrides `days`.
    Inside information (IP) exists from Feb 2020 onwards.
    limit: max filings returned (the newest ones).
    """
    found = catalejo.filings(days=days, kind=kind, issuer=issuer, since=since, until=until)
    return [_as_dict(f) for f in found[:limit]]


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one INFO line per request is noise
    mcp.run()  # stdio by default


if __name__ == "__main__":
    main()
