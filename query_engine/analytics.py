from __future__ import annotations

import re
import pandas as pd

from .glossary import (
    AGM_COLUMN,
    BRANCH_COLUMN,
    DROPOUT_PERCENTAGE_COLUMN,
    RI_COLUMN,
    ZONE_COLUMN,
)


# ---------------------------------------------------------------------------
# Reusable analytics primitives.
#
# All query capabilities are thin orchestration layers around these
# parameter-driven analytics functions. None of them are aware of natural
# language -- they take resolved column names and operate on whatever
# DataFrame apply_filter_context() produced.
# ---------------------------------------------------------------------------


def _resolve_cy_ly_cols(df: pd.DataFrame, column: str) -> tuple[str | None, str | None]:
    """Helper to resolve Current Year (CY) and Last Year (LY) column names in df."""
    if column in df.columns:
        if column.startswith('CY-') or column.startswith('CY_'):
            ly = column.replace('CY-', 'LY-').replace('CY_', 'LY_')
            return column, ly if ly in df.columns else None
        if column.startswith('LY-') or column.startswith('LY_'):
            cy = column.replace('LY-', 'CY-').replace('LY_', 'CY_')
            return cy if cy in df.columns else column, column

    cy = f"CY-{column}" if f"CY-{column}" in df.columns else (f"CY_{column}" if f"CY_{column}" in df.columns else (column if column in df.columns else None))
    ly = f"LY-{column}" if f"LY-{column}" in df.columns else (f"LY_{column}" if f"LY_{column}" in df.columns else None)

    if cy is None and column in df.columns:
        cy = column
    return cy, ly


def rank_branches_by_metric(
    df: pd.DataFrame, column: str, n: int | None = 5, ascending: bool = False
) -> list[dict]:
    """Top/bottom-N branches by any single numeric metric column."""
    cy_col, ly_col = _resolve_cy_ly_cols(df, column)

    work = df.copy()
    col_to_sort = cy_col or column
    if col_to_sort not in work.columns:
        col_to_sort = column
    if col_to_sort not in work.columns:
        return []

    work[col_to_sort] = pd.to_numeric(work[col_to_sort], errors='coerce')
    work = work.dropna(subset=[BRANCH_COLUMN, col_to_sort])
    work = work[work[BRANCH_COLUMN].str.len() > 0]
    work = work.sort_values(
        [col_to_sort, BRANCH_COLUMN], ascending=[ascending, True], kind='stable'
    )
    if n is not None and n > 0:
        work = work.head(n)

    results = []
    for rank, (_, row) in enumerate(work.iterrows(), start=1):
        cy_val = float(row[cy_col]) if (cy_col and cy_col in row.index and not pd.isna(row[cy_col])) else float(row[col_to_sort])
        ly_val = float(row[ly_col]) if (ly_col and ly_col in row.index and not pd.isna(row[ly_col])) else 0.0
        diff = cy_val - ly_val
        results.append({
            'rank': rank,
            'branch': str(row[BRANCH_COLUMN]),
            'current_year': round(cy_val, 2),
            'previous_year': round(ly_val, 2),
            'difference': round(diff, 2),
            'value': round(float(row[col_to_sort]), 2),
        })
    return results


def lookup_branch_metrics(
    df: pd.DataFrame, columns: list[str], branches: list[str] | None = None
) -> list[dict]:
    """One or more metric columns for one, several, or all branches."""
    work = df
    if branches:
        wanted = {str(b).strip().casefold() for b in branches}
        work = work[
            work[BRANCH_COLUMN].astype('string').str.strip().str.casefold().isin(wanted)
        ]

    results = []
    for _, row in work.iterrows():
        entry: dict = {'branch': str(row[BRANCH_COLUMN])}
        for column in columns:
            col_to_use = column
            if col_to_use not in row.index:
                cy_col, ly_col = _resolve_cy_ly_cols(df, column)
                if cy_col and cy_col in row.index:
                    col_to_use = cy_col
            if col_to_use not in row.index:
                entry[column] = None
                continue
            value = row[col_to_use]
            entry[column] = None if pd.isna(value) else round(float(value), 2)
        results.append(entry)
    return results


