from __future__ import annotations

from functools import lru_cache

from django.conf import settings
import pandas as pd
import re

from .analytics import (
    aggregate_by_group,
    aggregate_metric_total,
    calculate_room_ratio,
    compare_dimensions,
    entity_summary,
    fee_books_not_purchased,
    fee_summary_by_branch,
    fee_yoy_comparison,
    filter_by_threshold,
    lookup_branch_metrics,
    rank_branches_by_metric,
    revenue_salary_ranking,
    revenue_salary_segment_comparison,
    revenue_salary_summary,
    revenue_salary_threshold_filter,
    select_dropout_entities,
    top_5_dropout_branches,
    year_over_year_ranking,
)
from .analysis_engine import (
    build_agm_analysis,
    build_branch_analysis,
    build_ri_analysis,
    build_agm_fee_due_analysis,
    build_ri_fee_due_analysis,
    build_branch_fee_due_analysis,
    build_agm_revenue_salary_analysis,
    build_ri_revenue_salary_analysis,
    build_branch_revenue_salary_analysis,
    build_agm_teacher_student_ratio_analysis,
    build_ri_teacher_student_ratio_analysis,
    build_branch_teacher_student_ratio_analysis,
    format_display_ri_name,
)
from .formatting import (
    format_branch_lookup,
    format_branch_scorecard,
    format_dimension_comparison,
    format_entity_summary,
    format_fee_books,
    format_fee_summary,
    format_fee_yoy,
    format_group_aggregate,
    format_ranked_branches,
    format_revenue_salary_ranking,
    format_revenue_salary_segment_comparison,
    format_revenue_salary_summary,
    format_revenue_salary_threshold,
    format_room_ratio,
    format_room_snapshot,
    format_scope_total,
    format_sections_sps_snapshot,
    format_staff_summary,
    format_strength_difference,
    format_threshold_result,
    format_top_5_dropout,
    format_year_over_year,
    render_operation_response,
)
from .glossary import AGM_COLUMN, BRANCH_COLUMN, GROUP_COLUMNS, RI_COLUMN, ROOM_METRICS, ZONE_COLUMN
from .params import resolve_single_entity
from .metric_registry import get_default_metric_registry
from .pandas_tools import build_metric_index, load_excel, resolve_column
from .query_planner import get_prepared_dataframe


from .dataset_loader import clear_dataset_cache
from .filters import apply_filter_context


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


