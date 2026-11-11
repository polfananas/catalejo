import json
from datetime import date, datetime
from typing import Any

import pytest

pytest.importorskip("mcp")  # optional extra: skip if not installed

from catalejo import mcp_server  # noqa: E402
from catalejo._parse import MADRID  # noqa: E402
from catalejo.mcp_server import _as_dict  # noqa: E402
from catalejo.models import Filing  # noqa: E402


def test_filing_serializes_to_json() -> None:
    filing = Filing(
        kind="IP",
        registered_at=datetime(2026, 11, 5, 17, 38, tzinfo=MADRID),
        issuer="CELLNEX TELECOM, S.A.",
        issuer_nif="A64907306",
        category="Sobre negocio y situación financiera",
        title="Resultados 9M 2026",
        registry_number=3409,
        document_url="https://www.cnmv.es/webservices/verdocumento/ver?t=%7babc%7d",
    )
    d = _as_dict(filing)

    assert d["registered_at"] == "2026-11-05T17:38:00+01:00"
    assert d["registry_number"] == 3409
    json.dumps(d)  # must not raise


def test_issuer_filings_passes_dates_and_applies_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    fake = Filing(
        kind="IP",
        registered_at=datetime(2024, 3, 1, 9, 0, tzinfo=MADRID),
        issuer="CELLNEX TELECOM, S.A.",
        issuer_nif="A64907306",
        category="",
        title="",
        registry_number=1,
        document_url="",
    )

    def fake_filings(**kwargs: Any) -> list[Filing]:
        calls.append(kwargs)
        return [fake] * 5

    monkeypatch.setattr(mcp_server.catalejo, "filings", fake_filings)
    out = mcp_server.issuer_filings("A64907306", since=date(2023, 1, 1), limit=2)

    assert len(out) == 2
    assert calls[0]["since"] == date(2023, 1, 1)
    assert calls[0]["issuer"] == "A64907306"
