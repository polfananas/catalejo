"""Securities (ISINs) registered under an issuer, from the CNMV's ISIN agency."""

from __future__ import annotations

from catalejo._http import HttpClient
from catalejo._parse import normalize_nif, parse_securities_page
from catalejo.filings import _default_client
from catalejo.models import Security

ISIN_URL = "https://www.cnmv.es/portal/ancv/isin.aspx"


def securities(
    nif: str, *, client: HttpClient | None = None, max_pages: int = 50
) -> list[Security]:
    """All ISINs the CNMV lists for an issuer: shares, bonds, notes...

    `nif` can be written with or without dash. Use `[s for s in ... if s.is_share]`
    to keep only shares.

    >>> catalejo.securities("A64907306")  # doctest: +SKIP
    [Security(isin='ES0105066007', fisn='CLNX/AC 0.25', cfi='ESVUFB', ...)]
    """
    client = client or _default_client()
    base = normalize_nif(nif)
    if not base:
        raise ValueError("nif can't be empty")
    # Like the filings search, the CNMV only matches the NIF in the form it stores it.
    for variant in (base, f"{base[0]}-{base[1:]}"):
        found = _fetch(client, variant, max_pages)
        if found:
            return found
    return []


def _fetch(client: HttpClient, nif: str, max_pages: int) -> list[Security]:
    out: list[Security] = []
    for page_index in range(max_pages):
        page = parse_securities_page(client.get(ISIN_URL, {"nif": nif, "page": page_index}).text)
        out.extend(page.securities)
        if page.is_last or not page.securities:
            break
    return out
