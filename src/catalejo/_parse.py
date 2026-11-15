"""HTML parsing for CNMV result listings (IP and OIR share the same markup)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import unquote, urljoin
from zoneinfo import ZoneInfo

from selectolax.lexbor import LexborHTMLParser as HTMLParser
from selectolax.lexbor import LexborNode as Node

from catalejo.models import Filing, FilingKind, Security

MADRID = ZoneInfo("Europe/Madrid")

# Result pages live at /portal/<section>/Resultado-XX. Some entries link to a CNMV
# page instead of a PDF, with a relative href ("../consultas/..."): resolve it.
_RESULTS_BASE = "https://www.cnmv.es/portal/Otra-Informacion-Relevante/Resultado-OIR"
# What the CNMV shows when a search finds nothing. A page with no results and
# without this notice isn't what we expect (changed layout, error page...): fail.
_NO_FILINGS = "[id$=wucSinDatos_divAviso]"
_NO_SECURITIES = "[id$=ContentPrincipal_divAviso]"  # "...no ha sido encontrado..."
_PAGE_INFO = re.compile(r"(\d+)\D+(\d+)")  # "Página 1 de 8" / "Page 1 out of 8"
# "Número de registro: 43521" (or "Register number: 43521" in English). Anchored on
# the label: titles can mention the Registro Mercantil too.
_REGISTRY = re.compile(r"(?:registro|register number)\s*:\s*(\d+)\s*$", re.IGNORECASE)


class CNMVParseError(ValueError):
    """The page didn't look like we expected. Probably the CNMV changed its HTML."""


@dataclass(frozen=True, slots=True)
class ResultsPage:
    filings: list[Filing]
    page: int
    """1-based number of this page."""
    total_pages: int

    @property
    def is_last(self) -> bool:
        return self.page >= self.total_pages


def parse_results_page(html: str, kind: FilingKind) -> ResultsPage:
    tree = HTMLParser(html)
    entries = tree.css("#listaElementosPrimernivel > li")
    if not entries:
        if tree.css_first(_NO_FILINGS) is None:
            raise CNMVParseError(
                "no filings and no 'no data' notice on the page: the CNMV page may have changed"
            )
        return ResultsPage(filings=[], page=1, total_pages=1)
    filings = [_parse_entry(node, kind) for node in entries]
    page, total = _parse_page_info(tree)
    return ResultsPage(filings=filings, page=page, total_pages=total)


def normalize_nif(raw: str) -> str:
    return re.sub(r"[\s\-.]", "", raw).upper()


def _parse_entry(node: Node, kind: FilingKind) -> Filing:
    date = _text(node, "li.fecha-con-hora")
    time = _text(node, "li.time")
    issuer_link = _required(node, "a[id$=hlTituloCabecera]")
    doc_link = _required(node, "a[id$=subtituloRegistroEnlace]")

    registry = next(
        (m for li in node.css("li.resumen") if (m := _REGISTRY.search(li.text(strip=True)))),
        None,
    )
    if registry is None:
        raise CNMVParseError(f"no registry number in entry: {node.text(strip=True)[:120]!r}")

    try:
        registered_at = datetime.strptime(f"{date} {time}", "%d/%m/%Y %H:%M").replace(tzinfo=MADRID)
    except ValueError as e:
        raise CNMVParseError(f"bad date/time {date!r} {time!r}") from e

    raw_nif = _nif_from_href(issuer_link.attributes.get("href") or "")
    return Filing(
        kind=kind,
        registered_at=registered_at,
        issuer=issuer_link.text(strip=True),
        issuer_nif=normalize_nif(raw_nif) if raw_nif else None,
        category=_text(node, "span[id$=descripcionSubtituloCabecera]"),
        title=doc_link.text(strip=True),
        registry_number=int(registry.group(1)),
        document_url=urljoin(_RESULTS_BASE, (doc_link.attributes.get("href") or "").strip()),
        issuer_nif_raw=raw_nif,
    )


def _parse_page_info(tree: HTMLParser) -> tuple[int, int]:
    info = tree.css_first(".PagActivaTXT")
    if info is None:
        return 1, 1  # single page of results: the CNMV shows no paginator
    match = _PAGE_INFO.search(info.text())
    if match is None:
        raise CNMVParseError(f"can't read pagination from {info.text()!r}")
    return int(match.group(1)), int(match.group(2))


def _nif_from_href(href: str) -> str | None:
    match = re.search(r"[?&]nif=([^&]+)", href, flags=re.IGNORECASE)
    return unquote(match.group(1)).strip() if match else None


def _required(node: Node, selector: str) -> Node:
    found = node.css_first(selector)
    if found is None:
        raise CNMVParseError(f"missing {selector!r} in entry: {node.text(strip=True)[:120]!r}")
    return found


def _text(node: Node, selector: str) -> str:
    return _required(node, selector).text(strip=True)


@dataclass(frozen=True, slots=True)
class SecuritiesPage:
    securities: list[Security]
    page: int
    total_pages: int

    @property
    def is_last(self) -> bool:
        return self.page >= self.total_pages


def parse_securities_page(html: str) -> SecuritiesPage:
    tree = HTMLParser(html)
    rows = tree.css("table#ctl00_ContentPrincipal_grdDatos tbody tr")
    if not rows:
        notice = tree.css_first(_NO_SECURITIES)
        text = notice.text().lower() if notice is not None else ""
        if "encontrado" not in text and "not found" not in text:
            raise CNMVParseError(
                "no ISINs and no 'not found' notice on the page: the CNMV page may have changed"
            )
        return SecuritiesPage(securities=[], page=1, total_pages=1)
    securities = []
    for row in rows:
        cells = {
            (td.attributes.get("data-th") or ""): td.text().strip() or None for td in row.css("td")
        }
        isin = cells.get("ISIN")
        if not isin:
            raise CNMVParseError(f"ISIN row without ISIN: {row.text(strip=True)[:120]!r}")
        securities.append(
            Security(
                isin=isin,
                fisn=cells.get("FISN"),
                cfi=cells.get("CFI 2015"),
                currency=cells.get("Moneda"),
                issue_date=_es_date(cells.get("Fecha emisión")),
                maturity_date=_es_date(cells.get("Fecha vencimiento")),
                outstanding=_es_number(cells.get("Nº valores / Saldo emitido")),
                nominal=_es_number(cells.get("Nominal / VMN / Precio")),
                interest_rate=_es_number(cells.get("Interés")),
            )
        )
    page, total = _parse_page_info(tree)
    return SecuritiesPage(securities=securities, page=page, total_pages=total)


def _es_number(text: str | None) -> float | None:
    """ "4.768.462.486,00" -> 4768462486.0"""
    if not text:
        return None
    try:
        return float(text.replace(".", "").replace(",", "."))
    except ValueError as e:
        raise CNMVParseError(f"bad number {text!r}") from e


def _es_date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError as e:
        raise CNMVParseError(f"bad date {text!r}") from e
