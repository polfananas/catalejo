"""catalejo: Spanish CNMV public data, made usable."""

__version__ = "0.0.1"

from catalejo.filings import filings
from catalejo.models import Filing

__all__ = ["Filing", "filings"]
