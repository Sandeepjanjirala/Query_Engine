from __future__ import annotations

import pandas as pd

from .glossary import BRANCH_COLUMN, DROPOUT_PERCENTAGE_COLUMN


# ---------------------------------------------------------------------------
# Reusable analytics primitives.
#
# All query capabilities are thin orchestration layers around these
# parameter-driven analytics functions. None of them are aware of natural
# language -- they take resolved column names and operate on whatever
# DataFrame apply_filter_context() produced.
# ---------------------------------------------------------------------------


def rank_branches_by_metric(
    df: pd.DataFrame, column: str, n: int | None = 5, ascending: bool = False
) -> list[dict]:
    """Top/bottom-N branches by any single numeric metric column."""
    work = df[[BRANCH_COLUMN, column]].copy()
    work[column] = pd.to_numeric(work[column], errors='coerce')
    work = work.dropna(subset=[BRANCH_COLUMN, column])
    work = work[work[BRANCH_COLUMN].str.len() > 0]
    work = work.sort_values(
        [column, BRANCH_COLUMN], ascending=[ascending, True], kind='stable'
    )
    if n is not None and n > 0:
        work = work.head(n)

    return [
        {
            'rank': rank,
            'branch': str(row[BRANCH_COLUMN]),
            'value': round(float(row[column]), 2),
        }
        for rank, (_, row) in enumerate(work.iterrows(), start=1)
    ]


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
            if column not in row.index:
                entry[column] = None
                continue
            value = row[column]
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
    """Sum/mean/count of a metric column grouped by an org dimension column."""
    work = df[[group_column, value_column]].copy()
    work[value_column] = pd.to_numeric(work[value_column], errors='coerce')
    work = work.dropna(subset=[group_column])

    grouped = work.groupby(group_column, dropna=False)[value_column]
    if agg == 'mean':
        series = grouped.mean()
    elif agg == 'count':
        series = grouped.count()
    else:
        series = grouped.sum()

    series = series.sort_values(ascending=ascending)
    if n is not None and n > 0:
        series = series.head(n)

    return [{'group': str(key), 'value': round(float(val), 2)} for key, val in series.items()]


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

        records = [
            {'group': str(k), 'value': round(float(v), 2)}
            for k, v in matches.sort_values(ascending=False).items()
        ]
        return {
            'count': len(records),
            'threshold': threshold,
            'op': op,
            'count_only': count_only,
            'group_column': group_column,
            'records': records,
        }

    work = df.copy()
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
    records = [
        {'branch': str(row[BRANCH_COLUMN]), 'value': round(float(row[col_to_use]), 2)}
        for _, row in matched.iterrows()
    ]
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
) -> dict:
    """
    Compare metrics across categories (Levels PP/PS/HS, Types Existing/New, Rooms Occupied/Empty,
    or Group CY vs LY).
    """
    if yoy_pairs:
        # e.g. {'PP': ('PP-CY-DPP', 'PP-LY-DPP'), 'PS': ('PS-CY-DPP', 'PS-LY-DPP'), ...}
        results = []
        for cat, (cy_col, ly_col) in yoy_pairs.items():
            if cy_col not in df.columns or ly_col not in df.columns:
                continue
            cy_val = pd.to_numeric(df[cy_col], errors='coerce').dropna()
            ly_val = pd.to_numeric(df[ly_col], errors='coerce').dropna()
            cy_res = cy_val.mean() if agg == 'mean' else cy_val.sum()
            ly_res = ly_val.mean() if agg == 'mean' else ly_val.sum()
            diff = cy_res - ly_res
            results.append({
                'category': cat,
                'current_year': round(float(cy_res), 2),
                'last_year': round(float(ly_res), 2),
                'change': round(float(diff), 2),
            })
        if top == 'highest_improvement' or top == 'improved':
            # Highest positive change
            sorted_res = sorted(results, key=lambda x: x['change'], reverse=True)
            winner = sorted_res[0] if sorted_res else None
            return {'comparison_type': 'yoy_breakdown', 'data': results, 'winner': winner}
        if top == 'highest_decline' or top == 'declined':
            # Lowest (most negative) change
            sorted_res = sorted(results, key=lambda x: x['change'])
            winner = sorted_res[0] if sorted_res else None
            return {'comparison_type': 'yoy_breakdown', 'data': results, 'winner': winner}
        return {'comparison_type': 'yoy_breakdown', 'data': results, 'winner': None}

    if group_column:
        # Grouped comparison: each category computed per group value
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

    # Overall category comparison
    data = []
    for label, col in columns_map.items():
        if col in df.columns:
            val = pd.to_numeric(df[col], errors='coerce').dropna()
            calc = val.mean() if agg == 'mean' else val.sum()
            data.append({'category': label, 'value': round(float(calc), 2)})
        else:
            data.append({'category': label, 'value': 0.0})

    winner = None
    if top == 'highest':
        sorted_d = sorted(data, key=lambda x: x['value'], reverse=True)
        winner = sorted_d[0] if sorted_d else None
    elif top == 'lowest':
        sorted_d = sorted(data, key=lambda x: x['value'])
        winner = sorted_d[0] if sorted_d else None

    return {'comparison_type': 'categories', 'data': data, 'winner': winner}


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
    work = df[[BRANCH_COLUMN, DROPOUT_PERCENTAGE_COLUMN]].copy()
    work = work.dropna(subset=[BRANCH_COLUMN, DROPOUT_PERCENTAGE_COLUMN])
    work = work[work[BRANCH_COLUMN].str.len() > 0]
    work = work.sort_values(
        [DROPOUT_PERCENTAGE_COLUMN, BRANCH_COLUMN],
        ascending=[False, True],
        kind='stable',
    ).head(5)

    return [
        {
            'rank': rank,
            'branch': str(row[BRANCH_COLUMN]),
            'dropout_percentage': round(float(row[DROPOUT_PERCENTAGE_COLUMN]), 2),
        }
        for rank, (_, row) in enumerate(work.iterrows(), start=1)
    ]
