from datetime import datetime

import pytest

import catalejo
from catalejo._parse import MADRID
from catalejo.models import Filing, Security

pd = pytest.importorskip("pandas")


def make_filing() -> Filing:
    return Filing(
        kind="IP",
        registered_at=datetime(2026, 11, 6, 12, 0, tzinfo=MADRID),
        issuer="CELLNEX TELECOM, S.A.",
        issuer_nif="A64907306",
        category="",
        title="Test filing",
        registry_number=123,
        document_url="https://example.com/document.pdf",
    )


def make_security() -> Security:
    return Security(
        isin="ES0105066007",
        fisn="CLNX/AC 0.25",
        cfi="ESVUFB",
        currency="EUR",
    )


def test_to_frame_filings() -> None:
    df = catalejo.to_frame([make_filing()])

    assert list(df.columns) == [
        "kind",
        "registered_at",
        "issuer",
        "issuer_nif",
        "category",
        "title",
        "registry_number",
        "document_url",
        "issuer_nif_raw",
    ]
    assert len(df) == 1
    assert df.iloc[0]["issuer"] == "CELLNEX TELECOM, S.A."
    assert str(df["registered_at"].dt.tz) == "Europe/Madrid"


def test_to_frame_securities() -> None:
    df = catalejo.to_frame([make_security()])

    assert list(df.columns) == [
        "isin",
        "fisn",
        "cfi",
        "currency",
        "issue_date",
        "maturity_date",
        "outstanding",
        "nominal",
        "interest_rate",
    ]
    assert len(df) == 1
    assert df.iloc[0]["isin"] == "ES0105066007"


def test_to_frame_empty_filings() -> None:
    df = catalejo.to_frame([], model=Filing)

    assert df.empty
    assert list(df.columns) == [
        "kind",
        "registered_at",
        "issuer",
        "issuer_nif",
        "category",
        "title",
        "registry_number",
        "document_url",
        "issuer_nif_raw",
    ]


def test_to_frame_empty_securities() -> None:
    df = catalejo.to_frame([], model=Security)

    assert df.empty
    assert "isin" in df.columns
    assert "maturity_date" in df.columns


def test_empty_items_require_model() -> None:
    with pytest.raises(ValueError, match="model is required"):
        catalejo.to_frame([])


def test_mixed_dataclasses_are_rejected() -> None:
    with pytest.raises(TypeError, match="only one dataclass type"):
        catalejo.to_frame([make_filing(), make_security()])