def aggregate_by_group(
    df: pd.DataFrame,
    group_column: str,
    value_column: str,
    agg: str = 'sum',
    n: int | None = None,
    ascending: bool = False,
) -> list[dict]:
    """Sum/mean/count/derived of a metric column grouped by an org dimension column."""
    from .metric_registry import get_default_metric_registry
    registry = get_default_metric_registry()
    spec = registry.get(value_column)

    cy_col, ly_col = _resolve_cy_ly_cols(df, value_column)

    if spec and spec.metric_type == 'derived' and spec.numerator_metric and spec.denominator_metric:
        num_col = spec.numerator_metric
        den_col = spec.denominator_metric

        cy_num, ly_num = _resolve_cy_ly_cols(df, num_col)
        cy_den, ly_den = _resolve_cy_ly_cols(df, den_col)

        if cy_num and cy_den and cy_num in df.columns and cy_den in df.columns:
            cols_needed = [group_column, cy_num, cy_den]
            if ly_num and ly_den and ly_num in df.columns and ly_den in df.columns:
                cols_needed.extend([ly_num, ly_den])

            work = df[cols_needed].copy()
            work[cy_num] = pd.to_numeric(work[cy_num], errors='coerce')
            work[cy_den] = pd.to_numeric(work[cy_den], errors='coerce')
            if ly_num and ly_num in work.columns:
                work[ly_num] = pd.to_numeric(work[ly_num], errors='coerce')
            if ly_den and ly_den in work.columns:
                work[ly_den] = pd.to_numeric(work[ly_den], errors='coerce')

            work = work.dropna(subset=[group_column])

            cy_n_sum = work.groupby(group_column, dropna=False)[cy_num].sum()
            cy_d_sum = work.groupby(group_column, dropna=False)[cy_den].sum()
            valid_cy_d = cy_d_sum.replace(0, pd.NA)
            cy_series = (cy_n_sum / valid_cy_d) * (100.0 if spec.data_type == 'percentage' else 1.0)

            if ly_num and ly_den and ly_num in work.columns and ly_den in work.columns:
                ly_n_sum = work.groupby(group_column, dropna=False)[ly_num].sum()
                ly_d_sum = work.groupby(group_column, dropna=False)[ly_den].sum()
                valid_ly_d = ly_d_sum.replace(0, pd.NA)
                ly_series = (ly_n_sum / valid_ly_d) * (100.0 if spec.data_type == 'percentage' else 1.0)
            else:
                ly_series = pd.Series(0.0, index=cy_series.index)

            sorted_keys = cy_series.dropna().sort_values(ascending=ascending).index
            if n is not None and n > 0:
                sorted_keys = sorted_keys[:n]

            results = []
            for key in sorted_keys:
                c_val = round(float(cy_series.get(key, 0.0)), 2)
                l_val = round(float(ly_series.get(key, 0.0)), 2)
                results.append({
                    'group': str(key),
                    'current_year': c_val,
                    'previous_year': l_val,
                    'difference': round(c_val - l_val, 2),
                    'value': c_val,
                })
            return results

    work = df.copy()
    val_col = cy_col or value_column
    if val_col not in work.columns:
        val_col = value_column
    if val_col not in work.columns:
        return []

    cols_to_use = [group_column, val_col]
    if ly_col and ly_col in work.columns and ly_col != val_col:
        cols_to_use.append(ly_col)

    work = work[cols_to_use].copy()
    work[val_col] = pd.to_numeric(work[val_col], errors='coerce')
    if ly_col and ly_col in work.columns:
        work[ly_col] = pd.to_numeric(work[ly_col], errors='coerce')
    work = work.dropna(subset=[group_column])

    grouped = work.groupby(group_column, dropna=False)
    if agg == 'mean' or (spec and spec.data_type == 'percentage'):
        cy_series = grouped[val_col].mean()
        ly_series = grouped[ly_col].mean() if (ly_col and ly_col in work.columns) else pd.Series(0.0, index=cy_series.index)
    elif agg == 'count':
        cy_series = grouped[val_col].count()
        ly_series = grouped[ly_col].count() if (ly_col and ly_col in work.columns) else pd.Series(0.0, index=cy_series.index)
    else:
        cy_series = grouped[val_col].sum()
        ly_series = grouped[ly_col].sum() if (ly_col and ly_col in work.columns) else pd.Series(0.0, index=cy_series.index)

    sorted_keys = cy_series.dropna().sort_values(ascending=ascending).index
    if n is not None and n > 0:
        sorted_keys = sorted_keys[:n]

    results = []
    for key in sorted_keys:
        c_val = round(float(cy_series.get(key, 0.0)), 2)
        l_val = round(float(ly_series.get(key, 0.0)), 2) if ly_col in work.columns else 0.0
        results.append({
            'group': str(key),
            'current_year': c_val,
            'previous_year': l_val,
            'difference': round(c_val - l_val, 2),
            'value': c_val,
        })
    return results


def year_over_year_ranking(
    df: pd.DataFrame,
    cy_column: str,
    ly_column: str,
    n: int | None = 5,
    ascending: bool = False,
    sort_by: str = 'change',
) -> list[dict]:
    """Branches ranked by CY-minus-LY change on a metric that has both a CY and LY column."""
    work = df[[BRANCH_COLUMN, cy_column, ly_column]].copy()
    work[cy_column] = pd.to_numeric(work[cy_column], errors='coerce')
    work[ly_column] = pd.to_numeric(work[ly_column], errors='coerce')
    work = work.dropna(subset=[BRANCH_COLUMN, cy_column, ly_column])
    work['change'] = work[cy_column] - work[ly_column]

    if sort_by == 'absolute':
        work['abs_change'] = work['change'].abs()
        work = work.sort_values(
            ['abs_change', BRANCH_COLUMN], ascending=[False, True], kind='stable'
        )
    elif sort_by == 'none':
        work = work.sort_values([BRANCH_COLUMN], ascending=[True], kind='stable')
    else:
        work = work.sort_values(
            ['change', BRANCH_COLUMN], ascending=[ascending, True], kind='stable'
        )

    if n is not None and n > 0:
        work = work.head(n)

    return [
        {
            'rank': rank,
            'branch': str(row[BRANCH_COLUMN]),
            'current_year': round(float(row[cy_column]), 2),
            'last_year': round(float(row[ly_column]), 2),
            'change': round(float(row['change']), 2),
        }
        for rank, (_, row) in enumerate(work.iterrows(), start=1)
    ]


