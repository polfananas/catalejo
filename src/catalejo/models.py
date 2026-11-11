"""Data models returned by catalejo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from urllib.parse import parse_qs, urlsplit

FilingKind = Literal["IP", "OIR"]
"""``IP`` = información privilegiada (inside information, art. 17 MAR).
``OIR`` = otra información relevante (other relevant information)."""


@dataclass(frozen=True, slots=True)
class Filing:
    """One disclosure published by an issuer through the CNMV."""

    kind: FilingKind
    registered_at: datetime
    """When the CNMV registered it (timezone-aware, Europe/Madrid)."""
    issuer: str
    issuer_nif: str | None
    """Spanish tax id of the issuer, without dashes. Foreign issuers get an N-prefixed NIF."""
    category: str
    """Category as shown by the CNMV, in Spanish (e.g. "Sobre gobierno corporativo")."""
    title: str
    registry_number: int
    """Official registry number. IP and OIR are numbered separately."""
    document_url: str
    """Link to the filed document (usually a PDF)."""
    issuer_nif_raw: str | None = None
    """NIF exactly as the CNMV writes it (sometimes "A-28004885"). Needed to query by issuer."""

    @property
    def document_id(self) -> str | None:
        """The GUID the CNMV uses to identify the document, if present in the URL."""
        values = parse_qs(urlsplit(self.document_url).query).get("t")
        return values[0].strip("{}") if values else None


@dataclass(frozen=True, slots=True)
class Security:
    """A security registered under an issuer at the CNMV's ISIN agency (ANCV)."""

    isin: str
    fisn: str | None
    """Short name, e.g. "CLNX/AC 0.25" (AC = acciones / shares, OB = bonds)."""
    cfi: str | None
    """ISO 10962 classification. Shares start with "ES". Empty for most foreign issuers."""
    currency: str | None = None
    issue_date: date | None = None
    maturity_date: date | None = None
    outstanding: float | None = None
    """Number of securities (shares) or amount issued (debt)."""
    nominal: float | None = None
    interest_rate: float | None = None

    @property
    def is_share(self) -> bool:
        return (self.cfi or "").startswith("ES")
