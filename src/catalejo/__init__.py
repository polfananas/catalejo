"""catalejo: Spanish CNMV public data, made usable."""

__version__ = "0.1.2"

from catalejo.documents import document_text
from catalejo.errors import (
    CNMVParseError,
    CNMVRequestError,
    IncompleteResultsError,
    IncompleteResultsWarning,
)
from catalejo.filings import filings
from catalejo.models import Filing, Security
from catalejo.securities import securities

__all__ = [
    "CNMVParseError",
    "CNMVRequestError",
    "Filing",
    "IncompleteResultsError",
    "IncompleteResultsWarning",
    "Security",
    "document_text",
    "filings",
    "securities",
]