def filter_by_threshold(
    df: pd.DataFrame,
    column: str | None = None,
    op: str = 'gt',
    threshold: float = 0.0,
    count_only: bool = False,
    group_column: str | None = None,
    agg: str = 'mean',
    custom_series: pd.Series | None = None,
) -> dict:
    """Filter branches or groups where value satisfies the comparison op and threshold."""
    if group_column:
        work = df[[group_column, column]].copy()
        work[column] = pd.to_numeric(work[column], errors='coerce')
        work = work.dropna(subset=[group_column, column])
        grouped = work.groupby(group_column)[column]
        series = grouped.mean() if agg == 'mean' else grouped.sum()
        if op in ('>', 'gt'):
            matches = series[series > threshold]
        elif op in ('>=', 'gte'):
            matches = series[series >= threshold]
        elif op in ('<', 'lt'):
            matches = series[series < threshold]
        elif op in ('<=', 'lte'):
            matches = series[series <= threshold]
        else:
            matches = series[series == threshold]

        cy_col, ly_col = _resolve_cy_ly_cols(df, column if column else '')
        ly_series = work.groupby(group_column)[ly_col].mean() if (ly_col and ly_col in work.columns and agg == 'mean') else (work.groupby(group_column)[ly_col].sum() if (ly_col and ly_col in work.columns) else pd.Series(0.0, index=series.index))

        records = []
        for k, v in matches.sort_values(ascending=False).items():
            cy_val = round(float(v), 2)
            ly_val = round(float(ly_series.get(k, 0.0)), 2)
            records.append({
                'group': str(k),
                'current_year': cy_val,
                'previous_year': ly_val,
                'difference': round(cy_val - ly_val, 2),
                'value': cy_val,
            })
        return {
            'count': len(records),
            'threshold': threshold,
            'op': op,
            'count_only': count_only,
            'group_column': group_column,
            'records': records,
        }

    work = df.copy()
    cy_col, ly_col = _resolve_cy_ly_cols(df, column if column else '')
    if custom_series is not None:
        work['_val'] = custom_series
        col_to_use = '_val'
    else:
        work[column] = pd.to_numeric(work[column], errors='coerce')
        col_to_use = column

    work = work.dropna(subset=[BRANCH_COLUMN, col_to_use])
    if op in ('>', 'gt'):
        matched = work[work[col_to_use] > threshold]
    elif op in ('>=', 'gte'):
        matched = work[work[col_to_use] >= threshold]
    elif op in ('<', 'lt'):
        matched = work[work[col_to_use] < threshold]
    elif op in ('<=', 'lte'):
        matched = work[work[col_to_use] <= threshold]
    else:
        matched = work[work[col_to_use] == threshold]

    matched = matched.sort_values([col_to_use, BRANCH_COLUMN], ascending=[False, True])
    records = []
    for rank, (_, row) in enumerate(matched.iterrows(), start=1):
        cy_val = float(row[cy_col]) if (cy_col and cy_col in row.index and not pd.isna(row[cy_col])) else float(row[col_to_use])
        ly_val = float(row[ly_col]) if (ly_col and ly_col in row.index and not pd.isna(row[ly_col])) else 0.0
        diff = cy_val - ly_val
        records.append({
            'rank': rank,
            'branch': str(row[BRANCH_COLUMN]),
            'current_year': round(cy_val, 2),
            'previous_year': round(ly_val, 2),
            'difference': round(diff, 2),
            'value': round(float(row[col_to_use]), 2),
        })
    return {
        'count': len(records),
        'threshold': threshold,
        'op': op,
        'count_only': count_only,
        'records': records,
    }


