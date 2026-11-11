from datetime import datetime
from pathlib import Path

import pytest

from catalejo._parse import (
    MADRID,
    CatalejoParseError,
    normalize_nif,
    parse_results_page,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_oir_first_page() -> None:
    page = parse_results_page(load("oir_dias3_page1.html"), "OIR")

    assert (page.page, page.total_pages) == (1, 8)
    assert not page.is_last
    assert len(page.filings) == 3

    first = page.filings[0]
    assert first.kind == "OIR"
    assert first.registered_at == datetime(2026, 11, 6, 14, 50, tzinfo=MADRID)
    assert first.issuer == "EUROCAJA RURAL, SOCIEDAD COOPERATIVA DE CRÉDITO"
    assert first.issuer_nif == "F45003993"
    assert first.issuer_nif_raw == "F45003993"
    assert first.category == "Otra información relevante"
    assert first.title == "La Entidad informa sobre cambios en su Consejo Rector"
    assert first.registry_number == 43535
    assert first.document_url.startswith("https://www.cnmv.es/webservices/verdocumento/ver?t=")
    assert first.document_id == "fe35f418-f7f7-40ed-b779-4c37e115744a"


def test_entries_come_newest_first() -> None:
    filings = parse_results_page(load("oir_dias3_page1.html"), "OIR").filings
    numbers = [f.registry_number for f in filings]
    assert numbers == sorted(numbers, reverse=True)


def test_last_page_and_nif_with_dash() -> None:
    page = parse_results_page(load("oir_dias3_page8_last.html"), "OIR")

    assert (page.page, page.total_pages) == (8, 8)
    assert page.is_last
    acs = page.filings[0]
    assert acs.issuer.startswith("ACS,")
    assert acs.issuer_nif == "A28004885"
    assert acs.issuer_nif_raw == "A-28004885"  # as in the HTML; the CNMV only matches this form
    assert acs.category == "Programas de recompra de acciones, estabilización y autocartera"


def test_inside_information_page() -> None:
    page = parse_results_page(load("ip_dias7_page1.html"), "IP")

    assert (page.page, page.total_pages) == (1, 2)
    assert [f.kind for f in page.filings] == ["IP", "IP", "IP"]
    hbx = page.filings[0]
    assert hbx.issuer == "HBX GROUP INTERNATIONAL PLC"
    assert hbx.issuer_nif == "N0289673F"
    assert hbx.registry_number == 3411
    assert "Carlos Muñoz" in hbx.title


def test_page_without_results_or_paginator() -> None:
    html = '<section id="maincontent"><ul id="listaElementosPrimernivel"></ul></section>'
    page = parse_results_page(html, "IP")
    assert page.filings == []
    assert (page.page, page.total_pages) == (1, 1)


def test_broken_entry_raises_instead_of_guessing() -> None:
    html = """
    <ul id="listaElementosPrimernivel">
      <li class="blocks-single"><ul><li class="fecha-con-hora">06/11/2026</li></ul></li>
    </ul>"""
    with pytest.raises(CatalejoParseError):
        parse_results_page(html, "OIR")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("A-28004885", "A28004885"), ("a28164754", "A28164754"), (" N 0289673-F ", "N0289673F")],
)
def test_normalize_nif(raw: str, expected: str) -> None:
    assert normalize_nif(raw) == expected
