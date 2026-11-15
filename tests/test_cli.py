import csv
import io
import json
import warnings
from datetime import date, datetime
from typing import Any

import pytest

from catalejo import cli
from catalejo._parse import MADRID
from catalejo.errors import IncompleteResultsError, IncompleteResultsWarning
from catalejo.models import Filing, Security

FILING = Filing(
    kind="IP",
    registered_at=datetime(2025, 10, 16, 18, 41, tzinfo=MADRID),
    issuer="BANCO BILBAO VIZCAYA ARGENTARIA, S.A.",
    issuer_nif="A48265169",
    category="Sobre operaciones corporativas",
    title="Resultado de la oferta pública de adquisición sobre Banco de Sabadell",
    registry_number=2898,
    document_url="https://www.cnmv.es/webservices/verdocumento/ver?t=%7babc%7d",
)


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []

    def fake_filings(**kwargs: Any) -> list[Filing]:
        seen.append(kwargs)
        return [FILING] * 3

    monkeypatch.setattr(cli.catalejo, "filings", fake_filings)
    return seen


def test_filings_table(calls: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["filings", "--days", "3", "--kind", "ip"]) == 0

    out = capsys.readouterr().out.splitlines()
    assert len(out) == 3
    assert out[0].startswith("2025-10-16 18:41  IP   BANCO BILBAO")
    assert calls[0]["days"] == 3
    assert calls[0]["kind"] == "IP"


def test_year_shortcuts_and_limit(
    calls: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["filings", "--issuer", "A48265169", "--since", "2020", "--until", "2023"])
    capsys.readouterr()
    cli.main(["filings", "--limit", "1", "--format", "json"])

    assert calls[0]["since"] == date(2020, 1, 1)
    assert calls[0]["until"] == date(2023, 12, 31)
    assert calls[1]["kind"] == "all"
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 1
    assert data[0]["registered_at"] == "2025-10-16T18:41:00+02:00"


def test_filings_csv(calls: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["filings", "--format", "csv"])

    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert len(rows) == 3
    assert rows[0]["registry_number"] == "2898"


def test_bad_date_is_a_usage_error() -> None:
    with pytest.raises(SystemExit):
        cli.main(["filings", "--since", "last year"])


def test_securities_only_shares(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secs = [
        Security(isin="ES0105066007", fisn="CLNX/AC 0.25", cfi="ESVUFB", outstanding=706_429_811),
        Security(isin="XS2300292617", fisn="CLNX/OB 0.75", cfi="DBFTFB"),
    ]
    monkeypatch.setattr(cli.catalejo, "securities", lambda nif, strict=False: secs)

    cli.main(["securities", "A64907306", "--shares"])

    out = capsys.readouterr().out
    assert "ES0105066007" in out
    assert "706,429,811" in out
    assert "XS2300292617" not in out


def test_errors_go_to_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(**kwargs: Any) -> list[Filing]:
        raise ValueError("issuer must not be empty")

    monkeypatch.setattr(cli.catalejo, "filings", boom)

    assert cli.main(["filings", "--issuer", ""]) == 1
    assert "issuer must not be empty" in capsys.readouterr().err


def test_incomplete_results_warn_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_filings(**kwargs: Any) -> list[Filing]:
        warnings.warn("stopped after max_pages=50", IncompleteResultsWarning, stacklevel=2)
        return [FILING]

    monkeypatch.setattr(cli.catalejo, "filings", fake_filings)
    assert cli.main(["filings", "--days", "60"]) == 0

    captured = capsys.readouterr()
    assert "2025-10-16 18:41" in captured.out  # you still get the results
    assert "catalejo: warning: stopped after max_pages=50" in captured.err


def test_strict_fails_on_incomplete_results(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_filings(**kwargs: Any) -> list[Filing]:
        calls.append(kwargs)
        raise IncompleteResultsError("stopped after max_pages=50")

    monkeypatch.setattr(cli.catalejo, "filings", fake_filings)
    assert cli.main(["filings", "--days", "60", "--strict"]) == 1

    assert calls[0]["strict"] is True
    assert "catalejo: stopped after max_pages=50" in capsys.readouterr().err