def compare_dimensions(
    df: pd.DataFrame,
    columns_map: dict[str, str],
    group_column: str | None = None,
    agg: str = 'sum',
    top: str | None = None,
    yoy_pairs: dict[str, tuple[str, str]] | None = None,
    kpi_direction: str = 'positive',
) -> dict:
    """
    Compare metrics across categories (Levels PP/PS/HS, Types Existing/New, Rooms Occupied/Empty,
    or Group CY vs LY).
    """
    if yoy_pairs:
        from .metric_registry import get_default_metric_registry
        registry = get_default_metric_registry()

        results = []
        is_negative_kpi = kpi_direction == 'negative'

        for cat, (cy_col, ly_col) in yoy_pairs.items():
            if cy_col not in df.columns or ly_col not in df.columns:
                continue

            cy_spec = registry.get(cy_col) or registry.get(f"{cat}_DPP") or registry.get(f"{cat}_SAL_V_REV")

            cy_res = None
            ly_res = None
            if cy_spec and cy_spec.metric_type == 'derived' and cy_spec.numerator_metric and cy_spec.denominator_metric:
                num_col = cy_spec.numerator_metric
                den_col = cy_spec.denominator_metric
                if num_col in df.columns and den_col in df.columns:
                    n_sum = pd.to_numeric(df[num_col], errors='coerce').sum()
                    d_sum = pd.to_numeric(df[den_col], errors='coerce').sum()
                    if d_sum > 0:
                        cy_res = (n_sum / d_sum) * (100.0 if cy_spec.data_type == 'percentage' else 1.0)

            if cy_res is None:
                cy_val = pd.to_numeric(df[cy_col], errors='coerce').dropna()
                cy_res = cy_val.mean() if agg == 'mean' or 'dpp' in cy_col.lower() or 'pct' in cy_col.lower() else cy_val.sum()

            if ly_res is None:
                ly_val = pd.to_numeric(df[ly_col], errors='coerce').dropna()
                ly_res = ly_val.mean() if agg == 'mean' or 'dpp' in ly_col.lower() or 'pct' in ly_col.lower() else ly_val.sum()

            diff = cy_res - ly_res
            results.append({
                'category': cat,
                'current_year': round(float(cy_res), 2),
                'previous_year': round(float(ly_res), 2),
                'last_year': round(float(ly_res), 2),
                'difference': round(float(diff), 2),
                'change': round(float(diff), 2),
                'value': round(float(cy_res), 2),
            })

        if top == 'highest_improvement' or top == 'improved':
            sorted_res = sorted(results, key=lambda x: x['change'], reverse=not is_negative_kpi)
            winner = sorted_res[0] if sorted_res else None
            return {'comparison_type': 'yoy_breakdown', 'data': results, 'winner': winner, 'top_type': 'improved'}
        if top == 'highest_decline' or top == 'declined':
            sorted_res = sorted(results, key=lambda x: x['change'], reverse=is_negative_kpi)
            winner = sorted_res[0] if sorted_res else None
            return {'comparison_type': 'yoy_breakdown', 'data': results, 'winner': winner, 'top_type': 'declined'}
        return {'comparison_type': 'yoy_breakdown', 'data': results, 'winner': None}

    if group_column:
        groups = df[group_column].dropna().unique()
        data = []
        for g in sorted(groups):
            g_df = df[df[group_column] == g]
            row = {'group': str(g)}
            for label, col in columns_map.items():
                if col in g_df.columns:
                    val = pd.to_numeric(g_df[col], errors='coerce').dropna()
                    row[label] = round(float(val.mean() if agg == 'mean' else val.sum()), 2)
                else:
                    row[label] = 0.0
            data.append(row)
        return {'comparison_type': 'grouped', 'group_column': group_column, 'data': data}

    data = []
    for label, col in columns_map.items():
        if col in df.columns:
            cy_col, ly_col = _resolve_cy_ly_cols(df, col)
            cy_val = pd.to_numeric(df[cy_col], errors='coerce').dropna() if cy_col and cy_col in df.columns else pd.to_numeric(df[col], errors='coerce').dropna()
            cy_calc = cy_val.mean() if agg == 'mean' else cy_val.sum()

            ly_calc = 0.0
            if ly_col and ly_col in df.columns:
                ly_val = pd.to_numeric(df[ly_col], errors='coerce').dropna()
                ly_calc = ly_val.mean() if agg == 'mean' else ly_val.sum()

            diff = cy_calc - ly_calc
            data.append({
                'category': label,
                'current_year': round(float(cy_calc), 2),
                'previous_year': round(float(ly_calc), 2),
                'last_year': round(float(ly_calc), 2),
                'difference': round(float(diff), 2),
                'change': round(float(diff), 2),
                'value': round(float(cy_calc), 2),
            })
        else:
            data.append({
                'category': label,
                'current_year': 0.0,
                'previous_year': 0.0,
                'last_year': 0.0,
                'difference': 0.0,
                'change': 0.0,
                'value': 0.0,
            })

    winner = None
    if top == 'highest':
        sorted_d = sorted(data, key=lambda x: x['current_year'], reverse=True)
        winner = sorted_d[0] if sorted_d else None
        return {'comparison_type': 'category_breakdown', 'data': data, 'winner': winner, 'top_kind': 'highest'}
    elif top == 'lowest':
        sorted_d = sorted(data, key=lambda x: x['current_year'])
        winner = sorted_d[0] if sorted_d else None
        return {'comparison_type': 'category_breakdown', 'data': data, 'winner': winner, 'top_kind': 'lowest'}

    return {'comparison_type': 'category_breakdown', 'data': data, 'winner': winner}


def calculate_room_ratio(
    df: pd.DataFrame,
    ratio_type: str = 'occupancy',
    n: int | None = None,
    ascending: bool | None = None,
) -> list[dict]:
    """Calculate room occupancy percentage or vacancy percentage by branch."""
    work = df[[BRANCH_COLUMN, 'NOCR', 'NOOR', 'NOVR']].copy()
    work['NOCR'] = pd.to_numeric(work['NOCR'], errors='coerce').fillna(0)
    work['NOOR'] = pd.to_numeric(work['NOOR'], errors='coerce').fillna(0)
    work['NOVR'] = pd.to_numeric(work['NOVR'], errors='coerce').fillna(0)
    work = work.dropna(subset=[BRANCH_COLUMN])

    if ratio_type == 'occupancy':
        work['percentage'] = work.apply(
            lambda r: (r['NOOR'] / r['NOCR'] * 100) if r['NOCR'] > 0 else 0.0, axis=1
        )
    else:
        work['percentage'] = work.apply(
            lambda r: (r['NOVR'] / r['NOCR'] * 100) if r['NOCR'] > 0 else 0.0, axis=1
        )

    if ascending is not None:
        work = work.sort_values(
            ['percentage', BRANCH_COLUMN], ascending=[ascending, True], kind='stable'
        )
    else:
        work = work.sort_values([BRANCH_COLUMN], ascending=[True], kind='stable')

    if n is not None and n > 0:
        work = work.head(n)

    return [
        {
            'rank': rank,
            'branch': str(row[BRANCH_COLUMN]),
            'nocr': int(row['NOCR']),
            'noor': int(row['NOOR']),
            'novr': int(row['NOVR']),
            'percentage': round(float(row['percentage']), 2),
            'current_year': round(float(row['percentage']), 2),
            'previous_year': 0.0,
            'difference': round(float(row['percentage']), 2),
        }
        for rank, (_, row) in enumerate(work.iterrows(), start=1)
    ]


