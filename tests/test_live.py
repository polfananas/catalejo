"""Checks against the real CNMV website.

Skipped unless ``CATALEJO_LIVE=1``. They run every week in CI
(``.github/workflows/live.yml``) to catch changes in the CNMV pages before users
do. To run them locally:

    CATALEJO_LIVE=1 pytest tests/test_live.py -v
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

import catalejo

pytestmark = pytest.mark.skipif(
    os.environ.get("CATALEJO_LIVE") != "1",
    reason="live checks against the CNMV: set CATALEJO_LIVE=1",
)

BBVA = "A48265169"
CELLNEX = "A64907306"
CELLNEX_SHARE = "ES0105066007"


def _check_filing(f: catalejo.Filing) -> None:
    assert f.kind in ("IP", "OIR")
    assert f.registered_at.tzinfo is not None
    assert f.registry_number > 0
    assert f.issuer.strip()
    assert f.title.strip()
    assert f.document_url.startswith("https://www.cnmv.es/")


def test_recent_filings() -> None:
    # Both kinds over two weeks: there's always something, even around holidays.
    filings = catalejo.filings(days=14)
    assert filings, "no filings in 14 days: the listing pages may have changed"
    for f in filings:
        _check_filing(f)
    times = [f.registered_at for f in filings]
    assert times == sorted(times, reverse=True), "filings are not newest first"


def test_filings_by_nif() -> None:
    filings = catalejo.filings(issuer=BBVA, since=date.today() - timedelta(days=365))
    assert filings, "no BBVA filings in a year: filtering by NIF may have broken"
    assert all(f.issuer_nif == BBVA for f in filings)


def test_securities() -> None:
    securities = catalejo.securities(CELLNEX)
    assert any(s.isin == CELLNEX_SHARE and s.is_share for s in securities)


def test_document_text() -> None:
    pytest.importorskip("pypdf")
    # Some documents are scanned and have no text, so try a few.
    filings = catalejo.filings(days=14, kind="IP")[:5]
    assert filings
    texts = [catalejo.document_text(f) for f in filings]
    assert any(len(t) > 100 for t in texts), "no text in the latest IP documents"
