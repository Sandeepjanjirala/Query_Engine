from __future__ import annotations

from functools import lru_cache

from django.conf import settings
import pandas as pd

from .analytics import (
    aggregate_by_group,
    aggregate_metric_total,
    calculate_room_ratio,
    compare_dimensions,
    filter_by_threshold,
    lookup_branch_metrics,
    rank_branches_by_metric,
    top_5_dropout_branches,
    year_over_year_ranking,
)
from .formatting import (
    format_branch_lookup,
    format_branch_scorecard,
    format_dimension_comparison,
    format_group_aggregate,
    format_ranked_branches,
    format_room_ratio,
    format_room_snapshot,
    format_scope_total,
    format_sections_sps_snapshot,
    format_staff_summary,
    format_strength_difference,
    format_threshold_result,
    format_top_5_dropout,
    format_year_over_year,
)
from .glossary import GROUP_COLUMNS, ROOM_METRICS
from .metric_registry import get_default_metric_registry
from .pandas_tools import build_metric_index, load_excel, resolve_column
from .query_planner import get_prepared_dataframe


from .dataset_loader import clear_dataset_cache


@lru_cache(maxsize=1)
def get_dataframe():
    """Process-level cache: Excel is loaded once, not for every request."""
    return load_excel(settings.BRANCH_ANALYTICS_FILE, settings.BRANCH_ANALYTICS_SHEET)


def clear_caches():
    get_dataframe.cache_clear()
    get_metric_index.cache_clear()
    clear_dataset_cache()



@lru_cache(maxsize=1)
def get_metric_index():
    """Process-level cache of the (level, type, year, metric) -> column map."""
    return build_metric_index(get_dataframe())


def _empty_result(function_name: str, answer: str):
    return {'function': function_name, 'answer': answer, 'data': []}


def run_top_5_dropout(context: dict | None = None):
    """V1 pre-function: top 5 branches with highest CY-DPP."""
    df = get_prepared_dataframe(['CY-DPP'], context)
    results = top_5_dropout_branches(df)
    return {
        'function': 'top_5_dropout_branches',
        'answer': format_top_5_dropout(results),
        'data': results,
    }


def run_rank_branches_by_metric(params: dict, context: dict | None = None):
    """Top/bottom-N branches by any metric/level/type/year combination."""
    metric = params.get('metric') or 'CY-DPP'
    spec = get_default_metric_registry().get(metric)
    m_key = spec.metric_id if spec else metric
    df = get_prepared_dataframe([m_key], context)

    index = build_metric_index(df)
    column = None
    if spec and spec.source_column in df.columns:
        column = spec.source_column
    elif metric in df.columns:
        column = metric
    else:
        column = resolve_column(
            index, metric, params.get('level'), params.get('type'), params.get('year', 'CY')
        )

    if column is None:
        return _empty_result(
            'rank_branches_by_metric',
            f"No data column is available for the requested metric ({metric}).",
        )
    results = rank_branches_by_metric(df, column, n=params.get('n', 5), ascending=params.get('ascending', False))
    return {
        'function': 'rank_branches_by_metric',
        'answer': format_ranked_branches(results, metric, params.get('ascending', False)),
        'data': results,
    }


def run_branch_metric_lookup(params: dict, context: dict | None = None):
    """Value(s) of one or more metrics for one, several, or all branches."""
    metrics = params.get('metrics') or [params.get('metric') or 'CY-DPP']
    df = get_prepared_dataframe(metrics, context)
    index = build_metric_index(df)

    columns = []
    for m in metrics:
        spec = get_default_metric_registry().get(m)
        if spec and spec.source_column in df.columns:
            columns.append(spec.source_column)
        elif m in df.columns:
            columns.append(m)
        else:
            col = resolve_column(index, m, params.get('level'), params.get('type'), params.get('year', 'CY'))
            if col:
                columns.append(col)

    if not columns:
        return _empty_result(
            'branch_metric_lookup',
            f"No data column is available for the requested metrics.",
        )
    results = lookup_branch_metrics(df, columns, branches=params.get('branches'))
    return {
        'function': 'branch_metric_lookup',
        'answer': format_branch_lookup(results, columns),
        'data': results,
    }


