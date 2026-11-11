"""Text of the documents attached to filings (PDFs)."""

from __future__ import annotations

import io
import math

from catalejo._http import HttpClient
from catalejo.filings import _default_client
from catalejo.models import Filing


def document_text(filing: Filing | str, *, client: HttpClient | None = None) -> str:
    """Plain text of a filing's PDF (or of a document URL).

    Needs the optional dependency: ``pip install "catalejo[pdf]"``.
    Documents never change, so they're cached forever after the first download.
    Scanned PDFs have no text layer and return "".
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError('document_text() needs pypdf: pip install "catalejo[pdf]"') from None

    url = filing.document_url if isinstance(filing, Filing) else filing
    response = (client or _default_client()).get(url, ttl=math.inf)
    if not response.content.startswith(b"%PDF"):
        raise ValueError(f"not a PDF ({response.content_type or 'unknown type'}): {url}")

    reader = PdfReader(io.BytesIO(response.content))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
