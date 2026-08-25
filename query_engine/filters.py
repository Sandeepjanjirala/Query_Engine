"""
Centralized filter-context application layer.

Every pre-function scopes its calculation to the dashboard's current
AGM/RI/Branch selection by calling apply_filter_context(df, context)
before running its own analytics -- so this filtering logic is written
once here, not duplicated per function.
"""
from __future__ import annotations

import pandas as pd

from .glossary import AGM_COLUMN, BRANCH_COLUMN, RI_COLUMN, ZONE_COLUMN


def _is_all(value) -> bool:
    """True if `value` means "no filter" (missing, blank, or literal "All")."""
    return value is None or str(value).strip() == '' or str(value).strip().casefold() == 'all'


def _match_column(df: pd.DataFrame, column: str, value: str) -> pd.DataFrame:
    return df[df[column].astype('string').str.strip().str.casefold() == str(value).strip().casefold()]


def apply_filter_context(df: pd.DataFrame, context: dict | None) -> pd.DataFrame:
    """
    Return a new DataFrame scoped to context's agm/ri/branches, matching
    case-insensitively and whitespace-trimmed. "All" (or missing/blank) on
    any field means no filter for that field. A DataFrame missing a given
    identifier column (e.g. a synthetic/test df) simply skips that filter
    instead of raising. Never mutates the input df.
    """
    context = context or {}
    result = df

    agm = context.get('agm')
    if not _is_all(agm) and AGM_COLUMN in result.columns:
        result = _match_column(result, AGM_COLUMN, agm)

    ri = context.get('ri')
    if not _is_all(ri) and RI_COLUMN in result.columns:
        result = _match_column(result, RI_COLUMN, ri)

    zone = context.get('zone')
    if not _is_all(zone) and ZONE_COLUMN in result.columns:
        result = _match_column(result, ZONE_COLUMN, zone)

    branches = [b for b in (context.get('branches') or []) if not _is_all(b)]
    if branches and BRANCH_COLUMN in result.columns:
        wanted = {str(b).strip().casefold() for b in branches}
        result = result[result[BRANCH_COLUMN].astype('string').str.strip().str.casefold().isin(wanted)]

    return result.copy()
