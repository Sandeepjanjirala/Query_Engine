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
    run_entity_summary,
    run_fee_books_not_purchased,
    run_fee_summary,
    run_fee_yoy_comparison,
    run_filter_by_threshold,
    run_group_metric_aggregate,
    run_rank_branches_by_metric,
    run_revenue_salary_ranking,
    run_revenue_salary_ratio,
    run_revenue_salary_segment_comparison,
    run_revenue_salary_summary,
    run_revenue_salary_surplus,
    run_revenue_salary_threshold,
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
    'entity_summary': run_entity_summary,
    'filter_by_threshold': run_filter_by_threshold,
    'compare_dimensions': run_compare_dimensions,
    'calculate_room_ratio': run_calculate_room_ratio,
    'scope_total': run_scope_total,
    # Fee Due capabilities
    'fee_summary': run_fee_summary,
    'fee_books_not_purchased': run_fee_books_not_purchased,
    'fee_yoy_comparison': run_fee_yoy_comparison,
    # Revenue vs Salary capabilities
    'revenue_salary_summary': run_revenue_salary_summary,
    'revenue_salary_segment_comparison': run_revenue_salary_segment_comparison,
    'revenue_salary_ranking': run_revenue_salary_ranking,
    'revenue_salary_threshold': run_revenue_salary_threshold,
    'revenue_salary_surplus': run_revenue_salary_surplus,
    'revenue_salary_ratio': run_revenue_salary_ratio,
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

    q_branches = p.extract_known_values(question, df[BRANCH_COLUMN].dropna().unique()) if BRANCH_COLUMN in df.columns else []
    q_zones = p.extract_known_values(question, df[ZONE_COLUMN].dropna().unique()) if ZONE_COLUMN in df.columns else []
    q_agms = p.extract_known_values(question, df[AGM_COLUMN].dropna().unique()) if AGM_COLUMN in df.columns else []
    q_ris = p.extract_known_values(question, df[RI_COLUMN].dropna().unique()) if RI_COLUMN in df.columns else []

    if q_branches:
        merged['branches'] = q_branches
        if not q_ris: merged['ri'] = 'All'
        if not q_zones: merged['zone'] = 'All'
        if not q_agms: merged['agm'] = 'All'

    if q_ris:
        merged['ri'] = q_ris[0]
        if not q_branches: merged['branches'] = ['All']
        if not q_zones: merged['zone'] = 'All'
        if not q_agms: merged['agm'] = 'All'

    if q_zones:
        merged['zone'] = q_zones[0]
        if not q_branches: merged['branches'] = ['All']
        if not q_ris: merged['ri'] = 'All'
        if not q_agms: merged['agm'] = 'All'

    if q_agms:
        merged['agm'] = q_agms[0]
        if not q_branches: merged['branches'] = ['All']
        if not q_ris: merged['ri'] = 'All'
        if not q_zones: merged['zone'] = 'All'

    return merged


