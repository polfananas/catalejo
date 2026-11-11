from datetime import datetime
from pathlib import Path

import httpx
import pytest

from catalejo._http import HttpClient
from catalejo._parse import MADRID
from catalejo.filings import filings, matches_issuer
from catalejo.models import Filing

FIXTURES = Path(__file__).parent / "fixtures"

# (path fragment, zero-based page) -> fixture file
PAGES = {
    ("Resultado-IP", "0"): "ip_dias7_page1.html",
    ("Resultado-IP", "1"): "oir_dias3_page8_last.html",  # same markup, says "8 de 8"
    ("Resultado-OIR", "0"): "oir_dias3_page8_last.html",
}


@pytest.fixture
def requests_seen() -> list[httpx.URL]:
    return []


@pytest.fixture
def client(tmp_path: Path, requests_seen: list[httpx.URL]) -> HttpClient:
    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request.url)
        page = request.url.params.get("page", "0")
        for (fragment, p), name in PAGES.items():
            if fragment in request.url.path and p == page:
                return httpx.Response(200, text=(FIXTURES / name).read_text(encoding="utf-8"))
        return httpx.Response(404)

    return HttpClient(
        cache_dir=tmp_path,
        transport=httpx.MockTransport(handler),
        min_interval=0,
        sleep=lambda s: None,
    )


def test_follows_pagination_until_last_page(
    client: HttpClient, requests_seen: list[httpx.URL]
) -> None:
    result = filings(days=7, kind="IP", client=client)

    assert [u.params["page"] for u in requests_seen] == ["0", "1"]
    assert all(u.params["dias"] == "7" for u in requests_seen)
    assert len(result) == 5


def test_all_merges_both_channels_newest_first(client: HttpClient) -> None:
    result = filings(days=7, kind="all", client=client)

    dates = [f.registered_at for f in result]
    assert dates == sorted(dates, reverse=True)
    assert {f.kind for f in result} == {"IP", "OIR"}


def test_max_pages_is_respected(client: HttpClient, requests_seen: list[httpx.URL]) -> None:
    filings(days=7, kind="IP", max_pages=1, client=client)
    assert len(requests_seen) == 1


def test_days_must_be_positive(client: HttpClient) -> None:
    with pytest.raises(ValueError):
        filings(days=0, client=client)


def _filing(issuer: str, nif: str | None) -> Filing:
    return Filing(
        kind="IP",
        registered_at=datetime(2026, 11, 6, 12, 0, tzinfo=MADRID),
        issuer=issuer,
        issuer_nif=nif,
        category="",
        title="",
        registry_number=1,
        document_url="",
    )


def test_matches_issuer() -> None:
    cellnex = _filing("CELLNEX TELECOM, S.A.", "A64907306")
    telefonica = _filing("TELEFÓNICA, S.A.", "A28015865")

    assert matches_issuer(cellnex, "A64907306")
    assert matches_issuer(cellnex, "a-64907306")
    assert matches_issuer(cellnex, "cellnex")
    assert matches_issuer(telefonica, "telefonica")
    assert matches_issuer(telefonica, "Telefónica")
    assert not matches_issuer(cellnex, "telefonica")
    assert not matches_issuer(_filing("SIN NIF", None), "A64907306")
