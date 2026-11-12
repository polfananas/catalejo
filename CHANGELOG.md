# Changelog

## 0.1.0 (unreleased)

First public release.

- `catalejo.filings()`: price-sensitive (IP) and other regulatory (OIR) announcements from the CNMV register, with full history since 2020, date ranges and server-side filtering by NIF.
- `catalejo.securities()`: ISINs registered under an issuer (shares, bonds...).
- `catalejo.document_text()`: text of the PDF attached to a filing (`catalejo[pdf]`).
- MCP server (`catalejo-mcp`, `catalejo[mcp]`) with `latest_filings` and `issuer_filings` tools.
- Polite by default: identifiable User-Agent, 1 request per second, on-disk cache.
