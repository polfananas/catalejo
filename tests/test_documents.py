import sys
from pathlib import Path

import httpx
import pytest

from catalejo._http import HttpClient
from catalejo.documents import document_text

pytest.importorskip("pypdf")

URL = "https://www.cnmv.es/webservices/verdocumento/ver?t=%7babc%7d"


def tiny_pdf(text: str | None) -> bytes:
    """A minimal one-page PDF, optionally with a line of text."""
    content = f"BT /F1 18 Tf 20 100 Td ({text}) Tj ET" if text else ""
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R"
        " /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out


def make_client(tmp_path: Path, body: bytes, calls: list[int] | None = None) -> HttpClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(1)
        return httpx.Response(200, content=body, headers={"Content-Type": "application/pdf"})

    return HttpClient(cache_dir=tmp_path, transport=httpx.MockTransport(handler), min_interval=0)


def test_extracts_text(tmp_path: Path) -> None:
    client = make_client(tmp_path, tiny_pdf("Resultados 9M 2026"))
    assert document_text(URL, client=client) == "Resultados 9M 2026"


def test_scanned_pdf_without_text_gives_empty_string(tmp_path: Path) -> None:
    client = make_client(tmp_path, tiny_pdf(None))
    assert document_text(URL, client=client) == ""


def test_documents_are_cached_even_with_short_ttl(tmp_path: Path) -> None:
    calls: list[int] = []
    client = make_client(tmp_path, tiny_pdf("x"), calls)
    client.cache_ttl = 0  # listings would not be cached at all...

    document_text(URL, client=client)
    document_text(URL, client=client)
    assert len(calls) == 1  # ...but documents are


def test_non_pdf_is_an_error(tmp_path: Path) -> None:
    client = make_client(tmp_path, b"<html>not found</html>")
    with pytest.raises(ValueError, match="not a PDF"):
        document_text(URL, client=client)


def test_helpful_error_without_pypdf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pypdf", None)
    with pytest.raises(ImportError, match=r"catalejo\[pdf\]"):
        document_text(URL)