def run_group_metric_aggregate(params: dict, context: dict | None = None):
    """Sum/average/count of a metric grouped by Zone, AGM, or RI."""
    group_column = GROUP_COLUMNS.get(params['group_dimension'])
    metric = params.get('metric') or 'DP'
    spec = get_default_metric_registry().get(metric)
    m_key = spec.metric_id if spec else metric
    df = get_prepared_dataframe([m_key], context)

    metric_column = None
    if spec and spec.source_column in df.columns:
        metric_column = spec.source_column
    elif metric in df.columns:
        metric_column = metric
    else:
        metric_column = resolve_column(
            build_metric_index(df), metric, params.get('level'), params.get('type'), params.get('year', 'CY')
        )

    if group_column is None or metric_column is None:
        return _empty_result(
            'group_metric_aggregate',
            f"No data column is available for the requested metric ({metric}).",
        )
    agg = params.get('agg', 'mean' if metric in ('DPP', 'STR', 'Avg-SPS') else 'sum')
    results = aggregate_by_group(
        df, group_column, metric_column, agg=agg, n=params.get('n'), ascending=params.get('ascending', False)
    )
    return {
        'function': 'group_metric_aggregate',
        'answer': format_group_aggregate(results, metric, params['group_dimension'], agg),
        'data': results,
    }


def run_year_over_year_change_ranking(params: dict, context: dict | None = None):
    """Branches with the biggest CY-vs-LY gain/drop on a metric."""
    metric = params.get('metric') or 'NS'
    level = params.get('level')
    type_ = params.get('type')
    n = params.get('n', 5)
    direction = params.get('direction', 'positive')
    sort_by = params.get('sort_by', 'absolute' if direction == 'absolute' else 'change')
    ascending = params.get('ascending', direction == 'negative')

    spec = get_default_metric_registry().get(metric)
    m_key = spec.metric_id if spec else metric
    df = get_prepared_dataframe([m_key], context)

    index = build_metric_index(df)
    cy_column = resolve_column(index, metric, level, type_, 'CY')
    ly_column = resolve_column(index, metric, level, type_, 'LY')
    if cy_column is None or ly_column is None or cy_column == ly_column:
        return _empty_result(
            'year_over_year_change_ranking',
            f"No current-year/last-year data is available for the requested metric ({metric}).",
        )
    results = year_over_year_ranking(
        df, cy_column, ly_column, n=n, ascending=ascending, sort_by=sort_by
    )
    return {
        'function': 'year_over_year_change_ranking',
        'answer': format_year_over_year(results, metric),
        'data': results,
    }


def run_filter_by_threshold(params: dict, context: dict | None = None):
    """Filter branches or groups satisfying threshold condition."""
    metric = params.get('metric') or 'DPP'
    level = params.get('level')
    type_ = params.get('type')
    op = params.get('op', 'gt')
    threshold = params.get('threshold', 0.0)
    count_only = params.get('count_only', False)
    group_dimension = params.get('group_dimension')

    spec = get_default_metric_registry().get(metric)
    m_key = spec.metric_id if spec else metric
    df = get_prepared_dataframe([m_key], context)

    if metric == 'vacancy_rate':
        nocr = pd.to_numeric(df['NOCR'], errors='coerce').fillna(0)
        novr = pd.to_numeric(df['NOVR'], errors='coerce').fillna(0)
        custom_series = (novr / nocr * 100).fillna(0)
        results = filter_by_threshold(
            df, op=op, threshold=threshold, count_only=count_only, custom_series=custom_series
        )
        return {
            'function': 'filter_by_threshold',
            'answer': format_threshold_result(results, 'vacancy_rate'),
            'data': results['records'] if not count_only else [{'count': results['count']}],
        }

    column = None
    if spec and spec.source_column in df.columns:
        column = spec.source_column
    elif metric in df.columns:
        column = metric
    else:
        column = resolve_column(build_metric_index(df), metric, level, type_, params.get('year', 'CY'))

    if column is None:
        return _empty_result('filter_by_threshold', f'No column available for {metric}.')

    group_column = GROUP_COLUMNS.get(group_dimension) if group_dimension else None
    agg = 'mean' if metric in ('DPP', 'STR', 'Avg-SPS') else 'sum'
    results = filter_by_threshold(
        df, column=column, op=op, threshold=threshold, count_only=count_only,
        group_column=group_column, agg=agg,
    )
    return {
        'function': 'filter_by_threshold',
        'answer': format_threshold_result(results, metric),
        'data': results['records'] if not count_only else [{'count': results['count']}],
    }


