"""Price-sensitive (IP) and other regulatory (OIR) announcements published by issuers."""

from __future__ import annotations

import re
import unicodedata
import warnings
from datetime import date, datetime, timedelta
from typing import Literal

from catalejo._http import HttpClient
from catalejo._parse import MADRID, normalize_nif, parse_results_page
from catalejo.errors import IncompleteResultsError, IncompleteResultsWarning
from catalejo.models import Filing, FilingKind

BASE = "https://www.cnmv.es/portal"
RESULT_URLS: dict[FilingKind, str] = {
    "IP": f"{BASE}/Informacion-Privilegiada/Resultado-IP",
    "OIR": f"{BASE}/Otra-Informacion-Relevante/Resultado-OIR",
}

# Spanish NIF/CIF shapes: B12345678, A1234567B, 12345678Z (foreign issuers: N1234567X)
MAX_DAYS = 90  # the CNMV answers HTTP 400 above ~91; longer windows go as a date range

_NIF = re.compile(r"^(?:[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z])$")

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
    since: date | None = None,
    until: date | None = None,
    max_pages: int = 50,
    strict: bool = False,
    client: HttpClient | None = None,
) -> list[Filing]:
    """Filings registered at the CNMV, newest first.

    By default the last `days` days. Pass `since` (and optionally `until`) for a
    fixed date range instead, e.g. to pull history.

    Each search reads at most `max_pages` pages of 10 filings per kind. If there
    are more, you get the newest ones and an :class:`IncompleteResultsWarning`;
    with ``strict=True``, an :class:`IncompleteResultsError` instead.

    >>> import catalejo
    >>> catalejo.filings(days=3, kind="IP")  # doctest: +SKIP
    >>> catalejo.filings(since=date(2024, 1, 1), issuer="A64907306")  # doctest: +SKIP
    """
    if days < 1:
        raise ValueError("days must be >= 1")
    window = _window(days, since, until)
    client = client or _default_client()
    kinds: list[FilingKind] = ["IP", "OIR"] if kind == "all" else [kind]

    nif = _as_nif(issuer) if issuer is not None else None

    result: list[Filing] = []
    # IP and OIR are numbered separately. A filing can show up twice if a new one
    # is registered while we page through the results (everything shifts by one).
    seen: set[tuple[str, int]] = set()
    for k in kinds:
        # By NIF, ask the CNMV for just this issuer. It only matches the NIF in the
        # exact form it stores it, with or without a dash, so try both.
        searches = [{**window, "nif": v} for v in (nif, f"{nif[0]}-{nif[1:]}")] if nif else [window]
        for params in searches:
            for f in _fetch_all_pages(client, k, params, max_pages, strict):
                if (f.kind, f.registry_number) not in seen:
                    seen.add((f.kind, f.registry_number))
                    result.append(f)

    if issuer is not None:
        result = [f for f in result if matches_issuer(f, issuer)]

    result.sort(key=lambda f: f.registered_at, reverse=True)
    return result


def _fetch_all_pages(
    client: HttpClient,
    kind: FilingKind,
    params: dict[str, str | int],
    max_pages: int,
    strict: bool,
) -> list[Filing]:
    out: list[Filing] = []
    for page_index in range(max_pages):  # the CNMV's `page` param is zero-based
        response = client.get(RESULT_URLS[kind], {**params, "page": page_index})
        page = parse_results_page(response.text, kind)
        out.extend(page.filings)
        if page.is_last or not page.filings:
            break
    else:
        incomplete(
            f"{kind} filings: stopped after max_pages={max_pages}, older ones are missing. "
            "Narrow the date range, search by NIF or raise max_pages.",
            strict,
        )
    return out


def incomplete(message: str, strict: bool) -> None:
    """Report a search that stopped at max_pages: warn, or raise if strict."""
    if strict:
        raise IncompleteResultsError(message)
    warnings.warn(message, IncompleteResultsWarning, stacklevel=4)


def _window(days: int, since: date | None, until: date | None) -> dict[str, str | int]:
    """Query params for the time window: `dias=N` when possible, a date range otherwise."""
    if since is None and until is None and days <= MAX_DAYS:
        return {"dias": days}
    today = datetime.now(MADRID).date()
    until = until or today
    since = since or until - timedelta(days=days)
    if since > until:
        raise ValueError(f"since ({since}) is after until ({until})")
    return {"fechaDesde": f"{since:%d/%m/%Y}", "fechaHasta": f"{until:%d/%m/%Y}"}


def _as_nif(query: str) -> str | None:
    """The query normalized as a NIF, or None if it doesn't look like one."""
    candidate = normalize_nif(query)
    return candidate if _NIF.match(candidate) else None


def matches_issuer(filing: Filing, query: str) -> bool:
    """True if `query` identifies the filing's issuer.

    `query` can be a NIF ("A28004885", "A-28004885") or part of the name
    ("cellnex", "Telefónica" == "telefonica").
    """
    q = query.strip()
    if not q:
        raise ValueError("issuer can't be empty")
    if filing.issuer_nif and normalize_nif(q) == filing.issuer_nif:
        return True
    return _fold(q) in _fold(filing.issuer)


def _fold(text: str) -> str:
    """Lowercase and strip accents, so "Telefónica" == "telefonica"."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