def route_question(question: str):
    """Route any of the natural-language questions to a reusable capability."""
    q = normalize_question(question)

    # --- Extract shared parameters ---
    metric = p.extract_metric(q)
    level = p.extract_level(q)
    type_ = p.extract_type(q)
    year = p.extract_year(q) or 'CY'
    branch_entities = p.extract_known_values(q, _safe_branch_names())
    group_dimension = p.extract_group_dimension(q)

    def bound(fn, **extra_params):
        base_params = {
            'question': question,
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
        return bound(run_top_5_dropout)

    # -----------------------------------------------------------------------
    # 0) Fee Due dedicated routing (must come before generic ranking because
    #    fee column names don't appear in the branch_analytics index at all)
    # -----------------------------------------------------------------------

    _is_fee_q = any(t in q for t in (
        'fee due', 'fee_due', 'ly_fd', 'cy_a_fd', 'cy_fd',
        'fee not paid', 'fee paid', 'books not purchased', 'books not bought', 'did not purchase books', 'did not pay fee',
        'zero paid', 'zero-paid', 'cy_zp', 'zero paid fee', 'zero-paid fee', 'cy_zp_fd', 'zero-paid count', 'zero paid count',
        'due count', 'ly_fdc', 'cy_a_fdc',
        'last year fee', 'last year due', '2024-25 fee', '2025-26 fee',
        'live student fee', 'live student due', 'cy_fp_bn', 'cy_fn_bn', 'books summary',
    ))

    # 0a) Books-not-purchased (CY_FP_BN / CY_FN_BN)
    if _is_fee_q and any(t in q for t in ('books not purchased', 'books not bought', 'did not purchase books', 'books summary')):
        if 'fee paid' in q and 'fee not paid' not in q:
            mode = 'paid_not_bought'
        elif 'fee not paid' in q or 'not paid' in q:
            mode = 'not_paid_not_bought'
        else:
            mode = 'both'
        return bound(run_fee_books_not_purchased, mode=mode, n=p.extract_n(q), group_dim=group_dimension)

    # 0b) Fee YoY comparison (LY_FD vs CY_A_FD)
    if _is_fee_q and p.is_yoy_question(q):
        yoy_dir = p.extract_yoy_direction(q)
        ascending = (yoy_dir == 'negative')   # 'reduced most' = lowest change first
        return bound(run_fee_yoy_comparison, n=p.extract_n(q), ascending=ascending, group_dim=group_dimension)

    # 0c) Fee summary / snapshot / ranking / group-by
    if _is_fee_q:
        sort_col = metric if metric in (
            'CY_A_FD', 'LY_FD', 'CY_A_FDC', 'LY_FDC',
            'CY_ZP', 'CY_ZP_FD', 'CY_A_ZP',
        ) else 'CY_A_FD'
        ascending = p.extract_direction(q) == 'asc'
        return bound(
            run_fee_summary,
            sort_col=sort_col,
            n=p.extract_n(q),
            ascending=ascending,
            branches=branch_entities or None,
            group_dim=group_dimension,
        )

    # -----------------------------------------------------------------------
    # 0.5) Revenue vs Salary dedicated routing
    # -----------------------------------------------------------------------
    _is_rev_sal_q = not _is_fee_q and any(t in q for t in (
        'revenue', 'salary', 'surplus', 'cost per student', 'fee average',
        'salary vs revenue', 'sal vs rev', 'salary ratio', 'salary burden',
        'salary-to-revenue', 'tot_rev_n', 'tot_sal', 'tot_fa', 'tot_cs',
        'tot_sal_v_rev', 'tot_str', 'rev_n', 'sal_v_rev', 'employee cost',
        'salary cost', 'net revenue', 'academic segment', 'lower primary',
        'upper primary', 'pre primary', 'high school', 'ad_ac', 'lps', 'ups',
        'employee count', 'total employee', 'employees', 'total student count',
    ))

    if _is_rev_sal_q:
        # Threshold queries
        thresh = p.extract_threshold(q)
        if thresh is not None or any(t in q for t in ('greater than', 'more than', 'exceeding', 'above', 'below', 'less than', 'under', 'crore', 'lakh')):
            op = thresh[0] if thresh else ('>' if any(t in q for t in ('greater', 'more', 'exceeding', 'above', 'crore', 'lakh')) else '<')
            val = thresh[1] if thresh else 10000000.0
            if thresh is None:
                if 'crore' in q:
                    m_val = re.search(r'(\d+(?:\.\d+)?)\s*crore', q)
                    if m_val:
                        val = float(m_val.group(1)) * 10000000.0
                elif 'lakh' in q:
                    m_val = re.search(r'(\d+(?:\.\d+)?)\s*lakh', q)
                    if m_val:
                        val = float(m_val.group(1)) * 100000.0

            rev_metric = metric if metric in ('REV_N', 'SAL', 'SURPLUS', 'FA', 'CS', 'SAL_V_REV', 'STR', 'NS', 'SC') else 'TOT_REV_N'
            return bound(
                run_revenue_salary_threshold,
                metric=rev_metric,
                op=op,
                value=val,
                group_dim=group_dimension or 'Branch',
            )

        # Segment comparison or specific segment lookup
        if 'compare' in q or any(t in q for t in ('segment', 'segments', 'by segment', 'segment breakdown', 'across segments')) or (p.extract_academic_segment(q) and not p.has_ranking_language(q)):
            return bound(run_revenue_salary_segment_comparison)

        # Explicit Ranking / Group-by / Top-N
        has_ranking = p.has_ranking_language(q) or any(k in q for k in ('top', 'bottom', 'highest', 'lowest', 'worst', 'best', 'most', 'least', 'rank', 'ranked', 'ranking'))
        if group_dimension or has_ranking or 'branch-wise' in q or 'branch wise' in q or 'by branch' in q:
            rev_metric = metric if metric in ('REV_N', 'SAL', 'SURPLUS', 'FA', 'CS', 'SAL_V_REV', 'STR', 'NS', 'SC') else 'TOT_REV_N'
            return bound(
                run_revenue_salary_ranking,
                metric=rev_metric,
                group_dim=group_dimension or 'Branch',
                n=p.extract_n(q, default=5),
                ascending=p.extract_direction(q) == 'asc',
            )

        # Surplus queries
        if 'surplus' in q:
            return bound(
                run_revenue_salary_surplus,
                metric='SURPLUS',
                group_dim=group_dimension,
                n=p.extract_n(q),
                ascending=p.extract_direction(q) == 'asc',
            )

        # Overall / segment summary
        segment = p.extract_academic_segment(q) or 'TOT'
        return bound(run_revenue_salary_summary, segment=segment)


    # 1) Branch / Zone / RI / AGM scorecard / complete summary
    if any(kw in q for kw in _SCORECARD_KEYWORDS) or any(kw in q for kw in ('summary of', 'overview of', 'report of', 'details of', 'summary for', 'overview for')):
        if branch_entities or 'this branch' in q or 'for branch' in q or 'branch scorecard' in q:
            return bound(run_branch_scorecard, branches=branch_entities or None)
        return bound(run_entity_summary)


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

    # 15) Generic top/bottom-N branch ranking by metric or single metric lookup
    if metric:
        if p.has_ranking_language(q) or branch or 'fewest' in q or 'under' in q or 'within' in q or 'in ' in q:
            return bound(
                run_rank_branches_by_metric,
                n=p.extract_n(q),
                ascending=p.extract_direction(q) == 'asc',
            )
        return bound(run_scope_total, metric=metric)

    return None
