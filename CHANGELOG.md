# Changelog

## 0.1.1 (unreleased)

- `catalejo` command line: `filings`, `securities`, `text` and `mcp`, with table, CSV or JSON output. Also runs as `python -m catalejo`, or without installing via `uvx catalejo`.
- The MCP server can be started with `catalejo mcp` (the `catalejo-mcp` command still works).
- `server.json` for the official MCP registry (`io.github.polfananas/catalejo`).

## 0.1.0 (2026-11-12)

First public release.

- `catalejo.filings()`: price-sensitive (IP) and other regulatory (OIR) announcements from the CNMV register, with full history since 2020, date ranges and server-side filtering by NIF.
- `catalejo.securities()`: ISINs registered under an issuer (shares, bonds...).
- `catalejo.document_text()`: text of the PDF attached to a filing (`catalejo[pdf]`).
- MCP server (`catalejo-mcp`, `catalejo[mcp]`) with `latest_filings` and `issuer_filings` tools.
- Polite by default: identifiable User-Agent, 1 request per second, on-disk cache.
