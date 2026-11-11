"""MCP server exposing CNMV filings to AI agents."""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

import catalejo

mcp = FastMCP("catalejo")


def _as_dict(f: catalejo.Filing) -> dict[str, Any]:
    return {
        "kind": f.kind,
        "registered_at": f.registered_at.isoformat(),
        "issuer": f.issuer,
        "issuer_nif": f.issuer_nif,
        "category": f.category,
        "title": f.title,
        "registry_number": f.registry_number,
        "document_url": f.document_url,
    }


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
    issuer: str, days: int = 7, kind: Literal["IP", "OIR", "all"] = "all"
) -> list[dict[str, Any]]:
    """Filings from one specific company at the Spanish CNMV, newest first.

    issuer: company name or part of it ("Cellnex", "telefonica") or its Spanish
    tax id / NIF ("A64907306"). Accents and case don't matter.
    Keep `days` small (7-14): each extra week means more pages to download.
    """
    return [_as_dict(f) for f in catalejo.filings(days=days, kind=kind, issuer=issuer)]


def main() -> None:
    mcp.run()  # stdio by default


if __name__ == "__main__":
    main()