def aggregate_metric_total(df: pd.DataFrame, column: str, agg: str = 'sum') -> float:
    """Calculate overall total or average of a column across the filtered DataFrame."""
    val = pd.to_numeric(df[column], errors='coerce').dropna()
    if val.empty:
        return 0.0
    return round(float(val.mean() if agg == 'mean' else val.sum()), 2)


def top_5_dropout_branches(df: pd.DataFrame) -> list[dict]:
    """Return the five branches with the highest CY-DPP."""
    cy_col, ly_col = _resolve_cy_ly_cols(df, DROPOUT_PERCENTAGE_COLUMN)
    work = df.copy()
    col_to_use = cy_col or DROPOUT_PERCENTAGE_COLUMN
    work = work.dropna(subset=[BRANCH_COLUMN, col_to_use])
    work = work[work[BRANCH_COLUMN].str.len() > 0]
    work = work.sort_values(
        [col_to_use, BRANCH_COLUMN],
        ascending=[False, True],
        kind='stable',
    ).head(5)

    results = []
    for rank, (_, row) in enumerate(work.iterrows(), start=1):
        cy_val = float(row[col_to_use])
        ly_val = float(row[ly_col]) if (ly_col and ly_col in row.index and not pd.isna(row[ly_col])) else 0.0
        diff = cy_val - ly_val
        results.append({
            'rank': rank,
            'branch': str(row[BRANCH_COLUMN]),
            'dropout_percentage': round(cy_val, 2),
            'current_year': round(cy_val, 2),
            'previous_year': round(ly_val, 2),
            'difference': round(diff, 2),
        })
    return results


# ---------------------------------------------------------------------------
# Fee Due analytics primitives
# ---------------------------------------------------------------------------

_FEE_SUMMARY_COLS = ['CY_A_FD', 'LY_FD', 'CY_A_FDC', 'LY_FDC', 'CY_ZP', 'CY_ZP_FD']
_FEE_BOOKS_COLS   = ['CY_FP_BN', 'CY_FN_BN']


def _resolve_group_column(df: pd.DataFrame, group_col: str | None) -> tuple[str, str]:
    """Resolves group_col string to actual dataframe column and key label."""
    if not group_col:
        return BRANCH_COLUMN, 'branch'
    g = str(group_col).strip().lower()
    if g in ('zone',):
        col = ZONE_COLUMN if ZONE_COLUMN in df.columns else ('Zone' if 'Zone' in df.columns else group_col)
        return col, 'zone'
    if g in ('ri', 'ri name', 'ri_name'):
        col = RI_COLUMN if RI_COLUMN in df.columns else ('RI Name' if 'RI Name' in df.columns else ('RI' if 'RI' in df.columns else group_col))
        return col, 'ri'
    if g in ('agm', 'agm name', 'agm_name'):
        col = AGM_COLUMN if AGM_COLUMN in df.columns else ('AGM Name' if 'AGM Name' in df.columns else ('AGM' if 'AGM' in df.columns else group_col))
        return col, 'agm'
    if g in ('s_type', 'branch type', 'type', 's type', 'admission type'):
        col = 'S_Type' if 'S_Type' in df.columns else ('Branch Type' if 'Branch Type' in df.columns else group_col)
        return col, 's_type'
    return BRANCH_COLUMN, 'branch'


def fee_summary_by_branch(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    branches: list[str] | None = None,
    n: int | None = None,
    sort_col: str = 'CY_A_FD',
    ascending: bool = False,
    group_col: str | None = None,
) -> list[dict]:
    """
    Complete fee due snapshot aggregated by Branch, Zone, RI, AGM, or S_Type.
    """
    available = [c for c in (_FEE_SUMMARY_COLS if columns is None else columns) if c in df.columns]
    if not available:
        return []

    entity_col, entity_label = _resolve_group_column(df, group_col)
    if entity_col not in df.columns:
        entity_col = BRANCH_COLUMN if BRANCH_COLUMN in df.columns else df.columns[0]
        entity_label = 'branch'

    work = df[[entity_col] + available].copy()
    for col in available:
        work[col] = pd.to_numeric(work[col], errors='coerce').fillna(0)
    work = work.dropna(subset=[entity_col])
    work = work[work[entity_col].astype(str).str.strip().str.len() > 0]

    if branches and entity_label == 'branch':
        wanted = {str(b).strip().casefold() for b in branches}
        work = work[work[entity_col].astype(str).str.strip().str.casefold().isin(wanted)]

    # Group by entity if entity_col is not unique per row or explicitly specified
    if entity_col != BRANCH_COLUMN or len(work[entity_col]) != len(work[entity_col].unique()):
        grouped = work.groupby(entity_col, as_index=False)[available].sum()
        work = grouped

    if sort_col in work.columns:
        work = work.sort_values([sort_col, entity_col], ascending=[ascending, True], kind='stable')
    if n is not None and n > 0:
        work = work.head(n)

    results = []
    for rank, (_, row) in enumerate(work.iterrows(), start=1):
        entry = {'rank': rank, entity_label: str(row[entity_col])}
        for col in available:
            entry[col] = round(float(row[col]), 2)
        results.append(entry)
    return results


