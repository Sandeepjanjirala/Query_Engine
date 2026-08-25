from __future__ import annotations

from pathlib import Path

import pandas as pd

from .glossary import (
    AGM_COLUMN,
    BRANCH_COLUMN,
    DROPOUT_PERCENTAGE_COLUMN,
    LEVEL_TOKENS,
    RI_COLUMN,
    STAFF_CATEGORY_TOKENS,
    TYPE_TOKENS,
    YEAR_TOKENS,
    ZONE_COLUMN,
)

REQUIRED_COLUMNS = {BRANCH_COLUMN, DROPOUT_PERCENTAGE_COLUMN}

_IDENTIFIER_COLUMNS = {AGM_COLUMN, RI_COLUMN, ZONE_COLUMN, BRANCH_COLUMN}
_SEGMENT_ONE_TOKENS = set(LEVEL_TOKENS) | set(STAFF_CATEGORY_TOKENS)


def load_excel(path: str | Path, sheet_name: str = 'Sheet1') -> pd.DataFrame:
    """Load branch analytics and validate the source-data contract."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f'Branch analytics Excel file not found: {path}')

    df = pd.read_excel(path, sheet_name=sheet_name)
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f'Missing required columns: {sorted(missing)}')

    df = df.copy()
    df[BRANCH_COLUMN] = df[BRANCH_COLUMN].astype('string').str.strip()
    df[DROPOUT_PERCENTAGE_COLUMN] = pd.to_numeric(
        df[DROPOUT_PERCENTAGE_COLUMN], errors='coerce'
    )
    return df


def _parse_metric_column(column: str) -> tuple[str | None, str | None, str | None, str]:
    """
    Decompose a source column name into its (level_or_staff_category, type,
    year, metric) segments per the LEVEL?-TYPE?-YEAR?-METRIC contract
    documented in glossary.py. Segments that don't apply to a given column
    are None -- e.g. 'CY-DPP' -> (None, None, 'CY', 'DPP'),
    'PP-Avg-SPS' -> ('PP', None, None, 'Avg-SPS'), 'ARCS' -> (None, None, None, 'ARCS').
    """
    tokens = column.split('-')
    pos = 0

    level = None
    if tokens[pos] in _SEGMENT_ONE_TOKENS:
        level = tokens[pos]
        pos += 1

    type_ = None
    if pos < len(tokens) and tokens[pos] in TYPE_TOKENS:
        type_ = tokens[pos]
        pos += 1

    year = None
    if pos < len(tokens) and tokens[pos] in YEAR_TOKENS:
        year = tokens[pos]
        pos += 1

    metric = '-'.join(tokens[pos:])
    return level, type_, year, metric


def build_metric_index(df: pd.DataFrame) -> dict[tuple, str]:
    """
    Build a (level, type, year, metric) -> source-column-name lookup for
    every metric column in `df`, driven entirely by the actual column
    names -- not a hand-maintained list -- so it can never drift from the
    real Excel contract. Identifier columns (AGM/RI/Zone/Branch) are
    excluded since they aren't metrics.
    """
    index: dict[tuple, str] = {}
    for column in df.columns:
        if column in _IDENTIFIER_COLUMNS:
            continue
        level, type_, year, metric = _parse_metric_column(str(column))
        if not metric:
            continue
        index[(level, type_, year, metric)] = column
    return index


def resolve_column(
    index: dict[tuple, str],
    metric: str,
    level: str | None = None,
    type_: str | None = None,
    year: str | None = None,
) -> str | None:
    """
    Look up the source column for (level, type, year, metric) in `index`,
    falling back to progressively less specific keys (dropping type, then
    level) when a metric doesn't support that segment -- e.g. STR/SC/NOS
    never split by type, and room metrics never carry level/type/year.
    Returns None if no matching column exists at all.
    """
    for key in (
        (level, type_, year, metric),
        (level, None, year, metric),
        (None, type_, year, metric),
        (None, None, year, metric),
        (level, None, None, metric),
        (None, None, None, metric),
    ):
        if key in index:
            return index[key]
    return None