def run_top_5_dropout(params: dict | None = None, context: dict | None = None):
    """V1 pre-function: top 5 branches with highest CY-DPP (with 10% threshold & fallback)."""
    ctx = context if context is not None else (params if isinstance(params, dict) and 'question' not in params else None)
    df = get_prepared_dataframe(['CY-DPP'], ctx)
    raw_results = rank_branches_by_metric(df, 'CY-DPP', n=None, ascending=False)
    results, is_fallback = select_dropout_entities(raw_results, threshold=10.0, explicit_top_n=5)
    return {
        'function': 'top_5_dropout_branches',
        'answer': format_top_5_dropout(results, context=ctx, is_fallback=is_fallback),
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

    ascending = params.get('ascending', False)
    is_dropout_pct = (spec and spec.metric_id == 'DPP') or metric in ('DPP', 'CY-DPP') or 'dpp' in str(column).lower()

    if is_dropout_pct and not ascending:
        raw_results = rank_branches_by_metric(df, column, n=None, ascending=False)
        results, is_fallback = select_dropout_entities(raw_results, threshold=10.0, explicit_top_n=params.get('n'))
    else:
        results = rank_branches_by_metric(df, column, n=params.get('n'), ascending=ascending)
        is_fallback = False

    return {
        'function': 'rank_branches_by_metric',
        'answer': format_ranked_branches(results, metric, ascending, context=context, is_fallback=is_fallback),
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


def run_branch_hierarchy_lookup(params: dict, context: dict | None = None):
    """Answers which RI, AGM, and Zone a branch belongs to."""
    branches = params.get('branches') or (context.get('branches') if context else None) or []
    df = get_dataframe()
    if not branches or branches == ['All']:
        return _empty_result('branch_hierarchy_lookup', 'No branch was specified.')

    results = []
    for b in branches:
        match = df[df[BRANCH_COLUMN].astype(str).str.lower() == str(b).lower()]
        if match.empty:
            match = df[df[BRANCH_COLUMN].astype(str).str.lower().str.contains(str(b).lower(), na=False)]
        if not match.empty:
            row = match.iloc[0]
            ri = row.get(RI_COLUMN, 'N/A')
            agm = row.get(AGM_COLUMN, 'N/A')
            zone = row.get(ZONE_COLUMN, 'N/A')
            results.append({
                'branch': str(row[BRANCH_COLUMN]),
                'ri': str(ri),
                'agm': str(agm),
                'zone': str(zone),
            })

    if not results:
        return _empty_result('branch_hierarchy_lookup', f"Branch '{branches[0]}' was not found.")

    res = results[0]
    answer = (
        f"**{res['branch']}** belongs to **RI {res['ri']}** "
        f"(AGM: **{res['agm']}**, Zone: **{res['zone']}**)."
    )
    return {
        'function': 'branch_hierarchy_lookup',
        'answer': answer,
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
    ascending = params.get('ascending', False)
    is_dropout_pct = (spec and spec.metric_id == 'DPP') or metric in ('DPP', 'CY-DPP') or 'dpp' in str(metric_column).lower()

    q_text = params.get('question', '').lower()
    has_ranking_intent = (
        params.get('n') is not None
        or any(k in q_text for k in ('highest', 'lowest', 'worst', 'best', 'top', 'bottom', 'rank', 'ranking', 'which ris', 'which agms', 'which zones', 'which branches'))
    )
    is_specific_single_entity = bool(context and (
        (context.get('ri') and context['ri'] != 'All')
        or (context.get('agm') and context['agm'] != 'All')
        or (context.get('zone') and context['zone'] != 'All')
    )) and not any(w in q_text for w in ('which ris', 'which agms', 'which zones', 'which branches'))

    if is_dropout_pct and not ascending and (has_ranking_intent or not is_specific_single_entity):
        raw_results = aggregate_by_group(
            df, group_column, metric_column, agg=agg, n=None, ascending=False
        )
        results, is_fallback = select_dropout_entities(raw_results, threshold=10.0, explicit_top_n=params.get('n'))
    else:
        results = aggregate_by_group(
            df, group_column, metric_column, agg=agg, n=params.get('n'), ascending=ascending
        )
        is_fallback = False

    raw_year = params.get('raw_year')

    return {
        'function': 'group_metric_aggregate',
        'answer': format_group_aggregate(results, metric, params['group_dimension'], agg, context=context, is_fallback=is_fallback, year=raw_year),
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
        spec = get_default_metric_registry().get(metric)
        kpi_dir = spec.kpi_direction if spec else ('negative' if 'dpp' in metric.lower() or 'dropout' in metric.lower() else 'positive')

        if year == 'yoy' or params.get('direction') in ('positive', 'negative'):
            yoy_pairs = {
                'PP': (resolve_column(index, metric, 'PP', None, 'CY'), resolve_column(index, metric, 'PP', None, 'LY')),
                'PS': (resolve_column(index, metric, 'PS', None, 'CY'), resolve_column(index, metric, 'PS', None, 'LY')),
                'HS': (resolve_column(index, metric, 'HS', None, 'CY'), resolve_column(index, metric, 'HS', None, 'LY')),
            }
            direction = 'improved' if params.get('direction') == 'positive' else ('declined' if params.get('direction') == 'negative' else None)
            agg = 'mean' if metric in ('DPP', 'STR', 'Avg-SPS') else 'sum'
            results = compare_dimensions(df, {}, group_column=None, agg=agg, top=direction, yoy_pairs=yoy_pairs, kpi_direction=kpi_dir)
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
        results = compare_dimensions(df, columns_map, group_column=group_column, agg=agg, top=top, kpi_direction=kpi_dir)
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
    """Calculate overall metric value across current filter scope."""
    metric = params.get('metric') or 'NOOR'
    spec = get_default_metric_registry().get(metric)
    m_key = spec.metric_id if spec else metric
    df = get_prepared_dataframe([m_key], context)

    val = None
    if spec and spec.metric_type == 'derived' and spec.numerator_metric and spec.denominator_metric:
        num_col = spec.numerator_metric
        den_col = spec.denominator_metric
        if num_col not in df.columns:
            num_col = f"CY-{num_col}" if f"CY-{num_col}" in df.columns else f"CY_{num_col}"
        if den_col not in df.columns:
            den_col = f"CY-{den_col}" if f"CY-{den_col}" in df.columns else f"CY_{den_col}"

        if num_col in df.columns and den_col in df.columns:
            n_sum = pd.to_numeric(df[num_col], errors='coerce').sum()
            d_sum = pd.to_numeric(df[den_col], errors='coerce').sum()
            if d_sum > 0:
                val = (n_sum / d_sum) * (100.0 if spec.data_type == 'percentage' else 1.0)

    if val is None:
        column = spec.source_column if spec and spec.source_column in df.columns else (resolve_column(build_metric_index(df), metric) or metric)
        if column not in df.columns:
            if f"CY-{column}" in df.columns:
                column = f"CY-{column}"
            elif f"CY_{column}" in df.columns:
                column = f"CY_{column}"
        if column not in df.columns:
            return _empty_result('scope_total', f'Column not found for {metric}.')
        agg = 'mean' if (spec and spec.data_type == 'percentage') else 'sum'
        val = aggregate_metric_total(df, column, agg=agg)

    val = round(float(val), 2)
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


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Fee Due pre-built orchestrator runners (with Output Projection)
# ---------------------------------------------------------------------------

def _project_fee_data(results: list[dict], target_metric: str | None, group_dim: str = 'Branch') -> list[dict]:
    if not results:
        return []
    if target_metric in (None, 'summary'):
        return results

    sample = results[0]
    entity_key = 'branch'
    for k in ('branch', 'zone', 'ri', 'agm', 's_type'):
        if k in sample:
            entity_key = k
            break

    projected = []
    for rank_idx, item in enumerate(results, start=1):
        row = {entity_key: item[entity_key]}
        if 'rank' in item:
            row['rank'] = item['rank']

        if target_metric == 'LY_FD':
            row['LY_FD'] = item.get('LY_FD', item.get('last_year', 0.0))
        elif target_metric == 'LY_FDC':
            row['LY_FDC'] = int(item.get('LY_FDC', 0))
        elif target_metric == 'CY_A_FD':
            row['CY_A_FD'] = item.get('CY_A_FD', item.get('current_year', 0.0))
        elif target_metric == 'CY_A_FDC':
            row['CY_A_FDC'] = int(item.get('CY_A_FDC', 0))
        elif target_metric == 'CY_A_ZP':
            row['CY_A_ZP'] = int(item.get('CY_A_ZP', 0))
        elif target_metric == 'CY_ZP':
            row['CY_ZP'] = int(item.get('CY_ZP', 0))
        elif target_metric == 'CY_ZP_FD':
            row['CY_ZP_FD'] = item.get('CY_ZP_FD', 0.0)
        elif target_metric == 'CY_FP_BN':
            row['CY_FP_BN'] = int(item.get('CY_FP_BN', 0))
        elif target_metric == 'CY_FN_BN':
            row['CY_FN_BN'] = int(item.get('CY_FN_BN', 0))
        elif target_metric == 'fee_yoy':
            row['LY_FD'] = item.get('LY_FD', item.get('last_year', 0.0))
            row['CY_A_FD'] = item.get('CY_A_FD', item.get('current_year', 0.0))
            row['difference'] = item.get('difference', item.get('change', 0.0))
        elif target_metric == 'books_summary':
            row['CY_FP_BN'] = int(item.get('CY_FP_BN', 0))
            row['CY_FN_BN'] = int(item.get('CY_FN_BN', 0))
        else:
            return results
        projected.append(row)
    return projected


def run_fee_summary(params: dict, context: dict | None = None):
    """
    Fee due snapshot per branch/zone/RI/AGM/S_Type with strict Output Projection.
    """
    fee_metrics = ['CY_A_FD', 'LY_FD', 'CY_A_FDC', 'LY_FDC', 'CY_ZP', 'CY_ZP_FD']
    df = get_prepared_dataframe(fee_metrics, context)

    question = params.get('question', '')
    target_metric = extract_target_metric(question, params.get('metric'))
    group_col = params.get('group_dim') or params.get('group_col')
    n = params.get('n')
    ascending = params.get('ascending', False)

    context_branches = [
        b for b in (context or {}).get('branches', [])
        if str(b).strip().casefold() != 'all'
    ]
    branches = params.get('branches') or context_branches or None

    # Handle global scalar total queries (e.g. "What was the last year 2024-25 fee due amount?")
    if not group_col and not n and not branches and target_metric in ('LY_FD', 'CY_A_FD', 'LY_FDC', 'CY_A_FDC', 'CY_ZP', 'CY_ZP_FD'):
        metric_col = target_metric
        col_values = pd.to_numeric(df[metric_col], errors='coerce').fillna(0) if metric_col in df.columns else pd.Series([0])
        total_val = float(col_values.sum())
        spec = get_default_metric_registry().get(target_metric)
        label = spec.display_name if spec else target_metric
        if 'FD' in target_metric and 'FDC' not in target_metric:
            formatted_val = f"\u20b9{int(round(total_val)):,}"
        else:
            formatted_val = f"{int(total_val):,}"
        answer = f"Total {label}: {formatted_val}"
        return {
            'function': 'fee_summary',
            'answer': answer,
            'data': [{target_metric: round(total_val, 2)}],
        }

    sort_col = target_metric if target_metric in fee_metrics else params.get('sort_col', 'CY_A_FD')
    columns = params.get('columns') or fee_metrics

    results = fee_summary_by_branch(
        df, columns=columns, branches=branches,
        n=n, sort_col=sort_col, ascending=ascending, group_col=group_col,
    )
    projected_data = _project_fee_data(results, target_metric=target_metric, group_dim=group_col or 'Branch')
    answer = format_fee_summary(results, [sort_col], n=n, ascending=ascending, group_col=group_col, target_metric=target_metric)
    return {
        'function': 'fee_summary',
        'answer': answer,
        'data': projected_data,
    }


def run_fee_books_not_purchased(params: dict, context: dict | None = None):
    """
    Books not purchased per branch/zone/RI/AGM/S_Type with strict Output Projection.
    """
    df = get_prepared_dataframe(['CY_FP_BN', 'CY_FN_BN'], context)

    question = params.get('question', '')
    target_metric = extract_target_metric(question, params.get('metric'))
    group_col = params.get('group_dim') or params.get('group_col')
    mode = params.get('mode', 'both')
    n = params.get('n')
    ascending = params.get('ascending', False)

    context_branches = [
        b for b in (context or {}).get('branches', [])
        if str(b).strip().casefold() != 'all'
    ]
    branches = params.get('branches') or context_branches or None

    # Handle global scalar total queries (e.g. "Show count of students who did not pay fee and did not purchase books")
    if not group_col and not n and not branches and target_metric in ('CY_FP_BN', 'CY_FN_BN'):
        metric_col = target_metric
        col_values = pd.to_numeric(df[metric_col], errors='coerce').fillna(0) if metric_col in df.columns else pd.Series([0])
        total_count = int(col_values.sum())
        label = "Fee Paid But Books Not Purchased" if target_metric == 'CY_FP_BN' else "Fee Not Paid & Books Not Purchased"
        answer = f"Total Students ({label}): {total_count:,}"
        return {
            'function': 'fee_books_not_purchased',
            'answer': answer,
            'data': [{target_metric: total_count}],
        }

    results = fee_books_not_purchased(df, mode=mode, n=n, ascending=ascending, branches=branches, group_col=group_col)
    projected_data = _project_fee_data(results, target_metric=target_metric, group_dim=group_col or 'Branch')
    answer = format_fee_books(results, mode=mode, group_col=group_col, target_metric=target_metric)
    return {
        'function': 'fee_books_not_purchased',
        'answer': answer,
        'data': projected_data,
    }


def run_fee_yoy_comparison(params: dict, context: dict | None = None):
    """
    Year-over-year fee due comparison (LY_FD → CY_A_FD) with strict Output Projection.
    """
    df = get_prepared_dataframe(['CY_A_FD', 'LY_FD'], context)

    question = params.get('question', '')
    target_metric = extract_target_metric(question, params.get('metric')) or 'fee_yoy'
    group_col = params.get('group_dim') or params.get('group_col')
    n = params.get('n')
    ascending = params.get('ascending', False)

    context_branches = [
        b for b in (context or {}).get('branches', [])
        if str(b).strip().casefold() != 'all'
    ]
    branches = params.get('branches') or context_branches or None

    results = fee_yoy_comparison(df, n=n, ascending=ascending, branches=branches, group_col=group_col)
    projected_data = _project_fee_data(results, target_metric=target_metric, group_dim=group_col or 'Branch')
    answer = format_fee_yoy(results, ascending=ascending, group_col=group_col)
    return {
        'function': 'fee_yoy_comparison',
        'answer': answer,
        'data': projected_data,
    }


# ---------------------------------------------------------------------------
# Revenue vs Salary pre-built orchestrator runners (with Output Projection)
# ---------------------------------------------------------------------------

from .params import extract_compared_segments, extract_target_metric


def _map_rev_sal_group_col(group_dim: str | None) -> str:
    if not group_dim:
        return 'Branch'
    g_lower = str(group_dim).lower()
    if 'agm' in g_lower:
        return 'AGM'
    if 'ri' in g_lower:
        return 'RI'
    if 'zone' in g_lower:
        return 'Zone'
    return 'Branch'


def _project_summary_data(res: dict, target_metric: str) -> dict:
    if not res:
        return {}
    if target_metric == 'summary':
        return res

    base = {
        'branch_count': res.get('branch_count', 0),
        'segment': res.get('segment', 'TOT'),
        'segment_label': res.get('segment_label', 'Total Overall'),
    }
    if target_metric == 'total_students':
        base['total_students'] = res.get('total_students', 0)
    elif target_metric == 'total_employees':
        base['total_employees'] = res.get('total_employees', 0)
    elif target_metric == 'total_salary':
        base['total_salary'] = res.get('total_salary', 0.0)
    elif target_metric == 'total_revenue':
        base['total_revenue'] = res.get('total_revenue', 0.0)
    elif target_metric == 'surplus':
        base['surplus'] = res.get('surplus', 0.0)
        base['total_revenue'] = res.get('total_revenue', 0.0)
        base['total_salary'] = res.get('total_salary', 0.0)
    elif target_metric == 'cost_per_student':
        base['cost_per_student'] = res.get('cost_per_student', 0.0)
    elif target_metric == 'fee_average':
        base['fee_average'] = res.get('fee_average', 0.0)
    elif target_metric == 'salary_vs_revenue_pct':
        base['salary_vs_revenue_pct'] = res.get('salary_vs_revenue_pct', 0.0)
    elif target_metric == 'student_teacher_ratio':
        base['student_teacher_ratio'] = res.get('student_teacher_ratio', 0.0)
    elif target_metric == 'revenue_vs_salary':
        base['total_revenue'] = res.get('total_revenue', 0.0)
        base['total_salary'] = res.get('total_salary', 0.0)
        base['surplus'] = res.get('surplus', 0.0)
        base['salary_vs_revenue_pct'] = res.get('salary_vs_revenue_pct', 0.0)
    else:
        return res
    return base


def _project_ranking_data(results: list[dict], target_metric: str) -> list[dict]:
    if target_metric == 'summary':
        return results

    projected = []
    for item in results:
        row = {'rank': item['rank'], 'entity': item['entity']}
        if target_metric == 'total_students':
            row['total_students'] = item['total_students']
        elif target_metric == 'total_employees':
            row['total_employees'] = item['total_employees']
        elif target_metric == 'total_salary':
            row['total_salary'] = item['total_salary']
        elif target_metric == 'total_revenue':
            row['total_revenue'] = item['total_revenue']
        elif target_metric == 'surplus':
            row['surplus'] = item['surplus']
            row['total_revenue'] = item['total_revenue']
            row['total_salary'] = item['total_salary']
        elif target_metric == 'cost_per_student':
            row['cost_per_student'] = item['cost_per_student']
        elif target_metric == 'fee_average':
            row['fee_average'] = item['fee_average']
        elif target_metric == 'salary_vs_revenue_pct':
            row['salary_vs_revenue_pct'] = item['salary_vs_revenue_pct']
        elif target_metric == 'student_teacher_ratio':
            row['student_teacher_ratio'] = item['student_teacher_ratio']
        elif target_metric == 'revenue_vs_salary':
            row['total_revenue'] = item['total_revenue']
            row['total_salary'] = item['total_salary']
            row['surplus'] = item['surplus']
            row['salary_vs_revenue_pct'] = item['salary_vs_revenue_pct']
        else:
            projected.append(item)
            continue
        projected.append(row)
    return projected


def _project_segment_data(results: list[dict], target_metric: str, segments_filter: list[str] | None = None) -> list[dict]:
    filtered = results
    if segments_filter:
        filtered = [r for r in results if r['segment'] in segments_filter]
        if not filtered:
            filtered = results
    if target_metric == 'summary' and not segments_filter:
        return results

    projected = []
    for item in filtered:
        row = {'segment': item['segment'], 'segment_name': item['segment_label']}
        if target_metric == 'total_students':
            row['student_count'] = item['total_students']
        elif target_metric == 'total_employees':
            row['employee_count'] = item['total_employees']
        elif target_metric == 'total_salary':
            row['total_salary'] = item['total_salary']
        elif target_metric == 'total_revenue':
            row['total_revenue'] = item['total_revenue']
        elif target_metric == 'surplus':
            row['surplus'] = item['surplus']
        elif target_metric == 'cost_per_student':
            row['cost_per_student'] = item['cost_per_student']
        elif target_metric == 'fee_average':
            row['fee_average'] = item['fee_average']
        elif target_metric == 'salary_vs_revenue_pct':
            row['salary_vs_revenue_pct'] = item['salary_vs_revenue_pct']
        elif target_metric == 'student_teacher_ratio':
            row['student_teacher_ratio'] = item['student_teacher_ratio']
        else:
            row.update({
                'total_revenue': item['total_revenue'],
                'total_salary': item['total_salary'],
                'surplus': item['surplus'],
                'salary_vs_revenue_pct': item['salary_vs_revenue_pct'],
            })
        projected.append(row)
    return projected


def run_revenue_salary_summary(params: dict, context: dict | None = None):
    """
    Computes aggregated summary metrics for Revenue vs Salary dataset
    and applies intent-based output projection.
    """
    df = get_prepared_dataframe(['TOT_REV_N'], context=context, primary_dataset_id='revenue_vs_salary')
    segment = params.get('segment') or 'TOT'
    res = revenue_salary_summary(df, segment=segment)

    question = params.get('question', '')
    target_metric = extract_target_metric(question, params.get('metric'))

    answer = format_revenue_salary_summary(res, target_metric=target_metric)
    data = _project_summary_data(res, target_metric=target_metric)
    return {
        'function': 'revenue_salary_summary',
        'answer': answer,
        'data': data,
    }


def run_revenue_salary_segment_comparison(params: dict, context: dict | None = None):
    """
    Compares metrics across academic segments (PP, LPS, UPS, HS, ACD, AD_AC)
    and applies intent-based output projection.
    """
    df = get_prepared_dataframe(['TOT_REV_N'], context=context, primary_dataset_id='revenue_vs_salary')
    results = revenue_salary_segment_comparison(df)

    question = params.get('question', '')
    target_metric = extract_target_metric(question, params.get('metric'))
    segments_filter = extract_compared_segments(question)

    answer = format_revenue_salary_segment_comparison(results, target_metric=target_metric, segments_filter=segments_filter)
    data = _project_segment_data(results, target_metric=target_metric, segments_filter=segments_filter)
    return {
        'function': 'revenue_salary_segment_comparison',
        'answer': answer,
        'data': data,
    }


def run_revenue_salary_ranking(params: dict, context: dict | None = None):
    """
    Ranks entities (Branch, RI, Zone, AGM) by a Revenue vs Salary metric
    and applies intent-based output projection.
    """
    df = get_prepared_dataframe(['TOT_REV_N'], context=context, primary_dataset_id='revenue_vs_salary')
    metric = params.get('metric') or 'TOT_REV_N'
    group_dim = params.get('group_dim') or params.get('level') or 'Branch'
    group_col = _map_rev_sal_group_col(group_dim)
    n = params.get('n', 5)
    ascending = params.get('ascending', False)

    results = revenue_salary_ranking(df, metric=metric, group_col=group_col, n=n, ascending=ascending)
    spec = get_default_metric_registry().get(metric)
    metric_label = spec.display_name if spec else metric

    question = params.get('question', '')
    target_metric = extract_target_metric(question, metric)

    answer = format_revenue_salary_ranking(results, metric_label, target_metric=target_metric, group_dim=group_col, ascending=ascending)
    data = _project_ranking_data(results, target_metric=target_metric)
    return {
        'function': 'revenue_salary_ranking',
        'answer': answer,
        'data': data,
    }


def run_revenue_salary_threshold(params: dict, context: dict | None = None):
    """
    Filters entities matching threshold conditions (e.g. revenue > 1 crore)
    and applies intent-based output projection.
    """
    df = get_prepared_dataframe(['TOT_REV_N'], context=context, primary_dataset_id='revenue_vs_salary')
    metric = params.get('metric') or 'TOT_REV_N'
    op = params.get('op') or '>'
    value = float(params.get('value', 10000000.0))
    group_dim = params.get('group_dim') or 'Branch'
    group_col = _map_rev_sal_group_col(group_dim)

    results = revenue_salary_threshold_filter(df, metric=metric, operator=op, value=value, group_col=group_col)
    spec = get_default_metric_registry().get(metric)
    metric_label = spec.display_name if spec else metric

    question = params.get('question', '')
    target_metric = extract_target_metric(question, metric)

    answer = format_revenue_salary_threshold(results, metric_label, target_metric=target_metric, op=op, value=value, group_dim=group_col)
    data = _project_ranking_data(results, target_metric=target_metric)
    return {
        'function': 'revenue_salary_threshold',
        'answer': answer,
        'data': data,
    }


def run_revenue_salary_surplus(params: dict, context: dict | None = None):
    """
    Handles net surplus queries (Surplus = Revenue - Salary).
    """
    if params.get('ranking') or params.get('n') or params.get('group_dim'):
        params['metric'] = 'SURPLUS'
        return run_revenue_salary_ranking(params, context=context)
    return run_revenue_salary_summary(params, context=context)


def run_revenue_salary_ratio(params: dict, context: dict | None = None):
    """
    Handles ratio / percentage / per-student queries (Fee Average, Cost per Student, Salary vs Revenue %, STR).
    """
    if params.get('ranking') or params.get('n') or params.get('group_dim'):
        return run_revenue_salary_ranking(params, context=context)
    return run_revenue_salary_summary(params, context=context)


def run_ri_dropout_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete 8-section RI Dropout Statistics Review for the Main Report domain.
    """
    df = get_dataframe()
    context = context or {}
    ri_name = context.get('ri') or params.get('ri') or params.get('entity_name') or params.get('question', '')
    if not ri_name or str(ri_name).lower() == 'all':
        return run_entity_summary(params, context)

    resolved_ri = resolve_single_entity(str(ri_name), df[RI_COLUMN].dropna().unique(), 'ri')
    if not resolved_ri:
        return {
            'function': 'ri_dropout_statistics',
            'answer': f"I couldn't find a matching RI for '{ri_name}'. Please check the RI name and try again.",
            'data': [],
        }

    analysis = build_ri_analysis(df, ri_name=resolved_ri, context=context)
    answer = render_operation_response(analysis)

    return {
        'function': 'ri_dropout_statistics',
        'answer': answer,
        'data': analysis.rows,
        'analysis': analysis,
    }


def run_agm_dropout_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete 11-section AGM Dropout Statistics Review for the Main Report domain.
    """
    df = get_dataframe()
    context = context or {}
    agm_name = context.get('agm') or params.get('agm') or params.get('entity_name') or params.get('question', '')
    if not agm_name or str(agm_name).lower() == 'all':
        return run_entity_summary(params, context)

    resolved_agm = resolve_single_entity(str(agm_name), df[AGM_COLUMN].dropna().unique(), 'agm')
    if not resolved_agm:
        return {
            'function': 'agm_dropout_statistics',
            'answer': f"I couldn't find a matching AGM for '{agm_name}'. Please check the AGM name and try again.",
            'data': [],
        }

    analysis = build_agm_analysis(df, agm_name=resolved_agm, context=context)
    answer = render_operation_response(analysis)

    return {
        'function': 'agm_dropout_statistics',
        'answer': answer,
        'data': analysis.rows,
        'analysis': analysis,
    }


def run_branch_dropout_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete 10-section Branch Dropout Statistics Review for the Main Report domain.
    """
    df = get_dataframe()
    context = context or {}
    branch_name = (
        context.get('branch')
        or (context.get('branches')[0] if isinstance(context.get('branches'), list) and len(context.get('branches')) > 0 and str(context.get('branches')[0]).lower() != 'all' else None)
        or params.get('branch')
        or (params.get('branches')[0] if isinstance(params.get('branches'), list) and len(params.get('branches')) > 0 and str(params.get('branches')[0]).lower() != 'all' else None)
        or params.get('entity_name')
        or params.get('question', '')
    )
    if not branch_name or str(branch_name).lower() == 'all':
        return run_entity_summary(params, context)

    resolved_branch = resolve_single_entity(str(branch_name), df[BRANCH_COLUMN].dropna().unique(), 'branch')
    if not resolved_branch:
        raw_label = str(branch_name).strip()
        return {
            'function': 'branch_dropout_statistics',
            'answer': f"I couldn't find a matching branch for '{raw_label}'. Please check the branch name and try again.",
            'data': [],
        }

    analysis = build_branch_analysis(df, branch_name=resolved_branch, context=context)
    answer = render_operation_response(analysis)

    return {
        'function': 'branch_dropout_statistics',
        'answer': answer,
        'data': analysis.rows,
        'analysis': analysis,
    }


def run_zone_dropout_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete Zone Dropout Statistics Review for the Main Report domain.
    """
    df = get_dataframe()
    context = context or {}
    zone_name = (
        context.get('zone')
        or params.get('zone')
        or params.get('entity_name')
        or params.get('question', '')
    )
    if not zone_name or str(zone_name).lower() == 'all':
        return run_entity_summary(params, context)

    resolved_zone = resolve_single_entity(str(zone_name), df[ZONE_COLUMN].dropna().unique(), 'zone')
    if not resolved_zone:
        raw_label = str(zone_name).strip()
        return {
            'function': 'zone_dropout_statistics',
            'answer': f"I couldn't find a matching zone for '{raw_label}'. Please check the zone name and try again.",
            'data': [],
        }

    merged_context = dict(context or {})
    merged_context['zone'] = resolved_zone
    res = run_entity_summary(params, merged_context)
    res['function'] = 'zone_dropout_statistics'
    return res


ALL_DOMAIN_STATISTICS = ['dropout', 'fee_due', 'revenue_salary', 'teacher_student_ratio']


def run_ri_statistics(params: dict, context: dict | None = None):
    """
    Executes an overall 4-domain Statistics Review for an RI (Dropout, Fee Due, Revenue vs Salary, STR).
    """
    context = context or {}
    ri_name = context.get('ri') or params.get('ri') or params.get('entity_name') or params.get('question', '')
    if not ri_name or str(ri_name).lower() == 'all':
        return run_entity_summary(params, context)

    df = get_dataframe()
    candidate_ris = list(df[RI_COLUMN].dropna().unique()) if RI_COLUMN in df.columns else []
    resolved_ri = resolve_single_entity(str(ri_name), candidate_ris, 'ri') if ri_name != 'All' else 'All'
    if not resolved_ri:
        resolved_ri = str(ri_name).strip()

    return run_ri_combined_statistics(ri=resolved_ri, statistics=ALL_DOMAIN_STATISTICS, params=params, context=context)


def run_agm_statistics(params: dict, context: dict | None = None):
    """
    Executes an overall 4-domain Statistics Review for an AGM (Dropout, Fee Due, Revenue vs Salary, STR).
    """
    context = context or {}
    agm_name = context.get('agm') or params.get('agm') or params.get('entity_name') or params.get('question', '')
    if not agm_name or str(agm_name).lower() == 'all':
        return run_entity_summary(params, context)

    df = get_dataframe()
    candidate_agms = list(df[AGM_COLUMN].dropna().unique()) if AGM_COLUMN in df.columns else []
    resolved_agm = resolve_single_entity(str(agm_name), candidate_agms, 'agm') if agm_name != 'All' else 'All'
    if not resolved_agm:
        resolved_agm = str(agm_name).strip()

    return run_agm_combined_statistics(agm=resolved_agm, statistics=ALL_DOMAIN_STATISTICS, params=params, context=context)


def run_branch_statistics(params: dict, context: dict | None = None):
    """
    Executes an overall 4-domain Statistics Review for a Branch (Dropout, Fee Due, Revenue vs Salary, STR).
    """
    context = context or {}
    branch_name = (
        context.get('branch')
        or (context.get('branches')[0] if isinstance(context.get('branches'), list) and len(context.get('branches')) > 0 and str(context.get('branches')[0]).lower() != 'all' else None)
        or params.get('branch')
        or (params.get('branches')[0] if isinstance(params.get('branches'), list) and len(params.get('branches')) > 0 and str(params.get('branches')[0]).lower() != 'all' else None)
        or params.get('entity_name')
        or params.get('question', '')
    )
    if not branch_name or str(branch_name).lower() == 'all':
        return run_entity_summary(params, context)

    df = get_dataframe()
    candidate_branches = list(df[BRANCH_COLUMN].dropna().unique()) if BRANCH_COLUMN in df.columns else []
    resolved_branch = resolve_single_entity(str(branch_name), candidate_branches, 'branch') if branch_name != 'All' else 'All'
    if not resolved_branch:
        resolved_branch = str(branch_name).strip()

    return run_branch_combined_statistics(branch=resolved_branch, statistics=ALL_DOMAIN_STATISTICS, params=params, context=context)


run_zone_statistics = run_zone_dropout_statistics
run_ri_analysis = run_ri_statistics


def run_agm_fee_due_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete Fee Due Statistics Review for an AGM.
    """
    context = context or {}
    agm_name = context.get('agm') or params.get('agm') or params.get('entity_name')
    if not agm_name:
        q = params.get('question', '')
        m = re.search(r'agm\s+([^fee|due|stat|rep|rev|ana]+)', q, flags=re.IGNORECASE)
        if m:
            agm_name = m.group(1).strip()
    if not agm_name or str(agm_name).lower() == 'all':
        agm_name = 'All'

    df = get_prepared_dataframe(['CY_A_FD'], primary_dataset_id='fee_analysis')
    candidate_agms = list(df['AGM Name'].dropna().unique()) if 'AGM Name' in df.columns else (list(df['AGM'].dropna().unique()) if 'AGM' in df.columns else [])
    resolved_agm = resolve_single_entity(str(agm_name), candidate_agms, 'agm') if agm_name != 'All' else None
    if not resolved_agm:
        resolved_agm = format_display_ri_name(str(agm_name)) if agm_name != 'All' else (candidate_agms[0] if candidate_agms else 'All')

    analysis = build_agm_fee_due_analysis(df, agm_name=resolved_agm, context=context)
    answer = render_operation_response(analysis)

    return {
        'function': 'agm_fee_due_statistics',
        'answer': answer,
        'data': analysis.rows,
        'analysis': analysis,
    }


def run_ri_fee_due_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete Fee Due Statistics Review for an RI.
    """
    context = context or {}
    ri_name = context.get('ri') or params.get('ri') or params.get('entity_name')
    if not ri_name:
        q = params.get('question', '')
        m = re.search(r'ri\s+([^fee|due|stat|rep|rev|ana]+)', q, flags=re.IGNORECASE)
        if m:
            ri_name = m.group(1).strip()
    if not ri_name or str(ri_name).lower() == 'all':
        ri_name = 'All'

    df = get_prepared_dataframe(['CY_A_FD'], primary_dataset_id='fee_analysis')
    candidate_ris = list(df['RI Name'].dropna().unique()) if 'RI Name' in df.columns else (list(df['RI'].dropna().unique()) if 'RI' in df.columns else [])
    resolved_ri = resolve_single_entity(str(ri_name), candidate_ris, 'ri') if ri_name != 'All' else None
    if not resolved_ri:
        resolved_ri = format_display_ri_name(str(ri_name)) if ri_name != 'All' else (candidate_ris[0] if candidate_ris else 'All')

    analysis = build_ri_fee_due_analysis(df, ri_name=resolved_ri, context=context)
    answer = render_operation_response(analysis)

    return {
        'function': 'ri_fee_due_statistics',
        'answer': answer,
        'data': analysis.rows,
        'analysis': analysis,
    }


def run_branch_fee_due_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete Fee Due Statistics Review for a single Branch.
    """
    context = context or {}
    branch_name = (
        context.get('branch')
        or (context.get('branches')[0] if isinstance(context.get('branches'), list) and len(context.get('branches')) > 0 and str(context.get('branches')[0]).lower() != 'all' else None)
        or params.get('branch')
        or (params.get('branches')[0] if isinstance(params.get('branches'), list) and len(params.get('branches')) > 0 and str(params.get('branches')[0]).lower() != 'all' else None)
        or params.get('entity_name')
    )
    if not branch_name:
        q = params.get('question', '')
        m = re.search(r'(?:branch\s+)?([A-Za-z0-9\s]+?)\s+(?:fee|due|stat|rep|rev|ana)', q, flags=re.IGNORECASE)
        if m:
            branch_name = m.group(1).strip()
    if not branch_name or str(branch_name).lower() == 'all':
        branch_name = 'All'

    df = get_prepared_dataframe(['CY_A_FD'], primary_dataset_id='fee_analysis')
    candidate_branches = list(df['Branch'].dropna().unique()) if 'Branch' in df.columns else []
    resolved_branch = resolve_single_entity(str(branch_name), candidate_branches, 'branch') if branch_name != 'All' else None
    if not resolved_branch:
        resolved_branch = str(branch_name).strip() if branch_name != 'All' else (candidate_branches[0] if candidate_branches else 'All')

    analysis = build_branch_fee_due_analysis(df, branch_name=resolved_branch, context=context)
    answer = render_operation_response(analysis)

    return {
        'function': 'branch_fee_due_statistics',
        'answer': answer,
        'data': analysis.rows,
        'analysis': analysis,
    }


def run_agm_revenue_salary_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete Revenue vs Salary Statistics Review for an AGM.
    """
    context = context or {}
    agm_name = context.get('agm') or params.get('agm') or params.get('entity_name')
    if not agm_name:
        q = params.get('question', '')
        m = re.search(r'agm\s+([^fee|due|stat|rep|rev|sal|ana]+)', q, flags=re.IGNORECASE)
        if m:
            agm_name = m.group(1).strip()
    if not agm_name or str(agm_name).lower() == 'all':
        agm_name = 'All'

    df = get_prepared_dataframe(['TOT_REV_N'], primary_dataset_id='revenue_vs_salary')
    candidate_agms = list(df['AGM Name'].dropna().unique()) if 'AGM Name' in df.columns else (list(df['AGM'].dropna().unique()) if 'AGM' in df.columns else [])
    resolved_agm = resolve_single_entity(str(agm_name), candidate_agms, 'agm') if agm_name != 'All' else None
    if not resolved_agm:
        resolved_agm = format_display_ri_name(str(agm_name)) if agm_name != 'All' else (candidate_agms[0] if candidate_agms else 'All')

    analysis = build_agm_revenue_salary_analysis(df, agm_name=resolved_agm, context=context)
    answer = render_operation_response(analysis)

    return {
        'function': 'agm_revenue_salary_statistics',
        'answer': answer,
        'data': analysis.rows,
        'analysis': analysis,
    }


def run_ri_revenue_salary_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete Revenue vs Salary Statistics Review for an RI.
    """
    context = context or {}
    ri_name = context.get('ri') or params.get('ri') or params.get('entity_name')
    if not ri_name:
        q = params.get('question', '')
        m = re.search(r'ri\s+([^fee|due|stat|rep|rev|sal|ana]+)', q, flags=re.IGNORECASE)
        if m:
            ri_name = m.group(1).strip()
    if not ri_name or str(ri_name).lower() == 'all':
        ri_name = 'All'

    df = get_prepared_dataframe(['TOT_REV_N'], primary_dataset_id='revenue_vs_salary')
    candidate_ris = list(df['RI Name'].dropna().unique()) if 'RI Name' in df.columns else (list(df['RI'].dropna().unique()) if 'RI' in df.columns else [])
    resolved_ri = resolve_single_entity(str(ri_name), candidate_ris, 'ri') if ri_name != 'All' else None
    if not resolved_ri:
        resolved_ri = format_display_ri_name(str(ri_name)) if ri_name != 'All' else (candidate_ris[0] if candidate_ris else 'All')

    analysis = build_ri_revenue_salary_analysis(df, ri_name=resolved_ri, context=context)
    answer = render_operation_response(analysis)

    return {
        'function': 'ri_revenue_salary_statistics',
        'answer': answer,
        'data': analysis.rows,
        'analysis': analysis,
    }


def run_branch_revenue_salary_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete Revenue vs Salary Statistics Review for a single Branch.
    """
    context = context or {}
    branch_name = (
        context.get('branch')
        or (context.get('branches')[0] if isinstance(context.get('branches'), list) and len(context.get('branches')) > 0 and str(context.get('branches')[0]).lower() != 'all' else None)
        or params.get('branch')
        or (params.get('branches')[0] if isinstance(params.get('branches'), list) and len(params.get('branches')) > 0 and str(params.get('branches')[0]).lower() != 'all' else None)
        or params.get('entity_name')
    )
    if not branch_name:
        q = params.get('question', '')
        m = re.search(r'(?:branch\s+)?([A-Za-z0-9\s]+?)\s+(?:fee|due|stat|rep|rev|sal|ana)', q, flags=re.IGNORECASE)
        if m:
            branch_name = m.group(1).strip()
    if not branch_name or str(branch_name).lower() == 'all':
        branch_name = 'All'

    df = get_prepared_dataframe(['TOT_REV_N'], primary_dataset_id='revenue_vs_salary')
    candidate_branches = list(df['Branch'].dropna().unique()) if 'Branch' in df.columns else []
    resolved_branch = resolve_single_entity(str(branch_name), candidate_branches, 'branch') if branch_name != 'All' else None
    if not resolved_branch:
        resolved_branch = str(branch_name).strip() if branch_name != 'All' else (candidate_branches[0] if candidate_branches else 'All')

    analysis = build_branch_revenue_salary_analysis(df, branch_name=resolved_branch, context=context)
    answer = render_operation_response(analysis)

    return {
        'function': 'branch_revenue_salary_statistics',
        'answer': answer,
        'data': analysis.rows,
        'analysis': analysis,
    }


def run_agm_teacher_student_ratio_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete Teacher Student Ratio Statistics Review for an AGM.
    """
    context = context or {}
    agm_name = context.get('agm') or params.get('agm') or params.get('entity_name')
    if not agm_name:
        q = params.get('question', '')
        m = re.search(r'agm\s+([^teacher|student|staff|ratio|stat|rep|rev|ana]+)', q, flags=re.IGNORECASE)
        if m:
            agm_name = m.group(1).strip()
    if not agm_name or str(agm_name).lower() == 'all':
        agm_name = 'All'

    df = get_prepared_dataframe(['CY-STR'])
    candidate_agms = list(df['AGM Name'].dropna().unique()) if 'AGM Name' in df.columns else (list(df['AGM'].dropna().unique()) if 'AGM' in df.columns else [])
    resolved_agm = resolve_single_entity(str(agm_name), candidate_agms, 'agm') if agm_name != 'All' else None
    if not resolved_agm:
        resolved_agm = format_display_ri_name(str(agm_name)) if agm_name != 'All' else (candidate_agms[0] if candidate_agms else 'All')

    analysis = build_agm_teacher_student_ratio_analysis(df, agm_name=resolved_agm, context=context)
    answer = render_operation_response(analysis)

    return {
        'function': 'agm_teacher_student_ratio_statistics',
        'answer': answer,
        'data': analysis.rows,
        'analysis': analysis,
    }


def run_ri_teacher_student_ratio_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete Teacher Student Ratio Statistics Review for an RI.
    """
    context = context or {}
    ri_name = context.get('ri') or params.get('ri') or params.get('entity_name')
    if not ri_name:
        q = params.get('question', '')
        m = re.search(r'ri\s+([^teacher|student|staff|ratio|stat|rep|rev|ana]+)', q, flags=re.IGNORECASE)
        if m:
            ri_name = m.group(1).strip()
    if not ri_name or str(ri_name).lower() == 'all':
        ri_name = 'All'

    df = get_prepared_dataframe(['CY-STR'])
    candidate_ris = list(df['RI Name'].dropna().unique()) if 'RI Name' in df.columns else (list(df['RI'].dropna().unique()) if 'RI' in df.columns else [])
    resolved_ri = resolve_single_entity(str(ri_name), candidate_ris, 'ri') if ri_name != 'All' else None
    if not resolved_ri:
        resolved_ri = format_display_ri_name(str(ri_name)) if ri_name != 'All' else (candidate_ris[0] if candidate_ris else 'All')

    analysis = build_ri_teacher_student_ratio_analysis(df, ri_name=resolved_ri, context=context)
    answer = render_operation_response(analysis)

    return {
        'function': 'ri_teacher_student_ratio_statistics',
        'answer': answer,
        'data': analysis.rows,
        'analysis': analysis,
    }


def run_branch_teacher_student_ratio_statistics(params: dict, context: dict | None = None):
    """
    Executes a complete Teacher Student Ratio Statistics Review for a single Branch.
    """
    context = context or {}
    branch_name = (
        context.get('branch')
        or (context.get('branches')[0] if isinstance(context.get('branches'), list) and len(context.get('branches')) > 0 and str(context.get('branches')[0]).lower() != 'all' else None)
        or params.get('branch')
        or (params.get('branches')[0] if isinstance(params.get('branches'), list) and len(params.get('branches')) > 0 and str(params.get('branches')[0]).lower() != 'all' else None)
        or params.get('entity_name')
    )
    if not branch_name:
        q = params.get('question', '')
        m = re.search(r'(?:branch\s+)?([A-Za-z0-9\s]+?)\s+(?:teacher|student|staff|ratio|stat|rep|rev|ana)', q, flags=re.IGNORECASE)
        if m:
            branch_name = m.group(1).strip()
    if not branch_name or str(branch_name).lower() == 'all':
        branch_name = 'All'

    df = get_prepared_dataframe(['CY-STR'])
    candidate_branches = list(df['Branch'].dropna().unique()) if 'Branch' in df.columns else []
    resolved_branch = resolve_single_entity(str(branch_name), candidate_branches, 'branch') if branch_name != 'All' else None
    if not resolved_branch:
        resolved_branch = str(branch_name).strip() if branch_name != 'All' else (candidate_branches[0] if candidate_branches else 'All')

    analysis = build_branch_teacher_student_ratio_analysis(df, branch_name=resolved_branch, context=context)
    answer = render_operation_response(analysis)

    return {
        'function': 'branch_teacher_student_ratio_statistics',
        'answer': answer,
        'data': analysis.rows,
        'analysis': analysis,
    }


def run_entity_summary(params: dict, context: dict | None = None):
    """
    Handles multi-metric organizational entity summary report card requests.
    """
    df = get_dataframe()
    context = context or {}

    def _is_specific(val):
        return bool(val) and str(val).strip().casefold() != 'all'

    if _is_specific(context.get('ri')):
        return run_ri_analysis(params, context)

    df = apply_filter_context(df, context)

    group_dim = params.get('group_dimension') or (
        'Zone' if _is_specific(context.get('zone')) else (
            'RI' if _is_specific(context.get('ri')) else (
                'AGM' if _is_specific(context.get('agm')) else (
                    'Branch' if _is_specific(context.get('branch')) or (isinstance(context.get('branches'), list) and len(context.get('branches')) == 1 and _is_specific(context.get('branches')[0])) else None
                )
            )
        )
    )
    group_col = GROUP_COLUMNS.get(str(group_dim).lower(), group_dim) if group_dim else None

    entity_name = (
        context.get('zone') if _is_specific(context.get('zone')) else (
            context.get('ri') if _is_specific(context.get('ri')) else (
                context.get('agm') if _is_specific(context.get('agm')) else (
                    context.get('branch') if _is_specific(context.get('branch')) else (
                        context.get('branches')[0] if isinstance(context.get('branches'), list) and len(context.get('branches')) == 1 and _is_specific(context.get('branches')[0]) else None
                    )
                )
            )
        )
    )

    res = entity_summary(df, group_column=group_col, entity_name=entity_name)

    answer = format_entity_summary(res)
    return {
        'function': 'entity_summary',
        'answer': answer,
        'data': res.get('records', []),
    }


def run_agm_combined_statistics(agm: str | None = None, statistics: list[str] | None = None, params: dict | None = None, context: dict | None = None):
    params = params or {}
    context = context or {}
    agm_name = agm or context.get('agm') or params.get('agm') or params.get('entity_name') or 'All'
    stats = statistics or params.get('statistics') or []

    results = {}
    if 'dropout' in stats:
        results['dropout'] = run_agm_dropout_statistics({'agm': agm_name, 'entity_name': agm_name}, context=context)
    if 'fee_due' in stats:
        results['fee_due'] = run_agm_fee_due_statistics({'agm': agm_name, 'entity_name': agm_name}, context=context)
    if 'revenue_salary' in stats:
        results['revenue_salary'] = run_agm_revenue_salary_statistics({'agm': agm_name, 'entity_name': agm_name}, context=context)
    if 'teacher_student_ratio' in stats:
        results['teacher_student_ratio'] = run_agm_teacher_student_ratio_statistics({'agm': agm_name, 'entity_name': agm_name}, context=context)

    from .multi_stats import format_combined_statistics
    answer = format_combined_statistics('AGM', str(agm_name), stats, results)
    return {
        'success': True,
        'intent': 'statistics',
        'hierarchy': 'AGM',
        'entity': str(agm_name),
        'requested_statistics': stats,
        'function': 'agm_combined_statistics',
        'answer': answer,
        'data': {
            'entity_type': 'AGM',
            'entity_name': str(agm_name),
            'requested_statistics': stats,
            'results': {k: v.get('data', []) for k, v in results.items()}
        }
    }


def run_ri_combined_statistics(ri: str | None = None, statistics: list[str] | None = None, params: dict | None = None, context: dict | None = None):
    params = params or {}
    context = context or {}
    ri_name = ri or context.get('ri') or params.get('ri') or params.get('entity_name') or 'All'
    stats = statistics or params.get('statistics') or []

    results = {}
    if 'dropout' in stats:
        results['dropout'] = run_ri_dropout_statistics({'ri': ri_name, 'entity_name': ri_name}, context=context)
    if 'fee_due' in stats:
        results['fee_due'] = run_ri_fee_due_statistics({'ri': ri_name, 'entity_name': ri_name}, context=context)
    if 'revenue_salary' in stats:
        results['revenue_salary'] = run_ri_revenue_salary_statistics({'ri': ri_name, 'entity_name': ri_name}, context=context)
    if 'teacher_student_ratio' in stats:
        results['teacher_student_ratio'] = run_ri_teacher_student_ratio_statistics({'ri': ri_name, 'entity_name': ri_name}, context=context)

    from .multi_stats import format_combined_statistics
    answer = format_combined_statistics('RI', str(ri_name), stats, results)
    return {
        'success': True,
        'intent': 'statistics',
        'hierarchy': 'RI',
        'entity': str(ri_name),
        'requested_statistics': stats,
        'function': 'ri_combined_statistics',
        'answer': answer,
        'data': {
            'entity_type': 'RI',
            'entity_name': str(ri_name),
            'requested_statistics': stats,
            'results': {k: v.get('data', []) for k, v in results.items()}
        }
    }


def run_branch_combined_statistics(branch: str | None = None, statistics: list[str] | None = None, params: dict | None = None, context: dict | None = None):
    params = params or {}
    context = context or {}
    branch_name = (
        branch
        or context.get('branch')
        or (context.get('branches')[0] if isinstance(context.get('branches'), list) and len(context.get('branches')) > 0 and str(context.get('branches')[0]).lower() != 'all' else None)
        or params.get('branch')
        or (params.get('branches')[0] if isinstance(params.get('branches'), list) and len(params.get('branches')) > 0 and str(params.get('branches')[0]).lower() != 'all' else None)
        or params.get('entity_name')
        or 'All'
    )
    stats = statistics or params.get('statistics') or []

    results = {}
    if 'dropout' in stats:
        results['dropout'] = run_branch_dropout_statistics({'branch': branch_name, 'entity_name': branch_name}, context=context)
    if 'fee_due' in stats:
        results['fee_due'] = run_branch_fee_due_statistics({'branch': branch_name, 'entity_name': branch_name}, context=context)
    if 'revenue_salary' in stats:
        results['revenue_salary'] = run_branch_revenue_salary_statistics({'branch': branch_name, 'entity_name': branch_name}, context=context)
    if 'teacher_student_ratio' in stats:
        results['teacher_student_ratio'] = run_branch_teacher_student_ratio_statistics({'branch': branch_name, 'entity_name': branch_name}, context=context)

    from .multi_stats import format_combined_statistics
    answer = format_combined_statistics('Branch', str(branch_name), stats, results)
    return {
        'success': True,
        'intent': 'statistics',
        'hierarchy': 'Branch',
        'entity': str(branch_name),
        'requested_statistics': stats,
        'function': 'branch_combined_statistics',
        'answer': answer,
        'data': {
            'entity_type': 'Branch',
            'entity_name': str(branch_name),
            'requested_statistics': stats,
            'results': {k: v.get('data', []) for k, v in results.items()}
        }
    }


def run_multi_statistics(
    hierarchy: str,
    entity: str,
    requested_statistics: list[str] | None = None,
    params: dict | None = None,
    context: dict | None = None,
):
    """
    Generic multi-statistics orchestrator across all hierarchy levels (RI, AGM, Branch).
    Executes only the requested domain functions and combines structured results.
    """
    params = params or {}
    context = context or {}
    stats = requested_statistics or params.get('statistics') or ALL_DOMAIN_STATISTICS

    h_upper = str(hierarchy).strip().upper()
    if h_upper == 'RI':
        return run_ri_combined_statistics(ri=entity, statistics=stats, params=params, context=context)
    elif h_upper == 'BRANCH':
        return run_branch_combined_statistics(branch=entity, statistics=stats, params=params, context=context)
    else:
        return run_agm_combined_statistics(agm=entity, statistics=stats, params=params, context=context)


def run_combined_statistics(params: dict | None = None, context: dict | None = None):
    """
    Common coordinator function for multi-statistics requests.
    """
    params = params or {}
    context = context or {}
    question = params.get('question', '')

    from .multi_stats import extract_requested_statistics, detect_entity_level_and_name
    stats = params.get('statistics') or extract_requested_statistics(question)
    entity_type, entity_name = detect_entity_level_and_name(question, context)

    return run_multi_statistics(entity_type, entity_name, stats, params=params, context=context)