def fee_books_not_purchased(
    df: pd.DataFrame,
    mode: str = 'both',         # 'paid_not_bought' | 'not_paid_not_bought' | 'both'
    n: int | None = None,
    ascending: bool = False,
    branches: list[str] | None = None,
    group_col: str | None = None,
) -> list[dict]:
    """
    Entities (Branch, Zone, RI, AGM, S_Type) where books were not purchased.
    """
    cols_needed = [c for c in _FEE_BOOKS_COLS if c in df.columns]
    if not cols_needed:
        return []

    entity_col, entity_label = _resolve_group_column(df, group_col)
    if entity_col not in df.columns:
        entity_col = BRANCH_COLUMN if BRANCH_COLUMN in df.columns else df.columns[0]
        entity_label = 'branch'

    work = df[[entity_col] + cols_needed].copy()
    for col in cols_needed:
        work[col] = pd.to_numeric(work[col], errors='coerce').fillna(0)
    work = work.dropna(subset=[entity_col])
    work = work[work[entity_col].astype(str).str.strip().str.len() > 0]

    if branches and entity_label == 'branch':
        wanted = {str(b).strip().casefold() for b in branches}
        work = work[work[entity_col].astype(str).str.strip().str.casefold().isin(wanted)]

    # Aggregate by entity_col if grouping
    if entity_col != BRANCH_COLUMN or len(work[entity_col]) != len(work[entity_col].unique()):
        work = work.groupby(entity_col, as_index=False)[cols_needed].sum()

    fp_col = 'CY_FP_BN' if 'CY_FP_BN' in work.columns else None
    fn_col = 'CY_FN_BN' if 'CY_FN_BN' in work.columns else None

    if mode == 'paid_not_bought' and fp_col:
        mask = work[fp_col] > 0
        sort_col = fp_col
    elif mode == 'not_paid_not_bought' and fn_col:
        mask = work[fn_col] > 0
        sort_col = fn_col
    else:
        mask = pd.Series([False] * len(work), index=work.index)
        if fp_col:
            mask = mask | (work[fp_col] > 0)
        if fn_col:
            mask = mask | (work[fn_col] > 0)
        sort_col = fp_col or fn_col

    work = work[mask].sort_values(
        [sort_col, entity_col], ascending=[ascending, True], kind='stable'
    )
    if n is not None and n > 0:
        work = work.head(n)

    results = []
    for rank, (_, row) in enumerate(work.iterrows(), start=1):
        entry = {'rank': rank, entity_label: str(row[entity_col])}
        if fp_col:
            entry['CY_FP_BN'] = int(row[fp_col])
        if fn_col:
            entry['CY_FN_BN'] = int(row[fn_col])
        results.append(entry)
    return results


def fee_yoy_comparison(
    df: pd.DataFrame,
    n: int | None = None,
    ascending: bool = False,
    branches: list[str] | None = None,
    group_col: str | None = None,
) -> list[dict]:
    """
    Last Year vs Current Year fee due comparison aggregated by Branch, Zone, RI, AGM, or S_Type.
    """
    cy_col = 'CY_A_FD'
    ly_col = 'LY_FD'
    if cy_col not in df.columns or ly_col not in df.columns:
        return []

    entity_col, entity_label = _resolve_group_column(df, group_col)
    if entity_col not in df.columns:
        entity_col = BRANCH_COLUMN if BRANCH_COLUMN in df.columns else df.columns[0]
        entity_label = 'branch'

    work = df[[entity_col, cy_col, ly_col]].copy()
    work[cy_col] = pd.to_numeric(work[cy_col], errors='coerce').fillna(0)
    work[ly_col] = pd.to_numeric(work[ly_col], errors='coerce').fillna(0)
    work = work.dropna(subset=[entity_col])
    work = work[work[entity_col].astype(str).str.strip().str.len() > 0]

    if branches and entity_label == 'branch':
        wanted = {str(b).strip().casefold() for b in branches}
        work = work[work[entity_col].astype(str).str.strip().str.casefold().isin(wanted)]

    # Aggregate by entity_col if grouping
    if entity_col != BRANCH_COLUMN or len(work[entity_col]) != len(work[entity_col].unique()):
        work = work.groupby(entity_col, as_index=False)[[cy_col, ly_col]].sum()

    work['change'] = work[cy_col] - work[ly_col]
    work = work.sort_values(['change', entity_col], ascending=[ascending, True], kind='stable')
    if n is not None and n > 0:
        work = work.head(n)

    return [
        {
            'rank': rank,
            entity_label: str(row[entity_col]),
            'LY_FD': round(float(row[ly_col]), 2),
            'CY_A_FD': round(float(row[cy_col]), 2),
            'last_year': round(float(row[ly_col]), 2),
            'current_year': round(float(row[cy_col]), 2),
            'change': round(float(row['change']), 2),
            'difference': round(float(row['change']), 2),
        }
        for rank, (_, row) in enumerate(work.iterrows(), start=1)
    ]


# ---------------------------------------------------------------------------
# Revenue vs Salary Analytics Primitives
# ---------------------------------------------------------------------------

SEGMENT_LABELS = {
    'PP': 'Pre Primary',
    'LPS': 'Lower Primary',
    'UPS': 'Upper Primary',
    'HS': 'High School',
    'ACD': 'ACD',
    'AD_AC': 'Activity & Admin',
    'TOT': 'Total Overall',
}


