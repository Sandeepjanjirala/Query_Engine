from __future__ import annotations

import functools
import re

from . import params as p
from .glossary import AGM_COLUMN, BRANCH_COLUMN, RI_COLUMN, ROOM_METRICS, ZONE_COLUMN
from .orchestrator import (
    get_dataframe,
    run_branch_metric_lookup,
    run_branch_scorecard,
    run_calculate_room_ratio,
    run_compare_dimensions,
    run_filter_by_threshold,
    run_group_metric_aggregate,
    run_rank_branches_by_metric,
    run_room_utilization_snapshot,
    run_scope_total,
    run_sections_and_sps_snapshot,
    run_staff_count_summary,
    run_strength_difference_ranking,
    run_top_5_dropout,
    run_year_over_year_change_ranking,
)

PREFUNCTIONS = {
    'top_5_dropout_branches': run_top_5_dropout,
    'rank_branches_by_metric': run_rank_branches_by_metric,
    'branch_metric_lookup': run_branch_metric_lookup,
    'group_metric_aggregate': run_group_metric_aggregate,
    'year_over_year_change_ranking': run_year_over_year_change_ranking,
    'staff_count_summary': run_staff_count_summary,
    'room_utilization_snapshot': run_room_utilization_snapshot,
    'sections_and_sps_snapshot': run_sections_and_sps_snapshot,
    'strength_difference_ranking': run_strength_difference_ranking,
    'branch_scorecard': run_branch_scorecard,
    'filter_by_threshold': run_filter_by_threshold,
    'compare_dimensions': run_compare_dimensions,
    'calculate_room_ratio': run_calculate_room_ratio,
    'scope_total': run_scope_total,
}

_SCORECARD_KEYWORDS = ('scorecard', 'snapshot', 'overview', 'full report', 'all metrics', 'complete summary', 'complete details')
_AGGREGATE_KEYWORDS = ('total', 'sum', 'average', 'avg', 'mean', 'by zone', 'zone wise',
                        'zone-wise', 'by agm', 'agm wise', 'by ri', 'ri wise', 'per zone', 'grouped')


def normalize_question(question: str) -> str:
    return re.sub(r'\s+', ' ', question.strip().lower())


def _safe_branch_names():
    try:
        df = get_dataframe()
    except (FileNotFoundError, ValueError):
        return []
    return df[BRANCH_COLUMN].dropna().unique() if BRANCH_COLUMN in df.columns else []


def _merge_text_entities(question: str, context: dict | None) -> dict:
    merged = dict(context or {})
    try:
        df = get_dataframe()
    except (FileNotFoundError, ValueError):
        return merged

    if BRANCH_COLUMN in df.columns:
        branches = p.extract_known_values(question, df[BRANCH_COLUMN].dropna().unique())
        if branches:
            merged['branches'] = branches

    for key, column in (('zone', ZONE_COLUMN), ('agm', AGM_COLUMN), ('ri', RI_COLUMN)):
        if column in df.columns:
            found = p.extract_known_values(question, df[column].dropna().unique())
            if found:
                merged[key] = found[0]

    return merged


