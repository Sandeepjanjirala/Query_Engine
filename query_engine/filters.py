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


import re


def _clean_str(val: str) -> str:
    if not val:
        return ""
    s = str(val).lower().strip()
    s = re.sub(r'^(mr\.|mr\s+|mrs\.|mrs\s+|dr\.|dr\s+)', '', s)
    s = re.sub(r'[._\-,]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _match_column(df: pd.DataFrame, column: str, value: str) -> pd.DataFrame:
    col_series = df[column].astype('string').str.strip().str.casefold()
    target = str(value).strip().casefold()
    mask = col_series == target
    if not mask.any():
        clean_col = df[column].dropna().astype(str).map(_clean_str)
        clean_target = _clean_str(value)
        mask = clean_col == clean_target
    return df[mask]


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
