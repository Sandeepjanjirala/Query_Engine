from __future__ import annotations

from typing import List, Sequence
import pandas as pd


DEFAULT_JOIN_KEYS = ['AGM', 'RI', 'Zone', 'Branch']


def _create_join_key(df: pd.DataFrame, join_keys: Sequence[str]) -> pd.Series:
    """Create a case-insensitive, whitespace-trimmed normalized composite key."""
    parts = []
    for key in join_keys:
        if key in df.columns:
            s = df[key].astype('string').str.strip().str.casefold().fillna('')
        else:
            s = pd.Series([''] * len(df), index=df.index, dtype='string')
        parts.append(s)
    
    key_series = parts[0]
    for p in parts[1:]:
        key_series = key_series + "||" + p
    return key_series


def join_datasets(
    primary_df: pd.DataFrame,
    secondary_dfs: List[pd.DataFrame],
    join_keys: Sequence[str] = DEFAULT_JOIN_KEYS,
) -> pd.DataFrame:
    """
    Left-join secondary DataFrames onto primary_df using canonical business dimensions
    (AGM, RI, Zone, Branch). Primary rows are preserved even if missing from secondary datasets.
    """
    if not secondary_dfs:
        return primary_df.copy()

    # Determine existing join keys present in primary_df
    actual_keys = [k for k in join_keys if k in primary_df.columns]
    if not actual_keys:
        # Fallback to Branch alone if full keys missing in primary
        actual_keys = ['Branch'] if 'Branch' in primary_df.columns else []

    if not actual_keys:
        # Cannot join without keys
        return primary_df.copy()

    result = primary_df.copy()

    for i, sec_df in enumerate(secondary_dfs):
        if sec_df.empty:
            continue
        
        sec_copy = sec_df.copy()
        
        # Build composite key for matching
        result['__join_key__'] = _create_join_key(result, actual_keys)
        sec_copy['__join_key__'] = _create_join_key(sec_copy, actual_keys)

        # Identify non-key columns in secondary to bring over
        sec_cols_to_keep = [c for c in sec_copy.columns if c not in actual_keys and c != '__join_key__']
        
        # Deduplicate secondary on join key to prevent Cartesian product
        sec_dedup = sec_copy.drop_duplicates(subset=['__join_key__'])[['__join_key__'] + sec_cols_to_keep]

        # Perform LEFT JOIN
        result = pd.merge(result, sec_dedup, on='__join_key__', how='left')
        result.drop(columns=['__join_key__'], inplace=True)

    return result
