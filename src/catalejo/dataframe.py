"""Convert Catalejo dataclasses into pandas DataFrames."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import Any

from catalejo.models import Filing, Security


def to_frame(
    items: Sequence[Filing] | Sequence[Security],
    *,
    model: type[Filing] | type[Security] | None = None,
) -> Any:
    """Convert filings or securities into a pandas DataFrame.

    Pandas is an optional dependency. For an empty sequence, pass
    model=Filing or model=Security to determine the expected columns.
    """
    try:
        import pandas as pd  # type: ignore[import-untyped]
    except ImportError:
        raise ImportError('to_frame() needs pandas: pip install "catalejo[pandas]"') from None

    if model is not None and model not in (Filing, Security):
        raise TypeError("model must be Filing or Security")

    if items:
        item_type = type(items[0])

        if item_type not in (Filing, Security):
            raise TypeError("items must contain Filing or Security instances")

        if any(type(item) is not item_type for item in items):
            raise TypeError("items must contain only one dataclass type")

        if model is not None and model is not item_type:
            raise TypeError("model does not match the items")

    else:
        if model is None:
            raise ValueError(
                "model is required for empty items: use model=Filing or model=Security"
            )
        item_type = model

    columns = [field.name for field in dataclasses.fields(item_type)]
    rows = [dataclasses.asdict(item) for item in items]

    return pd.DataFrame.from_records(rows, columns=columns)
