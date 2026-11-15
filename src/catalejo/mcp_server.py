"""MCP server exposing CNMV filings to AI agents."""

from __future__ import annotations

import dataclasses
import logging
import warnings
from datetime import date
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

import catalejo

mcp = FastMCP("catalejo")
# FastMCP has no `version` argument: without this, clients see the version of the
# `mcp` library instead of catalejo's.
mcp._mcp_server.version = catalejo.__version__

SOURCE = "CNMV official registers (cnmv.es)"
Kind = Literal["IP", "OIR", "all"]
Limit = Annotated[int, Field(ge=1, le=200, description="Max filings returned, newest first.")]


def _as_dict(f: catalejo.Filing) -> dict[str, Any]:
    d = dataclasses.asdict(f)
    d["registered_at"] = f.registered_at.isoformat()  # datetime isn't JSON
    return d


def _search(limit: int, **kwargs: Any) -> dict[str, Any]:
    """Run catalejo.filings and say plainly whether the answer is complete."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", catalejo.IncompleteResultsWarning)
        found = catalejo.filings(**kwargs)
    complete = not any(issubclass(w.category, catalejo.IncompleteResultsWarning) for w in caught)

    result: dict[str, Any] = {
        "filings": [_as_dict(f) for f in found[:limit]],
        "found": len(found),
        "returned": min(len(found), limit),
        "complete": complete,
        "source": SOURCE,
    }
    if not complete:
        result["note"] = (
            "The CNMV search hit catalejo's page limit, so older filings in this window are "
            "missing. Use a shorter window, or search by NIF."
        )
    elif len(found) > limit:
        result["note"] = f"Showing the newest {limit} of {len(found)}. Raise `limit` for more."
    return result


@mcp.tool()
def latest_filings(
    days: Annotated[int, Field(ge=1, le=14, description="Last N days (1-14).")] = 3,
    kind: Kind = "all",
    limit: Limit = 50,
) -> dict[str, Any]:
    """Latest filings published at the Spanish CNMV, newest first.

    kind: "IP" = price-sensitive announcements, "OIR" = other regulatory announcements.
    For one company, or for longer periods, use `issuer_filings`.

    `complete` is false if the search was cut short; `found` counts every match,
    `returned` how many are in `filings`. In each filing, `issuer` is the company
    the filing is about: a bidder's announcements about a takeover, for example,
    are filed under the target.
    """
    return _search(limit, days=days, kind=kind)


@mcp.tool()
def issuer_filings(
    issuer: str,
    days: Annotated[int, Field(ge=1, le=366)] = 7,
    kind: Kind = "all",
    since: date | None = None,
    until: date | None = None,
    limit: Limit = 50,
) -> dict[str, Any]:
    """Filings from one specific company at the Spanish CNMV, newest first.

    issuer: its Spanish tax id / NIF ("A64907306") is best: the CNMV filters by it
    directly, so even years of history come back in seconds. A company name or part
    of it ("Cellnex", "telefonica") also works but scans every filing, so keep
    `days` small (7-14) when searching by name.
    since / until: optional date range (YYYY-MM-DD) for history; overrides `days`.
    Price-sensitive announcements (IP) exist from Feb 2020 onwards.

    `complete` is false if the search was cut short; `found` counts every match,
    `returned` how many are in `filings`.
    """
    return _search(limit, days=days, kind=kind, issuer=issuer, since=since, until=until)


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one INFO line per request is noise
    mcp.run()  # stdio by default


if __name__ == "__main__":
    main()