def revenue_salary_summary(df: pd.DataFrame, segment: str = 'TOT') -> dict:
    """
    Computes overall aggregated totals and derived metrics for a given segment.
    SUMS raw columns (REV_N, SAL, NS, SC) first, then computes derived metrics.
    Zero denominator safe.
    """
    if df.empty:
        return {
            'segment': segment,
            'segment_label': SEGMENT_LABELS.get(segment, segment),
            'branch_count': 0,
            'total_revenue': 0.0,
            'total_salary': 0.0,
            'total_students': 0,
            'total_employees': 0,
            'fee_average': 0.0,
            'cost_per_student': 0.0,
            'salary_vs_revenue_pct': 0.0,
            'student_teacher_ratio': 0.0,
            'surplus': 0.0,
        }

    pfx = f"{segment}_" if segment in ('PP', 'LPS', 'UPS', 'HS', 'ACD', 'AD_AC', 'TOT') else 'TOT_'
    rev_col = f"{pfx}REV_N" if f"{pfx}REV_N" in df.columns else 'TOT_REV_N'
    sal_col = f"{pfx}SAL" if f"{pfx}SAL" in df.columns else 'TOT_SAL'
    ns_col = f"{pfx}NS" if f"{pfx}NS" in df.columns else 'TOT_NS'
    sc_col = f"{pfx}SC" if f"{pfx}SC" in df.columns else 'TOT_SC'

    tot_rev = float(pd.to_numeric(df[rev_col], errors='coerce').fillna(0).sum())
    tot_sal = float(pd.to_numeric(df[sal_col], errors='coerce').fillna(0).sum())
    tot_ns = float(pd.to_numeric(df[ns_col], errors='coerce').fillna(0).sum())
    tot_sc = float(pd.to_numeric(df[sc_col], errors='coerce').fillna(0).sum())

    fa = (tot_rev / tot_ns) if tot_ns > 0 else 0.0
    cs = (tot_sal / tot_ns) if tot_ns > 0 else 0.0
    sal_v_rev = ((tot_sal / tot_rev) * 100.0) if tot_rev > 0 else 0.0
    str_ratio = (tot_ns / tot_sc) if tot_sc > 0 else 0.0
    surplus = tot_rev - tot_sal

    return {
        'segment': segment,
        'segment_label': SEGMENT_LABELS.get(segment, segment),
        'branch_count': len(df),
        'total_revenue': round(tot_rev, 2),
        'total_salary': round(tot_sal, 2),
        'total_students': int(tot_ns),
        'total_employees': int(tot_sc),
        'fee_average': round(fa, 2),
        'cost_per_student': round(cs, 2),
        'salary_vs_revenue_pct': round(sal_v_rev, 2),
        'student_teacher_ratio': round(str_ratio, 2),
        'surplus': round(surplus, 2),
    }


def revenue_salary_segment_comparison(df: pd.DataFrame) -> list[dict]:
    """
    Compares all 6 academic segments (PP, LPS, UPS, HS, ACD, AD_AC)
    by summing raw columns first and computing derived metrics.
    """
    segments = ['PP', 'LPS', 'UPS', 'HS', 'ACD', 'AD_AC']
    results = []
    for seg in segments:
        summary = revenue_salary_summary(df, segment=seg)
        results.append(summary)
    return results


def revenue_salary_ranking(
    df: pd.DataFrame,
    metric: str = 'TOT_REV_N',
    group_col: str = BRANCH_COLUMN,
    n: int | None = 5,
    ascending: bool = False
) -> list[dict]:
    """
    Ranks entities (Branch, RI, Zone, AGM) by a specified revenue vs salary metric.
    SUMS raw columns per entity first, then computes derived metrics.
    """
    if df.empty:
        return []

    # Map generic metric names
    m_upper = metric.upper()
    if m_upper in ('REVENUE', 'NET_REVENUE', 'TOT_REV_N'):
        sort_metric = 'total_revenue'
    elif m_upper in ('SALARY', 'EMPLOYEE_COST', 'TOT_SAL'):
        sort_metric = 'total_salary'
    elif m_upper in ('SURPLUS', 'NET_SURPLUS'):
        sort_metric = 'surplus'
    elif m_upper in ('STUDENTS', 'TOT_NS'):
        sort_metric = 'total_students'
    elif m_upper in ('EMPLOYEES', 'TOT_SC'):
        sort_metric = 'total_employees'
    elif m_upper in ('FEE_AVERAGE', 'TOT_FA'):
        sort_metric = 'fee_average'
    elif m_upper in ('COST_PER_STUDENT', 'TOT_CS'):
        sort_metric = 'cost_per_student'
    elif m_upper in ('SALARY_VS_REVENUE', 'TOT_SAL_V_REV'):
        sort_metric = 'salary_vs_revenue_pct'
    elif m_upper in ('STUDENT_TEACHER_RATIO', 'TOT_STR'):
        sort_metric = 'student_teacher_ratio'
    else:
        sort_metric = 'total_revenue'

    grouped = []
    for entity_name, group in df.groupby(group_col):
        summary = revenue_salary_summary(group, segment='TOT')
        summary['entity'] = str(entity_name)
        grouped.append(summary)

    grouped_df = pd.DataFrame(grouped)
    if grouped_df.empty:
        return []

    grouped_df = grouped_df.sort_values(by=sort_metric, ascending=ascending, kind='stable')
    if n is not None and n > 0:
        grouped_df = grouped_df.head(n)

    out = []
    for rank, (_, row) in enumerate(grouped_df.iterrows(), start=1):
        out.append({
            'rank': rank,
            'entity': row['entity'],
            'total_revenue': row['total_revenue'],
            'total_salary': row['total_salary'],
            'total_students': row['total_students'],
            'total_employees': row['total_employees'],
            'fee_average': row['fee_average'],
            'cost_per_student': row['cost_per_student'],
            'salary_vs_revenue_pct': row['salary_vs_revenue_pct'],
            'student_teacher_ratio': row['student_teacher_ratio'],
            'surplus': row['surplus'],
        })
    return out


