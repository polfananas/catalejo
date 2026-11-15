"""Exceptions and warnings that catalejo raises."""

from __future__ import annotations

from catalejo._http import CNMVRequestError
from catalejo._parse import CNMVParseError


class IncompleteResultsWarning(UserWarning):
    """A search stopped at `max_pages`: the results are missing older entries.

    Turn it into an error with ``warnings.simplefilter("error", IncompleteResultsWarning)``
    or pass ``strict=True``.
    """


class IncompleteResultsError(RuntimeError):
    """Raised instead of :class:`IncompleteResultsWarning` when ``strict=True``."""


__all__ = [
    "CNMVParseError",
    "CNMVRequestError",
    "IncompleteResultsError",
    "IncompleteResultsWarning",
]
