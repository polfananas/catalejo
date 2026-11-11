"""Inside information (IP) and other relevant information (OIR) published by issuers."""

from __future__ import annotations

import unicodedata
from typing import Literal

from catalejo._http import HttpClient
from catalejo._parse import normalize_nif, parse_results_page
from catalejo.models import Filing, FilingKind

BASE = "https://www.cnmv.es/portal"
RESULT_URLS: dict[FilingKind, str] = {
    "IP": f"{BASE}/Informacion-Privilegiada/Resultado-IP",
    "OIR": f"{BASE}/Otra-Informacion-Relevante/Resultado-OIR",
}

_client: HttpClient | None = None


def _default_client() -> HttpClient:
    global _client
    if _client is None:
        _client = HttpClient()
    return _client


def filings(
    days: int = 7,
    kind: FilingKind | Literal["all"] = "all",
    issuer: str | None = None,
    *,
    max_pages: int = 50,
    client: HttpClient | None = None,
) -> list[Filing]:
    """Filings registered at the CNMV in the last `days` days, newest first.

    >>> import catalejo
    >>> catalejo.filings(days=3, kind="IP")  # doctest: +SKIP
    """
    if days < 1:
        raise ValueError("days must be >= 1")
    client = client or _default_client()
    kinds: list[FilingKind] = ["IP", "OIR"] if kind == "all" else [kind]

    result: list[Filing] = []
    for k in kinds:
        result.extend(_fetch_all_pages(client, k, days, max_pages))

    if issuer is not None:
        result = [f for f in result if matches_issuer(f, issuer)]

    result.sort(key=lambda f: f.registered_at, reverse=True)
    return result


def _fetch_all_pages(
    client: HttpClient, kind: FilingKind, days: int, max_pages: int
) -> list[Filing]:
    out: list[Filing] = []
    for page_index in range(max_pages):  # the CNMV's `page` param is zero-based
        response = client.get(RESULT_URLS[kind], {"dias": days, "page": page_index})
        page = parse_results_page(response.text, kind)
        out.extend(page.filings)
        if page.is_last or not page.filings:
            break
    return out


def matches_issuer(filing: Filing, query: str) -> bool:
    """True if `query` identifies the filing's issuer.

    `query` can be a NIF ("A28004885", "A-28004885") or part of the name
    ("cellnex", "Telefónica" == "telefonica").
    """
    q = query.strip()
    if filing.issuer_nif and normalize_nif(q) == filing.issuer_nif:
        return True
    return _fold(q) in _fold(filing.issuer)


def _fold(text: str) -> str:
    """Lowercase and strip accents, so "Telefónica" == "telefonica"."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
