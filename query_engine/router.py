from __future__ import annotations

import functools
import re

from . import params as p
from .glossary import AGM_COLUMN, BRANCH_COLUMN, RI_COLUMN, ROOM_METRICS, ZONE_COLUMN
from .orchestrator import (
    get_dataframe,
    run_branch_hierarchy_lookup,
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
    run_ri_analysis,
    run_ri_statistics,
    run_agm_statistics,
    run_branch_statistics,
    run_ri_dropout_statistics,
    run_agm_dropout_statistics,
    run_branch_dropout_statistics,
    run_zone_dropout_statistics,
    run_agm_fee_due_statistics,
    run_ri_fee_due_statistics,
    run_branch_fee_due_statistics,
    run_agm_revenue_salary_statistics,
    run_ri_revenue_salary_statistics,
    run_branch_revenue_salary_statistics,
    run_agm_teacher_student_ratio_statistics,
    run_ri_teacher_student_ratio_statistics,
    run_branch_teacher_student_ratio_statistics,
    run_agm_combined_statistics,
    run_ri_combined_statistics,
    run_branch_combined_statistics,
    run_combined_statistics,
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
    'branch_hierarchy_lookup': run_branch_hierarchy_lookup,
    'group_metric_aggregate': run_group_metric_aggregate,
    'year_over_year_change_ranking': run_year_over_year_change_ranking,
    'staff_count_summary': run_staff_count_summary,
    'room_utilization_snapshot': run_room_utilization_snapshot,
    'sections_and_sps_snapshot': run_sections_and_sps_snapshot,
    'strength_difference_ranking': run_strength_difference_ranking,
    'branch_scorecard': run_branch_scorecard,
    'entity_summary': run_entity_summary,
    'ri_analysis': run_ri_analysis,
    'ri_statistics': run_ri_statistics,
    'agm_statistics': run_agm_statistics,
    'branch_statistics': run_branch_statistics,
    'ri_dropout_statistics': run_ri_dropout_statistics,
    'agm_dropout_statistics': run_agm_dropout_statistics,
    'branch_dropout_statistics': run_branch_dropout_statistics,
    'zone_dropout_statistics': run_zone_dropout_statistics,
    'agm_fee_due_statistics': run_agm_fee_due_statistics,
    'ri_fee_due_statistics': run_ri_fee_due_statistics,
    'branch_fee_due_statistics': run_branch_fee_due_statistics,
    'agm_combined_statistics': run_agm_combined_statistics,
    'ri_combined_statistics': run_ri_combined_statistics,
    'branch_combined_statistics': run_branch_combined_statistics,
    'combined_statistics': run_combined_statistics,
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
    from .multi_stats import normalize_speech_and_wording
    q = re.sub(r'\s+', ' ', question.strip().lower())
    q = normalize_speech_and_wording(q)
    return q


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

    q_low = question.lower()
    is_ri = ('ri ' in q_low or q_low.startswith('ri ')) and not any(k in q_low for k in ('which ri', 'what ri', 'per ri', 'by ri', 'across ri', 'each ri'))
    is_agm = ('agm ' in q_low or q_low.startswith('agm ')) and not any(k in q_low for k in ('which agm', 'what agm', 'per agm', 'by agm', 'across agm', 'each agm'))
    is_branch = ('branch ' in q_low or q_low.startswith('branch ')) and not any(k in q_low for k in ('which branch', 'what branch', 'per branch', 'by branch', 'across branch'))

    q_branches = p.extract_known_values(question, df[BRANCH_COLUMN].dropna().unique(), 'branch') if BRANCH_COLUMN in df.columns else []
    q_zones = p.extract_known_values(question, df[ZONE_COLUMN].dropna().unique(), 'zone') if ZONE_COLUMN in df.columns else []
    q_agms = p.extract_known_values(question, df[AGM_COLUMN].dropna().unique(), 'agm') if AGM_COLUMN in df.columns else []
    q_ris = p.extract_known_values(question, df[RI_COLUMN].dropna().unique(), 'ri') if RI_COLUMN in df.columns else []

    # Filter out false positive branch match if name is explicitly used as a Zone (e.g. "Kompally zone")
    if q_zones and q_branches:
        for z_val in list(q_zones):
            if z_val in q_branches and (f"{z_val.lower()} zone" in q_low or f"zone {z_val.lower()}" in q_low or "zone" in q_low):
                q_branches.remove(z_val)

    is_asking_which_ri = any(k in q_low for k in ('which ri', 'what ri', 'per ri', 'by ri', 'across ri', 'each ri'))
    ri_val = None
    agm_val = q_agms[0] if q_agms else None

    # 1. AGM Extraction
    if not agm_val and is_agm:
        m_agm = re.search(
            r'\bagm\s+([A-Za-z0-9\.\s]+?)(?:\s+(?:which|what|where|how|who|has|have|with|for|in|under|dropout|drop\s*outs?|statistics|stats|fee|due|feedue|revenue|salary|teacher|student|ratio|str|report|review|top|branches)|$)',
            question,
            flags=re.IGNORECASE,
        )
        if m_agm:
            raw_agm = m_agm.group(1).strip()
            agm_val = p.resolve_single_entity(raw_agm, df[AGM_COLUMN].dropna().unique(), 'agm') if AGM_COLUMN in df.columns else raw_agm
            if not agm_val and raw_agm:
                agm_val = raw_agm
    if agm_val:
        merged['agm'] = agm_val
        if not q_branches:
            merged['branches'] = ['All']
        if not q_zones:
            merged['zone'] = 'All'
        if not is_asking_which_ri:
            merged['ri'] = 'All'

    # 2. RI Extraction (ignore RI candidates if query is asking "which RIs", or if candidate is part of AGM name)
    if not is_asking_which_ri:
        valid_q_ris = [r for r in q_ris if not (agm_val and str(r).lower() in str(agm_val).lower())]
        ri_val = valid_q_ris[0] if valid_q_ris else None
        if not ri_val and is_ri:
            m_ri = re.search(
                r'\bri\s+([A-Za-z0-9\.\s]+?)(?:\s+(?:which|what|where|how|who|has|have|with|for|in|under|dropout|drop\s*outs?|statistics|stats|fee|due|feedue|revenue|salary|teacher|student|ratio|str|report|review|top|branches)|$)',
                question,
                flags=re.IGNORECASE,
            )
            if m_ri:
                raw_ri = m_ri.group(1).strip()
                ri_val = p.resolve_single_entity(raw_ri, df[RI_COLUMN].dropna().unique(), 'ri') if RI_COLUMN in df.columns else raw_ri
                if not ri_val and raw_ri:
                    ri_val = raw_ri
    if ri_val:
        merged['ri'] = ri_val
        if not q_branches:
            merged['branches'] = ['All']
        if not q_zones:
            merged['zone'] = 'All'

    # 3. Branch Extraction
    is_asking_which_branch = any(k in q_low for k in ('which branch', 'what branch', 'per branch', 'by branch', 'across branch'))
    if q_branches and not is_asking_which_branch:
        merged['branches'] = q_branches
    elif is_branch and not is_asking_which_branch:
        m_br = re.search(
            r'\bbranch\s+([A-Za-z0-9\.\s]+?)(?:\s+(?:which|what|where|how|who|has|have|with|for|in|under|belong|belongs|dropout|drop\s*outs?|statistics|stats|fee|due|feedue|revenue|salary|teacher|student|ratio|str|report|review)|$)',
            question,
            flags=re.IGNORECASE,
        )
        if m_br:
            raw_br = m_br.group(1).strip()
            br_val = p.resolve_single_entity(raw_br, df[BRANCH_COLUMN].dropna().unique(), 'branch') if BRANCH_COLUMN in df.columns else raw_br
            if br_val:
                merged['branches'] = [br_val]

    # 4. Zone Extraction
    if q_zones:
        merged['zone'] = q_zones[0]
        if not q_branches:
            merged['branches'] = ['All']

    return merged


def route_question(question: str):
    """Route any of the natural-language questions to a reusable capability."""
    q = normalize_question(question)

    # --- Extract shared parameters ---
    metric = p.extract_metric(q)
    level = p.extract_level(q)
    type_ = p.extract_type(q)
    raw_year = p.extract_year(q)
    year = raw_year or 'CY'
    branch_entities = p.extract_known_values(q, _safe_branch_names())
    group_dimension = p.extract_group_dimension(q)

    def bound(fn, **extra_params):
        base_params = {
            'question': question,
            'metric': metric,
            'level': level,
            'type': type_,
            'year': year,
            'raw_year': raw_year,
            'group_dimension': group_dimension,
        }
        base_params.update(extra_params)

        def handler(context):
            return fn(base_params, _merge_text_entities(question, context))

        return handler

    # --- Original V1 intent: exact match back-compatibility ---
    dropout = any(term in q for term in ('dropout', 'drop out', 'drop-out', 'dropouts', 'dpp'))
    top_five = any(term in q for term in ('top 5', 'top five', 'highest 5', 'top branches')) and not any(term in q for term in ('bottom', 'lowest', 'least', 'worst', 'smallest', 'fewest'))
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
    # Branch Hierarchy Lookup (e.g. "Branch Miyapur which RI does it belong to?")
    # -----------------------------------------------------------------------
    is_hierarchy_q = any(t in q for t in ('belong to', 'belongs to', 'which ri does', 'which agm does', 'which zone does', 'under which ri does', 'under which agm does', 'under which zone does')) or (
        ('branch ' in q or branch_entities) and any(t in q for t in ('which ri', 'which agm', 'which zone')) and not any(t in q for t in ('which branch', 'which branches', 'dropout', 'dropouts', 'fee', 'salary', 'revenue', 'strength', 'ratio'))
    )
    if is_hierarchy_q:
        return bound(run_branch_hierarchy_lookup, branches=branch_entities)

    # -----------------------------------------------------------------------
    # Multi-Statistics Dedicated Routing (2 or more distinct statistics requested)
    # -----------------------------------------------------------------------
    from .multi_stats import extract_requested_statistics
    requested_stats = extract_requested_statistics(q)
    if len(requested_stats) >= 2:
        return bound(run_combined_statistics, statistics=requested_stats)

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

    # 0b-2) Fee Due Statistics Review for AGM, RI, Branch ("AGM Suresh Fee Due Statistics", "RI Ramana Fee Due Statistics", "KAKINADA 1 Fee Due Statistics")
    if _is_fee_q and any(t in q for t in ('statistics', 'statistic', 'stats', 'report', 'review', 'analysis', 'complete summary', 'fee due statistics')):
        try:
            from .query_planner import get_prepared_dataframe
            df_fee = get_prepared_dataframe(['CY_A_FD'], primary_dataset_id='fee_analysis')
            q_branches_found = p.extract_known_values(question, df_fee['Branch'].dropna().unique(), 'branch') if 'Branch' in df_fee.columns else []
            q_agms_found = p.extract_known_values(question, df_fee['AGM Name'].dropna().unique(), 'agm') if 'AGM Name' in df_fee.columns else []
            q_ris_found = p.extract_known_values(question, df_fee['RI Name'].dropna().unique(), 'ri') if 'RI Name' in df_fee.columns else []

            if not (q_branches_found or q_agms_found or q_ris_found):
                df_all = get_dataframe()
                branch_col = 'Branch' if 'Branch' in df_all.columns else None
                agm_col = 'AGM Name' if 'AGM Name' in df_all.columns else ('AGM' if 'AGM' in df_all.columns else None)
                ri_col = 'RI Name' if 'RI Name' in df_all.columns else ('RI' if 'RI' in df_all.columns else None)
                q_branches_found = p.extract_known_values(question, df_all[branch_col].dropna().unique(), 'branch') if branch_col else []
                q_agms_found = p.extract_known_values(question, df_all[agm_col].dropna().unique(), 'agm') if agm_col else []
                q_ris_found = p.extract_known_values(question, df_all[ri_col].dropna().unique(), 'ri') if ri_col else []

            is_ri_explicit = 'ri ' in q or q.startswith('ri ') or 'ri fee' in q or 'ri statistics' in q
            is_agm_explicit = 'agm ' in q or q.startswith('agm ') or 'agm fee' in q or 'agm statistics' in q

            if is_ri_explicit:
                if q_ris_found: return bound(run_ri_fee_due_statistics, ri=q_ris_found[0])
                return bound(run_ri_fee_due_statistics)
            if is_agm_explicit:
                if q_agms_found: return bound(run_agm_fee_due_statistics, agm=q_agms_found[0])
                return bound(run_agm_fee_due_statistics)

            if q_branches_found:
                return bound(run_branch_fee_due_statistics, branch=q_branches_found[0])
            if q_ris_found:
                return bound(run_ri_fee_due_statistics, ri=q_ris_found[0])
            if q_agms_found:
                return bound(run_agm_fee_due_statistics, agm=q_agms_found[0])

            return bound(run_branch_fee_due_statistics)
        except Exception:
            pass

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
        # Dedicated Revenue vs Salary Statistics Review (AGM, RI, Branch)
        if any(t in q for t in ('statistics', 'statistic', 'stats', 'report', 'review', 'analysis', 'overview', 'details', 'summary')) or q in ('revenue statistics', 'salary statistics', 'revenue vs salary statistics'):
            try:
                from .query_planner import get_prepared_dataframe
                df_rev_sal = get_prepared_dataframe(['TOT_REV_N'], primary_dataset_id='revenue_vs_salary')
                q_branches_found = p.extract_known_values(question, df_rev_sal['Branch'].dropna().unique(), 'branch') if 'Branch' in df_rev_sal.columns else []
                q_agms_found = p.extract_known_values(question, df_rev_sal['AGM Name'].dropna().unique(), 'agm') if 'AGM Name' in df_rev_sal.columns else []
                q_ris_found = p.extract_known_values(question, df_rev_sal['RI Name'].dropna().unique(), 'ri') if 'RI Name' in df_rev_sal.columns else []

                is_ri_explicit = 'ri ' in q or q.startswith('ri ') or 'ri revenue' in q or 'ri salary' in q
                is_agm_explicit = 'agm ' in q or q.startswith('agm ') or 'agm revenue' in q or 'agm salary' in q

                if is_ri_explicit:
                    if q_ris_found: return bound(run_ri_revenue_salary_statistics, ri=q_ris_found[0])
                    return bound(run_ri_revenue_salary_statistics)
                if is_agm_explicit:
                    if q_agms_found: return bound(run_agm_revenue_salary_statistics, agm=q_agms_found[0])
                    return bound(run_agm_revenue_salary_statistics)

                if q_branches_found:
                    return bound(run_branch_revenue_salary_statistics, branch=q_branches_found[0])
                if q_ris_found:
                    return bound(run_ri_revenue_salary_statistics, ri=q_ris_found[0])
                if q_agms_found:
                    return bound(run_agm_revenue_salary_statistics, agm=q_agms_found[0])

                if any(t in q for t in ('statistics', 'statistic', 'stats')):
                    return bound(run_agm_revenue_salary_statistics)
            except Exception:
                pass
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


    # 0) Fee Due Statistics Queries ("AGM Suresh Fee Due Statistics", "RI Ramana Fee Due Statistics", "KAKINADA 1 Fee Due Statistics", etc.)
    if any(kw in q for kw in ('fee due', 'fee_due', 'zero paid', 'zero-paid', 'books not purchased')) and any(kw in q for kw in ('statistics', 'statistic', 'stats', 'report', 'review', 'summary', 'overview', 'fee due', 'fee_due', 'details')):
        try:
            from .query_planner import get_prepared_dataframe
            df_fee = get_prepared_dataframe(['CY_A_FD'], primary_dataset_id='fee_analysis')
            q_branches_found = p.extract_known_values(question, df_fee['Branch'].dropna().unique(), 'branch') if 'Branch' in df_fee.columns else []
            q_agms_found = p.extract_known_values(question, df_fee['AGM Name'].dropna().unique(), 'agm') if 'AGM Name' in df_fee.columns else []
            q_ris_found = p.extract_known_values(question, df_fee['RI Name'].dropna().unique(), 'ri') if 'RI Name' in df_fee.columns else []

            if q_branches_found:
                return bound(run_branch_fee_due_statistics, branch=q_branches_found[0])
            if q_ris_found:
                return bound(run_ri_fee_due_statistics, ri=q_ris_found[0])
            if q_agms_found:
                return bound(run_agm_fee_due_statistics, agm=q_agms_found[0])
        except Exception:
            pass

    # 0.75) Teacher Student Ratio Statistics Queries ("AGM Ramana teacher student ratio statistics", "teacher student ratio statistics", "staff ratio statistics", etc.)
    _is_str_stats_q = (
        any(kw in q for kw in (
            'teacher student ratio', 'student teacher ratio', 'student-teacher ratio', 'teacher-student ratio',
            'staff ratio', 'teacher student statistics', 'student teacher statistics',
            'staff ratio statistics', 'teacher ratio statistics', 'staffing statistics', 'str statistics', 'teacher student',
            'student teacher',
        ))
        and any(kw in q for kw in ('statistics', 'statistic', 'stats', 'report', 'review', 'analysis', 'overview'))
        and not (p.has_ranking_language(q) or p.extract_threshold(q) or p.is_level_comparison(q) or p.is_yoy_question(q) or any(kw in q for kw in ('by ri', 'by agm', 'by zone', 'by branch', 'ri wise', 'agm wise', 'zone wise', 'branch wise', 'ri-wise', 'agm-wise', 'zone-wise', 'branch-wise')))
    )

    if _is_str_stats_q:
        try:
            df_curr = get_dataframe()
            q_branches_found = p.extract_known_values(question, df_curr[BRANCH_COLUMN].dropna().unique(), 'branch') if BRANCH_COLUMN in df_curr.columns else []
            q_agms_found = p.extract_known_values(question, df_curr[AGM_COLUMN].dropna().unique(), 'agm') if AGM_COLUMN in df_curr.columns else []
            q_ris_found = p.extract_known_values(question, df_curr[RI_COLUMN].dropna().unique(), 'ri') if RI_COLUMN in df_curr.columns else []

            is_ri_explicit = 'ri ' in q or q.startswith('ri ') or 'ri staff' in q or 'ri teacher' in q
            is_agm_explicit = 'agm ' in q or q.startswith('agm ') or 'agm staff' in q or 'agm teacher' in q

            if is_ri_explicit:
                if q_ris_found: return bound(run_ri_teacher_student_ratio_statistics, ri=q_ris_found[0])
                return bound(run_ri_teacher_student_ratio_statistics)
            if is_agm_explicit:
                if q_agms_found: return bound(run_agm_teacher_student_ratio_statistics, agm=q_agms_found[0])
                return bound(run_agm_teacher_student_ratio_statistics)

            if q_branches_found:
                return bound(run_branch_teacher_student_ratio_statistics, branch=q_branches_found[0])
            if q_ris_found:
                return bound(run_ri_teacher_student_ratio_statistics, ri=q_ris_found[0])
            if q_agms_found:
                return bound(run_agm_teacher_student_ratio_statistics, agm=q_agms_found[0])

            return bound(run_agm_teacher_student_ratio_statistics)
        except Exception:
            pass

    # 1) Executive Analysis / Review / Dropout Statistics Queries ("Analyze RI Ramana", "RI Ramana Dropouts statistics", "KAKINADA 1 statistics", "AGM Suresh Dropouts statistics", etc.)
    if any(kw in q for kw in ('analyze', 'analysis', 'review', 'performance review', 'complete review', 'executive summary', 'statistics', 'statistic', 'stats')) or (any(d in q for d in ('dropout', 'dropouts', 'drop out', 'dpp')) and any(s in q for s in ('statistics', 'statistic', 'stats', 'report', 'review', 'summary'))):
        try:
            df_curr = get_dataframe()
            q_branches_found = p.extract_known_values(question, df_curr[BRANCH_COLUMN].dropna().unique(), 'branch') if BRANCH_COLUMN in df_curr.columns else []
            q_agms_found = p.extract_known_values(question, df_curr[AGM_COLUMN].dropna().unique(), 'agm') if AGM_COLUMN in df_curr.columns else []
            q_ris_found = p.extract_known_values(question, df_curr[RI_COLUMN].dropna().unique(), 'ri') if RI_COLUMN in df_curr.columns else []
            q_zones_found = p.extract_known_values(question, df_curr[ZONE_COLUMN].dropna().unique(), 'zone') if ZONE_COLUMN in df_curr.columns else []

            is_ri_explicit = 'ri ' in q or q.startswith('ri ') or 'ri statistics' in q or 'ri dropout' in q or 'ri dropouts' in q
            is_agm_explicit = 'agm ' in q or q.startswith('agm ') or 'agm statistics' in q or 'agm dropout' in q or 'agm dropouts' in q
            is_zone_explicit = 'zone ' in q or q.startswith('zone ') or 'zone statistics' in q or 'zone dropout' in q or 'zone dropouts' in q
            is_dropout_explicit = any(d in q for d in ('dropout', 'dropouts', 'drop out', 'dpp'))

            if is_ri_explicit:
                if is_dropout_explicit:
                    if q_ris_found: return bound(run_ri_dropout_statistics, ri=q_ris_found[0])
                    return bound(run_ri_dropout_statistics)
                if q_ris_found: return bound(run_ri_statistics, ri=q_ris_found[0])
                return bound(run_ri_statistics)

            if is_agm_explicit:
                if is_dropout_explicit:
                    if q_agms_found: return bound(run_agm_dropout_statistics, agm=q_agms_found[0])
                    return bound(run_agm_dropout_statistics)
                if q_agms_found: return bound(run_agm_statistics, agm=q_agms_found[0])
                return bound(run_agm_statistics)

            if is_zone_explicit:
                if q_zones_found: return bound(run_zone_dropout_statistics, zone=q_zones_found[0])
                return bound(run_zone_dropout_statistics)

            if q_branches_found:
                if is_dropout_explicit:
                    return bound(run_branch_dropout_statistics, branch=q_branches_found[0])
                return bound(run_branch_statistics, branch=q_branches_found[0])

            if q_ris_found:
                if is_dropout_explicit:
                    return bound(run_ri_dropout_statistics, ri=q_ris_found[0])
                return bound(run_ri_statistics, ri=q_ris_found[0])

            if q_agms_found:
                if is_dropout_explicit:
                    return bound(run_agm_dropout_statistics, agm=q_agms_found[0])
                return bound(run_agm_statistics, agm=q_agms_found[0])
            if q_zones_found:
                return bound(run_zone_dropout_statistics, zone=q_zones_found[0])

            def _entity_not_found_handler(context):
                clean_target = re.sub(r'\b(statistics|statistic|stats|branch|branches|ri|ris|agm|agms|zone|zones|dropout|dropouts|drop|out|show|give|analyze|analysis|review)\b', '', question, flags=re.IGNORECASE).strip()
                target_label = clean_target.strip(' .-_,') if clean_target else 'requested entity'
                return {
                    'function': 'entity_not_found',
                    'answer': f"I couldn't find a matching zone, branch, RI, or AGM for '{target_label}'. Please check the name and try again.",
                    'data': [],
                }
            return _entity_not_found_handler
        except Exception:
            pass
        if branch_entities or 'this branch' in q or 'for branch' in q or 'branch scorecard' in q:
            return bound(run_branch_scorecard, branches=branch_entities or None)
        return bound(run_entity_summary)

    # 1b) Branch / Zone / RI / AGM scorecard / complete summary
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
        is_ranking = p.has_ranking_language(q) or any(k in q for k in ('highest', 'lowest', 'top', 'bottom', 'which'))
        explicit_n = p.extract_explicit_n(q)
        if is_ranking and explicit_n is None and any(term in q for term in ('top ris', 'top agms', 'top zones', 'top five')):
            explicit_n = 5
        n_val = explicit_n if is_ranking else None
        asc = p.extract_direction(q) == 'asc'
        return bound(
            run_group_metric_aggregate,
            group_dimension=group_dimension,
            agg=agg,
            n=n_val,
            ascending=asc,
        )

    # 14) Single / multi branch metric lookup (Q33-Q42, Q64, Q65)
    if (branch_entities or 'branch-wise' in q or 'branch wise' in q) and metric and not p.has_ranking_language(q) and not any(k in q for k in ('highest', 'lowest', 'worst', 'best', 'top', 'bottom', 'rank', 'which')):
        return bound(run_branch_metric_lookup, metrics=[metric], branches=branch_entities or None)

    # 15) Generic top/bottom-N branch ranking by metric or single metric lookup
    if metric:
        if p.has_ranking_language(q) or branch or 'fewest' in q or 'under' in q or 'within' in q or 'in ' in q or 'which branches' in q or 'which branch' in q:
            explicit_n = p.extract_explicit_n(q)
            if explicit_n is None and any(term in q for term in ('top branches', 'top five branches', 'top 5', 'top five')):
                explicit_n = 5
            return bound(
                run_rank_branches_by_metric,
                n=explicit_n,
                ascending=p.extract_direction(q) == 'asc',
            )
        return bound(run_scope_total, metric=metric)

    return None