def run_compare_dimensions(params: dict, context: dict | None = None):
    """Compare across education levels (PP/PS/HS), admission types (E/N), or rooms."""
    dimension_type = params.get('dimension_type', 'level')
    metric = params.get('metric') or 'DPP'
    level = params.get('level')
    type_ = params.get('type')
    year = params.get('year', 'CY')
    group_dimension = params.get('group_dimension')
    top = params.get('top')
    group_column = GROUP_COLUMNS.get(group_dimension) if group_dimension else None

    spec = get_default_metric_registry().get(metric)
    m_key = spec.metric_id if spec else metric
    df = get_prepared_dataframe([m_key], context)
    index = build_metric_index(df)

    if dimension_type == 'level':
        if year == 'yoy' or params.get('direction') in ('positive', 'negative'):
            yoy_pairs = {
                'PP': (resolve_column(index, metric, 'PP', None, 'CY'), resolve_column(index, metric, 'PP', None, 'LY')),
                'PS': (resolve_column(index, metric, 'PS', None, 'CY'), resolve_column(index, metric, 'PS', None, 'LY')),
                'HS': (resolve_column(index, metric, 'HS', None, 'CY'), resolve_column(index, metric, 'HS', None, 'LY')),
            }
            direction = 'improved' if params.get('direction') == 'positive' else ('declined' if params.get('direction') == 'negative' else None)
            agg = 'mean' if metric in ('DPP', 'STR', 'Avg-SPS') else 'sum'
            results = compare_dimensions(df, {}, group_column=None, agg=agg, top=direction, yoy_pairs=yoy_pairs)
            return {
                'function': 'compare_dimensions',
                'answer': format_dimension_comparison(results, metric, 'education levels'),
                'data': results['data'],
            }

        columns_map = {
            'PP': resolve_column(index, metric, 'PP', None, year),
            'PS': resolve_column(index, metric, 'PS', None, year),
            'HS': resolve_column(index, metric, 'HS', None, year),
        }
        columns_map = {k: v for k, v in columns_map.items() if v}
        agg = 'mean' if metric in ('DPP', 'STR', 'Avg-SPS') else 'sum'
        results = compare_dimensions(df, columns_map, group_column=group_column, agg=agg, top=top)
        return {
            'function': 'compare_dimensions',
            'answer': format_dimension_comparison(results, metric, 'education levels'),
            'data': results['data'],
        }

    if dimension_type == 'type':
        if type_ == 'E' and not params.get('has_both_types'):
            col = resolve_column(index, metric, level, 'E', year)
            columns_map = {'Existing Students': col} if col else {}
        elif type_ == 'N' and not params.get('has_both_types'):
            col = resolve_column(index, metric, level, 'N', year)
            columns_map = {'New Students': col} if col else {}
        else:
            columns_map = {
                'Existing': resolve_column(index, metric, level, 'E', year),
                'New': resolve_column(index, metric, level, 'N', year),
            }
        columns_map = {k: v for k, v in columns_map.items() if v}
        agg = 'mean' if metric in ('DPP', 'STR', 'Avg-SPS') else 'sum'
        results = compare_dimensions(df, columns_map, group_column=group_column, agg=agg, top=top)
        return {
            'function': 'compare_dimensions',
            'answer': format_dimension_comparison(results, metric, 'admission types (Existing vs New)'),
            'data': results['data'],
        }

    if dimension_type == 'rooms':
        columns_map = {'Occupied': 'NOOR', 'Empty': 'NOVR'}
        results = compare_dimensions(df, columns_map, group_column=group_column, agg='sum')
        return {
            'function': 'compare_dimensions',
            'answer': format_dimension_comparison(results, 'Rooms', 'Occupied vs Empty'),
            'data': results['data'],
        }

    if dimension_type == 'group_yoy':
        cy_col = resolve_column(index, metric, level, None, 'CY')
        ly_col = resolve_column(index, metric, level, None, 'LY')
        columns_map = {'Current Year': cy_col, 'Last Year': ly_col}
        columns_map = {k: v for k, v in columns_map.items() if v}
        results = compare_dimensions(df, columns_map, group_column=group_column, agg='sum')
        return {
            'function': 'compare_dimensions',
            'answer': format_dimension_comparison(results, metric, f'CY vs LY by {group_dimension}'),
            'data': results['data'],
        }

    return _empty_result('compare_dimensions', 'Invalid comparison dimensions.')


def run_calculate_room_ratio(params: dict, context: dict | None = None):
    """Calculate room occupancy percentage or vacancy percentage across branches."""
    df = get_prepared_dataframe(['NOOR', 'NOVR', 'NOCR'], context)
    ratio_type = params.get('ratio_type', 'occupancy')
    n = params.get('n')
    ascending = params.get('ascending')
    results = calculate_room_ratio(df, ratio_type=ratio_type, n=n, ascending=ascending)
    return {
        'function': 'calculate_room_ratio',
        'answer': format_room_ratio(results, ratio_type, ascending),
        'data': results,
    }