def revenue_salary_threshold_filter(
    df: pd.DataFrame,
    metric: str = 'TOT_REV_N',
    operator: str = '>',
    value: float = 10000000.0,
    group_col: str = BRANCH_COLUMN
) -> list[dict]:
    """
    Filters entities matching threshold conditions (e.g., revenue > 1 crore).
    """
    all_ranked = revenue_salary_ranking(df, metric=metric, group_col=group_col, n=None, ascending=False)
    
    m_upper = metric.upper()
    metric_key = 'total_revenue'
    if 'SAL' in m_upper:
        metric_key = 'total_salary'
    elif 'SURPLUS' in m_upper:
        metric_key = 'surplus'
    elif 'CS' in m_upper:
        metric_key = 'cost_per_student'
    elif 'FA' in m_upper:
        metric_key = 'fee_average'
    elif 'STR' in m_upper:
        metric_key = 'student_teacher_ratio'
    elif 'SAL_V_REV' in m_upper:
        metric_key = 'salary_vs_revenue_pct'
    elif 'NS' in m_upper:
        metric_key = 'total_students'

    filtered = []
    for item in all_ranked:
        val = item.get(metric_key, 0.0)
        matches = False
        if operator in ('>', '>=', 'gt', 'gte'):
            matches = val >= value
        elif operator in ('<', '<=', 'lt', 'lte'):
            matches = val <= value
        elif operator in ('==', '=', 'eq'):
            matches = abs(val - value) < 1e-5

        if matches:
            filtered.append(item)

    return filtered


def entity_summary(
    df: pd.DataFrame,
    group_column: str | None = None,
    entity_name: str | None = None,
) -> dict:
    """
    Generate an entity-level summary card covering key metrics (Fee Due, Dropouts, Strength, Revenue, Salary, Ratios)
    with weighted derived metrics and KPI status.
    """
    work = df.copy()
    if group_column and entity_name:
        cols_to_filter = [group_column, group_column.replace(' Name', ''), f"{group_column}_Name"]
        target_col = None
        for c in cols_to_filter:
            if c in work.columns:
                target_col = c
                break
        if target_col:
            e_norm = entity_name.strip().lower()
            work = work[work[target_col].astype(str).str.strip().str.lower().str.contains(re.escape(e_norm), na=False)]

    if work.empty:
        return {'entity_name': entity_name or 'All Entities', 'group_column': group_column or 'All', 'records': []}

    metrics_to_include = [
        'CY_A_FD', 'LY_FD', 'CY_A_FDC', 'LY_FDC', 'CY_A_ZP', 'CY_ZP_FD',
        'DPP', 'DP', 'NS', 'STR', 'TOT_REV_N', 'TOT_SAL', 'TOT_SAL_V_REV', 'SURPLUS'
    ]

    from .metric_registry import get_default_metric_registry
    registry = get_default_metric_registry()

    summary_records = []
    for metric_id in metrics_to_include:
        spec = registry.get(metric_id)
        if not spec:
            continue

        val = None
        if spec.metric_type == 'derived' and spec.numerator_metric and spec.denominator_metric:
            num_col = spec.numerator_metric
            den_col = spec.denominator_metric
            if num_col not in work.columns:
                num_col = f"CY-{num_col}" if f"CY-{num_col}" in work.columns else f"CY_{num_col}"
            if den_col not in work.columns:
                den_col = f"CY-{den_col}" if f"CY-{den_col}" in work.columns else f"CY_{den_col}"

            if num_col in work.columns and den_col in work.columns:
                n_sum = pd.to_numeric(work[num_col], errors='coerce').sum()
                d_sum = pd.to_numeric(work[den_col], errors='coerce').sum()
                if d_sum > 0:
                    val = (n_sum / d_sum) * (100.0 if spec.data_type == 'percentage' else 1.0)
        else:
            col = spec.source_column
            if col not in work.columns:
                col = f"CY-{col}" if f"CY-{col}" in work.columns else f"CY_{col}"
            if col in work.columns:
                series = pd.to_numeric(work[col], errors='coerce').dropna()
                if not series.empty:
                    val = series.mean() if spec.default_agg == 'mean' or spec.data_type == 'percentage' else series.sum()

        if val is not None:
            summary_records.append({
                'metric_id': metric_id,
                'display_name': spec.display_name,
                'value': round(float(val), 2),
                'data_type': spec.data_type,
                'kpi_direction': spec.kpi_direction,
            })

    return {
        'entity_name': entity_name or 'Overall',
        'group_column': group_column or 'All',
        'records': summary_records,
    }


