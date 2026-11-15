import asyncio
import json
import warnings
from datetime import date, datetime
from typing import Any

import pytest

pytest.importorskip("mcp")  # optional extra: skip if not installed

import catalejo  # noqa: E402
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

    assert len(out["filings"]) == out["returned"] == 2
    assert out["found"] == 5
    assert out["complete"] is True
    assert "newest 2 of 5" in out["note"]
    assert calls[0]["since"] == date(2023, 1, 1)
    assert calls[0]["issuer"] == "A64907306"


def test_incomplete_search_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_filings(**kwargs: Any) -> list[Filing]:
        warnings.warn("stopped after max_pages=50", catalejo.IncompleteResultsWarning, stacklevel=2)
        return []

    monkeypatch.setattr(mcp_server.catalejo, "filings", fake_filings)
    out = mcp_server.latest_filings(days=3)

    assert out["complete"] is False
    assert "missing" in out["note"]
    assert out["source"].startswith("CNMV")


def test_server_reports_catalejo_version() -> None:
    options = mcp_server.mcp._mcp_server.create_initialization_options()
    assert options.server_version == catalejo.__version__


def test_tool_inputs_are_bounded() -> None:
    tools = {t.name: t.inputSchema for t in asyncio.run(mcp_server.mcp.list_tools())}

    assert tools["latest_filings"]["properties"]["days"]["maximum"] == 14
    assert tools["latest_filings"]["properties"]["limit"]["maximum"] == 200
    assert tools["issuer_filings"]["properties"]["limit"]["minimum"] == 1


def test_out_of_range_input_is_rejected_before_any_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mcp_server.catalejo, "filings", lambda **kw: pytest.fail("no request"))
    with pytest.raises(Exception, match="less than or equal to 14"):
        asyncio.run(mcp_server.mcp.call_tool("latest_filings", {"days": 90}))
