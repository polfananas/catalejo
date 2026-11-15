from datetime import date
from pathlib import Path

import httpx
import pytest

from catalejo._http import HttpClient
from catalejo._parse import CNMVParseError, parse_securities_page
from catalejo.errors import IncompleteResultsError, IncompleteResultsWarning
from catalejo.securities import securities

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parses_shares_and_bonds() -> None:
    page = parse_securities_page(load("isin_sabadell_page1.html"))

    assert (page.page, page.total_pages) == (1, 4)
    assert len(page.securities) == 4

    shares, floater, _, fixed = page.securities
    assert shares.isin == "ES0113860A34"
    assert shares.fisn == "SAB/AC 0.125"
    assert shares.is_share
    assert shares.outstanding == 4_768_462_486
    assert shares.maturity_date is None

    assert not floater.is_share
    assert floater.maturity_date == date(2026, 11, 30)
    assert fixed.interest_rate == 3.15
    assert fixed.issue_date == date(2022, 3, 30)


def test_foreign_issuer_has_isin_only() -> None:
    page = parse_securities_page(load("isin_hbx_foreign.html"))

    (hbx,) = page.securities
    assert hbx.isin == "GB00BNXJB679"
    assert hbx.cfi is None and hbx.fisn is None
    assert not hbx.is_share  # unknown, so not counted as a share
    assert (page.page, page.total_pages) == (1, 1)


def test_tries_the_dashed_nif_when_the_plain_one_finds_nothing(tmp_path: Path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nif = request.url.params["nif"]
        seen.append(nif)
        if nif == "A-08000143":
            return httpx.Response(200, text=load("isin_hbx_foreign.html"))
        return httpx.Response(200, text=load("isin_not_found.html"))

    client = HttpClient(cache_dir=tmp_path, transport=httpx.MockTransport(handler), min_interval=0)
    result = securities("A08000143", client=client)

    assert seen == ["A08000143", "A-08000143"]
    assert [s.isin for s in result] == ["GB00BNXJB679"]


def _client(tmp_path: Path, html: str) -> HttpClient:
    return HttpClient(
        cache_dir=tmp_path,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=html)),
        min_interval=0,
    )


def test_not_found_is_an_empty_list(tmp_path: Path) -> None:
    assert securities("A00000000", client=_client(tmp_path, load("isin_not_found.html"))) == []


def test_unexpected_page_raises(tmp_path: Path) -> None:
    with pytest.raises(CNMVParseError, match="not found"):
        securities("A08000143", client=_client(tmp_path, "<html><body></body></html>"))


def test_hitting_max_pages_warns_or_raises(tmp_path: Path) -> None:
    client = _client(tmp_path, load("isin_sabadell_page1.html"))  # "page 1 of 4"
    with pytest.warns(IncompleteResultsWarning, match="max_pages=1"):
        assert len(securities("A08000143", client=client, max_pages=1)) == 4
    with pytest.raises(IncompleteResultsError):
        securities("A08000143", client=client, max_pages=1, strict=True)
