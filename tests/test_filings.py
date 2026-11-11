from datetime import date, datetime
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
    with pytest.warns(UserWarning):
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


def test_empty_issuer_is_rejected() -> None:
    with pytest.raises(ValueError):
        matches_issuer(_filing("CELLNEX TELECOM, S.A.", "A64907306"), "   ")


EMPTY_PAGE = '<section id="maincontent"><ul id="listaElementosPrimernivel"></ul></section>'


def test_nif_query_is_filtered_by_the_cnmv(tmp_path: Path) -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        if request.url.params.get("nif") != "A64907306":  # Cellnex is stored without dash
            return httpx.Response(200, text=EMPTY_PAGE)
        name = {"0": "ip_dias7_page1.html", "1": "oir_dias3_page8_last.html"}[
            request.url.params["page"]
        ]
        return httpx.Response(200, text=(FIXTURES / name).read_text(encoding="utf-8"))

    client = HttpClient(
        cache_dir=tmp_path,
        transport=httpx.MockTransport(handler),
        min_interval=0,
        sleep=lambda s: None,
    )
    result = filings(days=7, kind="IP", issuer="a-64907306", client=client)

    assert [f.registry_number for f in result] == [3409]
    assert {u.params["nif"] for u in seen} == {"A64907306", "A-64907306"}
    assert len(seen) == 3  # two pages for the right variant, one empty page for the other


def test_name_query_scans_everything(client: HttpClient, requests_seen: list[httpx.URL]) -> None:
    result = filings(days=7, kind="IP", issuer="cellnex", client=client)

    assert [f.issuer for f in result] == ["CELLNEX TELECOM, S.A."]
    assert all("nif" not in u.params for u in requests_seen)


def test_date_range_uses_fecha_params(client: HttpClient, requests_seen: list[httpx.URL]) -> None:
    filings(kind="IP", since=date(2025, 1, 1), until=date(2025, 12, 31), client=client)

    first = requests_seen[0].params
    assert first["fechaDesde"] == "01/01/2025"
    assert first["fechaHasta"] == "31/12/2025"
    assert "dias" not in first


def test_more_than_90_days_becomes_a_date_range(
    client: HttpClient, requests_seen: list[httpx.URL]
) -> None:
    filings(days=180, kind="IP", client=client)

    params = requests_seen[0].params
    assert "dias" not in params
    since = datetime.strptime(params["fechaDesde"], "%d/%m/%Y").date()
    until = datetime.strptime(params["fechaHasta"], "%d/%m/%Y").date()
    assert (until - since).days == 180


def test_since_after_until_is_an_error(client: HttpClient) -> None:
    with pytest.raises(ValueError):
        filings(since=date(2026, 1, 2), until=date(2026, 1, 1), client=client)


def test_hitting_max_pages_warns(client: HttpClient) -> None:
    with pytest.warns(UserWarning, match="incomplete"):
        filings(days=7, kind="IP", max_pages=1, client=client)