def route_question(question: str):
    """Route any of the 150 natural-language questions to a reusable capability."""
    q = normalize_question(question)

    # --- Original V1 intent: exact match back-compatibility ---
    dropout = any(term in q for term in ('dropout', 'drop out', 'drop-out', 'dropouts', 'dpp'))
    top_five = any(term in q for term in ('top 5', 'top five', 'highest', 'worst', 'maximum', 'max'))
    branch = 'branch' in q or 'branches' in q
    percentage = any(term in q for term in ('percentage', '%', 'percent', 'dpp'))
    n_val = p.extract_n(q, default=5)

    if (
        dropout and top_five and branch and percentage and n_val == 5
        and 'top 10' not in q and 'top 3' not in q and 'top ten' not in q
        and not (
            p.is_yoy_question(q) or p.extract_threshold(q) or p.is_level_comparison(q) or p.is_type_comparison(q)
        )
    ):
        return PREFUNCTIONS['top_5_dropout_branches']

    # --- Extract shared parameters ---
    metric = p.extract_metric(q)
    level = p.extract_level(q)
    type_ = p.extract_type(q)
    year = p.extract_year(q) or 'CY'
    branch_entities = p.extract_known_values(q, _safe_branch_names())
    group_dimension = p.extract_group_dimension(q)

    def bound(fn, **extra_params):
        base_params = {
            'metric': metric,
            'level': level,
            'type': type_,
            'year': year,
            'group_dimension': group_dimension,
        }
        base_params.update(extra_params)

        def handler(context):
            return fn(base_params, _merge_text_entities(question, context))

        return handler

    # 1) Branch scorecard / complete summary
    if any(kw in q for kw in _SCORECARD_KEYWORDS) and (branch_entities or 'this branch' in q):
        return bound(run_branch_scorecard, branches=branch_entities or None)

    # 2) Scope total query (e.g. Q144/Q145)
    if p.is_scope_total_query(q):
        return bound(run_scope_total, metric=metric or 'NOOR')

    # 3) Threshold questions (Q86-Q100, Q141)
    thresh = p.extract_threshold(q)
    if thresh is not None:
        op, val, count_only = thresh
        th_metric = 'vacancy_rate' if 'vacant' in q and ('%' in q or 'percent' in q) else (metric or 'DPP')
        return bound(
            run_filter_by_threshold,
            metric=th_metric,
            op=op,
            threshold=val,
            count_only=count_only,
            group_dimension=group_dimension,
        )

    # 4) Room ratio (Occupancy / Vacancy percentage ranking / lookup) (Q137-Q140)
    ratio_info = p.is_room_ratio_query(q)
    if ratio_info is not None:
        ratio_type, is_ranking, asc = ratio_info
        return bound(
            run_calculate_room_ratio,
            ratio_type=ratio_type,
            n=p.extract_n(q) if is_ranking else None,
            ascending=asc if is_ranking else None,
        )

    # 5) Multi-metric branch lookup (Q43, Q44, Q45)
    multi_metrics = p.extract_multiple_metrics(q)
    if multi_metrics and branch_entities:
        return bound(run_branch_metric_lookup, metrics=multi_metrics, branches=branch_entities)

    # 6) Single branch specific metric lookup (Q33-Q42) - takes precedence over YoY if specific branch entity is named and no YoY explicit phrasing
    if branch_entities and metric and not p.has_ranking_language(q) and not any(
        ph in q for ph in ('compared with', 'compared to', 'from ly to cy', 'than last year', 'vs last year')
    ):
        return bound(run_branch_metric_lookup, metrics=[metric], branches=branch_entities)

    # 7) Dimension Comparisons
    # 7a) Room comparison (Occupied vs Empty) (Q142, Q143)
    if p.is_room_comparison(q):
        return bound(run_compare_dimensions, dimension_type='rooms', group_dimension=group_dimension)

    # 7b) Group YoY comparison (e.g. CY vs LY staff count by RI) (Q148)
    if p.is_yoy_question(q) and group_dimension:
        return bound(
            run_compare_dimensions,
            dimension_type='group_yoy',
            group_dimension=group_dimension,
            metric=metric or 'SC',
        )

    # 7c) Level comparison (PP vs PS vs HS) (Q101-Q115)
    if p.is_level_comparison(q):
        top = 'highest' if any(w in q for w in ('highest', 'most', 'more')) else (
            'lowest' if any(w in q for w in ('lowest', 'least', 'fewest')) else None
        )
        direction = 'positive' if 'improved' in q else ('negative' if 'declined' in q else None)
        yoy_year = 'yoy' if ('cy vs ly' in q or 'compared with last year' in q or direction) else (
            p.extract_year(q) or 'CY'
        )
        return bound(
            run_compare_dimensions,
            dimension_type='level',
            metric=metric or 'DPP',
            top=top,
            direction=direction,
            year=yoy_year,
        )

    # 7d) Admission type comparison (Existing vs New) (Q116-Q130)
    if p.is_type_comparison(q):
        top = 'highest' if any(w in q for w in ('highest', 'higher', 'more')) else (
            'lowest' if any(w in q for w in ('lowest', 'lower', 'less')) else None
        )
        has_both = 'existing' in q and 'new' in q
        return bound(
            run_compare_dimensions,
            dimension_type='type',
            metric=metric or 'DPP',
            group_dimension=group_dimension,
            top=top,
            level=level,
            year=p.extract_year(q) or 'CY',
            has_both_types=has_both,
        )

    # 8) Year-over-Year change / comparison intent (CY vs LY) (Q66-Q85, Q149)
    if p.is_yoy_question(q):
        yoy_metric = metric or 'NS'
        yoy_direction = p.extract_yoy_direction(q)
        return bound(
            run_year_over_year_change_ranking,
            metric=yoy_metric,
            direction=yoy_direction,
            n=p.extract_n(q),
        )

    # 9) Strength difference / net strength difference ranking
    if metric in ('SD', 'NSD'):
        return bound(
            run_strength_difference_ranking,
            n=p.extract_n(q), ascending=p.extract_direction(q) == 'asc',
        )

    # 10) Staff count summary (non-ranking / explicit staff category)
    staff_category = p.extract_staff_category(q)
    if (metric == 'SC' and not p.has_ranking_language(q) and not branch_entities and not group_dimension) or staff_category:
        return bound(
            run_staff_count_summary,
            staff_category=staff_category, branches=branch_entities or None,
        )

    # 11) Room utilization snapshot (non-ranking phrasing, no group/branch)
    if metric in ROOM_METRICS and not p.has_ranking_language(q) and not branch_entities and not group_dimension:
        return bound(run_room_utilization_snapshot, branches=branch_entities or None)

    # 12) Sections & SPS snapshot (non-ranking phrasing, no group/branch)
    if metric in ('NOS', 'Avg-SPS') and not p.has_ranking_language(q) and not branch_entities and not group_dimension:
        return bound(run_sections_and_sps_snapshot, branches=branch_entities or None)

    # 13) Group aggregate by Zone / AGM / RI (Q25-Q29, Q46-Q63, Q133-Q136, Q146)
    if group_dimension and metric:
        agg = p.extract_aggregation(q)
        is_ranking = p.has_ranking_language(q) or 'highest' in q or 'lowest' in q or 'top' in q or 'bottom' in q
        n_val = p.extract_n(q) if is_ranking else None
        asc = p.extract_direction(q) == 'asc'
        return bound(
            run_group_metric_aggregate,
            group_dimension=group_dimension,
            agg=agg,
            n=n_val,
            ascending=asc,
        )

    # 14) Single / multi branch metric lookup (Q33-Q42, Q64, Q65)
    if (branch_entities or 'branch-wise' in q or 'branch wise' in q) and metric and not p.has_ranking_language(q):
        return bound(run_branch_metric_lookup, metrics=[metric], branches=branch_entities or None)

    # 15) Generic top/bottom-N branch ranking by metric (Q1-Q24, Q30, Q131, Q132, Q147, Q150)
    if metric and (branch or p.has_ranking_language(q) or 'fewest' in q):
        return bound(
            run_rank_branches_by_metric,
            n=p.extract_n(q),
            ascending=p.extract_direction(q) == 'asc',
        )

    return None