def run_scope_total(params: dict, context: dict | None = None):
    """Calculate overall total for a metric across current filter scope."""
    metric = params.get('metric') or 'NOOR'
    spec = get_default_metric_registry().get(metric)
    m_key = spec.metric_id if spec else metric
    df = get_prepared_dataframe([m_key], context)

    column = spec.source_column if spec and spec.source_column in df.columns else (resolve_column(build_metric_index(df), metric) or metric)
    if column not in df.columns:
        return _empty_result('scope_total', f'Column not found for {metric}.')
    val = aggregate_metric_total(df, column, agg='sum')
    return {
        'function': 'scope_total',
        'answer': format_scope_total(val, metric),
        'data': [{'metric': metric, 'value': val}],
    }


def run_staff_count_summary(params: dict, context: dict | None = None):
    """Staff count breakdown for one branch or all filtered branches."""
    df = get_prepared_dataframe(['SC'], context)
    index = build_metric_index(df)
    columns = []
    if params.get('staff_category'):
        col = resolve_column(index, 'SC', params['staff_category'], None, params.get('year', 'CY'))
        if col:
            columns.append(col)
    else:
        for level in (params.get('level'), None) if params.get('level') else (None,):
            col = resolve_column(index, 'SC', level, None, params.get('year', 'CY'))
            if col and col not in columns:
                columns.append(col)
        for category in ('AC', 'AD'):
            col = resolve_column(index, 'SC', category, None, params.get('year', 'CY'))
            if col and col not in columns:
                columns.append(col)

    if not columns:
        return _empty_result('staff_count_summary', 'No staff count data is available for the current filters.')

    results = lookup_branch_metrics(df, columns, branches=params.get('branches'))
    return {
        'function': 'staff_count_summary',
        'answer': format_staff_summary(results, columns),
        'data': results,
    }


def run_room_utilization_snapshot(params: dict, context: dict | None = None):
    """NOCR/NOOR/NOVR/ARCS for one branch or all filtered branches."""
    df = get_prepared_dataframe(['NOCR', 'NOOR', 'NOVR', 'ARCS'], context)
    index = build_metric_index(df)
    metrics = [params['metric']] if params.get('metric') in ROOM_METRICS else list(ROOM_METRICS)
    columns = [c for c in (resolve_column(index, m) for m in metrics) if c]
    if not columns:
        return _empty_result('room_utilization_snapshot', 'No room utilization data is available.')

    results = lookup_branch_metrics(df, columns, branches=params.get('branches'))
    return {
        'function': 'room_utilization_snapshot',
        'answer': format_room_snapshot(results, columns),
        'data': results,
    }


def run_sections_and_sps_snapshot(params: dict, context: dict | None = None):
    """NOS / Avg-SPS for one or all filtered branches."""
    df = get_prepared_dataframe(['NOS', 'Avg-SPS'], context)
    index = build_metric_index(df)
    columns = []
    for metric in ('NOS', 'Avg-SPS'):
        col = resolve_column(index, metric, params.get('level'))
        if col:
            columns.append(col)
    if not columns:
        return _empty_result('sections_and_sps_snapshot', 'No sections/SPS data is available.')

    results = lookup_branch_metrics(df, columns, branches=params.get('branches'))
    return {
        'function': 'sections_and_sps_snapshot',
        'answer': format_sections_sps_snapshot(results, columns),
        'data': results,
    }


def run_strength_difference_ranking(params: dict, context: dict | None = None):
    """Branches ranked by SD or NSD."""
    metric = params.get('metric') or 'NSD'
    spec = get_default_metric_registry().get(metric)
    m_key = spec.metric_id if spec else metric
    df = get_prepared_dataframe([m_key], context)

    column = resolve_column(build_metric_index(df), metric, params.get('level'))
    if column is None:
        return _empty_result('strength_difference_ranking', f'No data column is available for {metric}.')

    results = rank_branches_by_metric(df, column, n=params.get('n', 5), ascending=params.get('ascending', False))
    return {
        'function': 'strength_difference_ranking',
        'answer': format_strength_difference(results, metric),
        'data': results,
    }


def run_branch_scorecard(params: dict, context: dict | None = None):
    """Composite multi-metric snapshot for one branch."""
    metrics = ['GS', 'NS', 'DPP', 'STR', 'NOS', 'SC'] + list(ROOM_METRICS)
    df = get_prepared_dataframe(metrics, context)
    index = build_metric_index(df)
    columns = [c for c in (resolve_column(index, m, params.get('level'), None, 'CY') for m in metrics) if c]

    context_branches = [b for b in (context or {}).get('branches', []) if str(b).strip().casefold() != 'all']
    branches = params.get('branches') or context_branches
    results = lookup_branch_metrics(df, columns, branches=branches or None)
    entry = results[0] if results else None
    branch_label = branches[0] if branches else 'the requested branch'
    return {
        'function': 'branch_scorecard',
        'answer': format_branch_scorecard(entry, branch_label),
        'data': results,
    }
