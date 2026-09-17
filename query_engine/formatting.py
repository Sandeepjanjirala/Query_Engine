from .analysis_engine import (
    AnalysisResult,
    build_group_analysis,
    build_lookup_analysis,
    build_ranking_analysis,
    build_ri_analysis,
)
from .glossary import ABBREVIATIONS
from .metric_registry import get_default_metric_registry

_EXTRA_LABELS = {
    'Avg-SPS': 'Average Students Per Section',
    'occupancy_rate': 'Room Occupancy Percentage',
    'vacancy_rate': 'Room Vacancy Percentage',
}


def _metric_label(metric: str) -> str:
    from .analysis_engine import get_clean_metric_label
    return get_clean_metric_label(metric)


def render_operation_response(analysis: AnalysisResult) -> str:
    lines = []

    if analysis.operation == 'analysis':
        if analysis.direct_answer:
            lines.append(analysis.direct_answer)
            lines.append("")

        for sec in analysis.sections:
            lines.append(f"### {sec['title']}")
            lines.append(sec['content'])
            lines.append("")

        if analysis.headers:
            evidence_heading = getattr(analysis, 'evidence_title', None) or "Detailed Branch Data"
            lines.append(f"### {evidence_heading}")
            lines.append("")
            hdr_line = "| " + " | ".join(analysis.headers) + " |"
            sep_line = "| " + " | ".join(["---"] * len(analysis.headers)) + " |"
            lines.append(hdr_line)
            lines.append(sep_line)
            for row in analysis.rows:
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")

        return "\n".join(lines).strip()

    if analysis.operation == 'lookup':
        return analysis.direct_answer

    # For ranking, group_by, threshold, yoy operations
    if analysis.direct_answer:
        lines.append(analysis.direct_answer)
        lines.append("")

    if analysis.headers and analysis.rows:
        lines.append("### Detailed Evidence")
        lines.append("")
        hdr_line = "| " + " | ".join(analysis.headers) + " |"
        sep_line = "| " + " | ".join(["---"] * len(analysis.headers)) + " |"
        lines.append(hdr_line)
        lines.append(sep_line)
        for row in analysis.rows:
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    return "\n".join(lines).strip()


def render_5_layer_response(analysis: AnalysisResult) -> str:
    return render_operation_response(analysis)


def format_top_5_dropout(results: list[dict], context: dict | None = None, is_fallback: bool = False) -> str:
    if not results:
        return 'No branch dropout data is available.'
    analysis = build_ranking_analysis(results, metric='CY-DPP', ascending=False, group_dimension='Branch', context=context, is_fallback=is_fallback)
    return render_operation_response(analysis)


def format_ranked_branches(results: list[dict], metric: str, ascending: bool, context: dict | None = None, is_fallback: bool = False) -> str:
    if not results:
        return f'No data is available for {_metric_label(metric)} with the current filters.'
    analysis = build_ranking_analysis(results, metric=metric, ascending=ascending, group_dimension='Branch', context=context, is_fallback=is_fallback)
    return render_operation_response(analysis)


def format_group_aggregate(results: list[dict], metric: str, group_dimension: str, agg: str, context: dict | None = None, is_fallback: bool = False, year: str | None = None) -> str:
    dim_hdr = group_dimension.upper() if group_dimension.lower() in ('ri', 'agm') else group_dimension.title()
    if not results:
        return f'No data is available to aggregate {_metric_label(metric)} by {dim_hdr}.'
    analysis = build_group_analysis(results, metric=metric, group_dimension=group_dimension, context=context, is_fallback=is_fallback, year=year)
    return render_operation_response(analysis)


def format_year_over_year(
    results: list[dict],
    metric: str = 'NS',
    context: dict | None = None,
    ascending: bool = False,
    direction: str | None = None,
) -> str:
    spec = get_default_metric_registry().get(metric)
    lbl = spec.display_name if spec else _metric_label(metric)
    if not results:
        if direction == 'negative':
            return f"No entities showed an improvement in {lbl}."
        return f'No year-over-year data is available for {lbl}.'
    analysis = build_ranking_analysis(
        results,
        metric=metric,
        ascending=ascending,
        group_dimension='Branch',
        operation='yoy',
        context=context,
        direction=direction,
    )
    return render_operation_response(analysis)


def format_branch_lookup(results: list[dict], columns: list[str]) -> str:
    if not results:
        return 'No matching branch data found for the current filters.'
    analysis = build_lookup_analysis(results, columns=columns)
    return render_operation_response(analysis)


def format_staff_summary(results: list[dict], columns: list[str]) -> str:
    if not results:
        return 'No staff data is available for the current filters.'
    lines = ['Staff count summary:']
    for entry in results:
        parts = [f"{_metric_label(col)}: {entry.get(col)}" for col in columns]
        lines.append(f"{entry['branch']} — " + ', '.join(parts))
    return '\n'.join(lines)


def format_room_snapshot(results: list[dict], columns: list[str]) -> str:
    if not results:
        return 'No room utilization data is available for the current filters.'
    lines = ['Room utilization snapshot:']
    for entry in results:
        parts = [f"{_metric_label(col)}: {entry.get(col)}" for col in columns]
        lines.append(f"{entry['branch']} — " + ', '.join(parts))
    return '\n'.join(lines)


def format_sections_sps_snapshot(results: list[dict], columns: list[str]) -> str:
    if not results:
        return 'No sections/students-per-section data is available for the current filters.'
    lines = ['Sections & students-per-section snapshot:']
    for entry in results:
        parts = [f"{_metric_label(col)}: {entry.get(col)}" for col in columns]
        lines.append(f"{entry['branch']} — " + ', '.join(parts))
    return '\n'.join(lines)


def format_strength_difference(results: list[dict], metric: str) -> str:
    if not results:
        return f'No data is available for {_metric_label(metric)}.'
    lines = [f'Branches ranked by {_metric_label(metric)}:']
    for item in results:
        lines.append(f"{item['rank']}. {item['branch']} — {item['value']:.2f}")
    return '\n'.join(lines)


def format_branch_scorecard(entry: dict | None, branch: str) -> str:
    if not entry:
        return f'No data is available for branch "{branch}" with the current filters.'
    lines = [f"Scorecard for {entry['branch']}:"]
    for key, value in entry.items():
        if key == 'branch':
            continue
        lines.append(f"{_metric_label(key)}: {value}")
    return '\n'.join(lines)


def format_threshold_result(res: dict, metric: str) -> str:
    count = res['count']
    op_symbol = {'>': 'above', 'gt': 'above', '>=': 'at least', 'gte': 'at least',
                 '<': 'below', 'lt': 'below', '<=': 'at most', 'lte': 'at most'}.get(res['op'], res['op'])
    target_entity = f"{res['group_column'].upper()}s" if res.get('group_column') else 'branches'

    if res.get('count_only'):
        return f"{count} {target_entity} have {_metric_label(metric)} {op_symbol} {res['threshold']}."

    if count == 0:
        return f"No {target_entity} found with {_metric_label(metric)} {op_symbol} {res['threshold']}."

    spec = get_default_metric_registry().get(metric)
    unit = '%' if (spec and spec.data_type == 'percentage') or 'dpp' in metric.lower() or 'pct' in metric.lower() else ''
    diff_unit = ' pp' if unit == '%' else ''
    g_col = res.get('group_column') or 'Branch'
    entity_hdr = g_col.upper() if g_col.lower() in ('ri', 'agm') else g_col.title()

    if res['records'] and 'current_year' in res['records'][0]:
        lines = [
            f"{count} {target_entity} with {_metric_label(metric)} {op_symbol} {res['threshold']}:",
            "",
            f'| Rank | {entity_hdr} | Current Year | Last Year | Difference |',
            '| --- | --- | --- | --- | --- |'
        ]
        for idx, item in enumerate(res['records'], start=1):
            name = item.get('group') or item.get('branch')
            cy = item.get('current_year') if item.get('current_year') is not None else item.get('value')
            ly = item.get('previous_year')
            diff = item.get('difference')
            if diff is None and cy is not None and ly is not None:
                diff = cy - ly

            cy_str = f"{cy:.2f}{unit}" if cy is not None else "N/A"
            ly_str = f"{ly:.2f}{unit}" if ly is not None else "N/A"
            if diff is not None:
                sign = '+' if diff >= 0 else ''
                diff_str = f"{sign}{diff:.2f}{diff_unit}"
            else:
                diff_str = "N/A"
            lines.append(f"| {idx} | {name} | {cy_str} | {ly_str} | {diff_str} |")
        return '\n'.join(lines)

    lines = [f"{count} {target_entity} with {_metric_label(metric)} {op_symbol} {res['threshold']}:"]
    for item in res['records']:
        name = item.get('group') or item.get('branch')
        lines.append(f"- {name} — {item['value']:.2f}")
    return '\n'.join(lines)


def format_dimension_comparison(res: dict, metric: str, dimension_type: str) -> str:
    spec = get_default_metric_registry().get(metric)
    unit = ' pp' if (spec and spec.data_type == 'percentage') or 'dpp' in metric.lower() or 'pct' in metric.lower() else ''
    val_unit = '%' if (spec and spec.data_type == 'percentage') or 'dpp' in metric.lower() or 'pct' in metric.lower() else ''

    if res.get('comparison_type') == 'yoy_breakdown':
        top_type = res.get('top_type', 'improved')
        winner_label = 'Improved most' if top_type in ('improved', 'highest_improvement') else 'Declined most'

        lines = [
            f"{_metric_label(metric)} CY vs LY by {dimension_type}:",
            "",
            '| Category | Current Year | Last Year | Difference |',
            '| --- | --- | --- | --- |'
        ]
        for item in res['data']:
            diff = item.get('difference', item.get('change', 0))
            ly = item.get('previous_year', item.get('last_year', 0))
            sign = '+' if diff >= 0 else ''
            lines.append(
                f"| {item['category']} | {item['current_year']:.2f}{val_unit} | {ly:.2f}{val_unit} | {sign}{diff:.2f}{unit} |"
            )
        if res.get('winner'):
            w = res['winner']
            diff = w.get('difference', w.get('change', 0))
            sign = '+' if diff >= 0 else ''
            lines.append(f"\n**{winner_label}**: {w['category']} ({sign}{diff:.2f}{unit})")
        return '\n'.join(lines)

    if res.get('comparison_type') == 'grouped':
        lines = [f"{_metric_label(metric)} comparison by {res['group_column']}:"]
        for row in res['data']:
            parts = [f"{k}: {v}" for k, v in row.items() if k != 'group']
            lines.append(f"{row['group']} — " + ', '.join(parts))
        return '\n'.join(lines)

    lines = [
        f"{_metric_label(metric)} comparison across {dimension_type}:",
        "",
        '| Category | Current Year | Last Year | Difference |',
        '| --- | --- | --- | --- |'
    ]
    for item in res['data']:
        diff = item.get('difference', item.get('change'))
        ly = item.get('previous_year', item.get('last_year'))
        cy = item.get('current_year', item.get('value', 0))
        cy_str = f"{cy:.2f}{val_unit}" if cy is not None else "N/A"
        ly_str = f"{ly:.2f}{val_unit}" if ly is not None else "N/A"
        if diff is not None:
            sign = '+' if diff >= 0 else ''
            diff_str = f"{sign}{diff:.2f}{unit}"
        else:
            diff_str = "N/A"
        lines.append(f"| {item['category']} | {cy_str} | {ly_str} | {diff_str} |")

    if res.get('winner'):
        w = res['winner']
        top_kind = res.get('top_kind', 'highest')
        label = 'Highest category' if top_kind == 'highest' else 'Lowest category'
        cy_w = w.get('current_year', w.get('value', 0))
        lines.append(f"\n**{label}**: {w['category']} ({cy_w:.2f}{val_unit})")
    return '\n'.join(lines)


def format_entity_summary(res: dict) -> str:
    entity = res.get('entity_name', 'Entity')
    records = res.get('records', [])
    if not records:
        return f"No summary data available for {entity}."

    lines = [f"Summary Report for {entity}:"]
    for item in records:
        val = item['value']
        dtype = item.get('data_type')

        if dtype == 'currency':
            val_str = f"₹{val:,.2f}"
        elif dtype == 'percentage':
            val_str = f"{val:.2f}%"
        else:
            val_str = f"{val:.2f}"

        lines.append(f"- {item['display_name']}: {val_str}")
    return '\n'.join(lines)


def format_room_ratio(results: list[dict], ratio_type: str, ascending: bool | None) -> str:
    if not results:
        return f'No {ratio_type} data available for branches.'
    heading = 'Room Occupancy Percentage' if ratio_type == 'occupancy' else 'Room Vacancy Percentage'
    lines = [f'Branches ranked by {heading}:']
    for item in results:
        lines.append(f"{item['rank']}. {item['branch']} — {item['percentage']:.2f}% (Occupied: {item['noor']}, Vacant: {item['novr']}, Total: {item['nocr']})")
    return '\n'.join(lines)


def format_scope_total(val: float, metric: str, level: str | None = None, type_: str | None = None) -> str:
    spec = get_default_metric_registry().get(metric)
    unit = '%' if (spec and spec.data_type == 'percentage') or 'dpp' in metric.lower() or 'pct' in metric.lower() else ''
    if spec and spec.data_type == 'currency':
        val_str = f"₹{val:,.2f}"
    else:
        val_str = f"{val:.2f}{unit}"
    label = _metric_label(metric)
    prefix_tags = []
    if level:
        prefix_tags.append(level)
    if type_:
        prefix_tags.append('Existing' if type_ == 'E' else ('New' if type_ == 'N' else type_))
    tag_str = f" {' '.join(prefix_tags)}" if prefix_tags else ""
    prefix = 'Average' if unit == '%' else ('Total' if spec and spec.data_type in ('count', 'currency') else 'Overall')
    return f"{prefix}{tag_str} {label} in current scope: {val_str}"


# ---------------------------------------------------------------------------
# Fee Due formatters
# ---------------------------------------------------------------------------

_FEE_COL_LABELS = {
    'CY_A_FD':  '2025-26 Fee Due',
    'LY_FD':    '2024-25 Fee Due',
    'CY_A_FDC': '2025-26 Due Count',
    'LY_FDC':   '2024-25 Due Count',
    'CY_ZP':    'Zero Paid Count',
    'CY_ZP_FD': 'Zero Paid Fee Due Amt',
    'CY_FP_BN': 'Fee Paid, Books Not Purchased',
    'CY_FN_BN': 'Fee Not Paid & Books Not Purchased',
}


def _fee_label(col: str) -> str:
    return _FEE_COL_LABELS.get(col) or _metric_label(col)


def _fmt_currency(val: float) -> str:
    """Format a rupee amount: ₹1,23,456 style."""
    try:
        v = int(round(val))
        # Indian-style grouping: last 3 digits, then groups of 2
        s = str(v)
        if len(s) <= 3:
            return f"\u20b9{s}"
        rest, last3 = s[:-3], s[-3:]
        parts = []
        while rest:
            parts.append(rest[-2:])
            rest = rest[:-2]
        return f"\u20b9{','.join(reversed(parts))},{last3}"
    except Exception:
        return f"\u20b9{val:.2f}"


def format_fee_summary(
    results: list[dict],
    columns: list[str],
    n: int | None = None,
    ascending: bool = False,
    group_col: str | None = None,
    target_metric: str | None = None,
) -> str:
    if not results:
        return "No fee due data is available for the current filters."

    # Identify entity key (branch, zone, ri, agm, s_type)
    sample = results[0]
    entity_key = 'branch'
    entity_title = 'Branches'
    for k, title in (('zone', 'Zones'), ('ri', 'RIs'), ('agm', 'AGMs'), ('s_type', 'Branch Types'), ('branch', 'Branches')):
        if k in sample:
            entity_key = k
            entity_title = title
            break

    heading = 'lowest' if ascending else 'highest'
    sort_col = columns[0] if columns else 'CY_A_FD'
    sort_label = _fee_label(target_metric or sort_col)
    limit_note = f" (top {n})" if n else ""
    lines = [f"{entity_title} by {sort_label} ({heading} first){limit_note}:"]

    for item in results:
        parts = []
        entity_val = item.get(entity_key, item.get('branch', ''))
        cols_to_show = [target_metric] if target_metric and target_metric in item else [c for c in columns if c in item]
        if not cols_to_show:
            cols_to_show = [c for c in item.keys() if c not in ('rank', 'branch', 'zone', 'ri', 'agm', 's_type')]
        for col in cols_to_show:
            val = item[col]
            if 'FD' in str(col) and 'FDC' not in str(col):
                parts.append(f"{_fee_label(col)}: {_fmt_currency(val)}")
            else:
                parts.append(f"{_fee_label(col)}: {int(val):,}")
        rank_str = f"{item['rank']}. " if 'rank' in item else ""
        lines.append(f"{rank_str}{entity_val} — " + ", ".join(parts))
    return "\n".join(lines)


def format_fee_books(
    results: list[dict],
    mode: str = 'both',
    group_col: str | None = None,
    target_metric: str | None = None,
) -> str:
    if not results:
        labels = {
            'paid_not_bought':     'fee paid but books not purchased',
            'not_paid_not_bought': 'fee not paid and books not purchased',
        }
        return f"No records found with {labels.get(mode, 'books not purchased issue')} in the current filters."

    sample = results[0]
    entity_key = 'branch'
    entity_title = 'Branches'
    for k, title in (('zone', 'Zones'), ('ri', 'RIs'), ('agm', 'AGMs'), ('s_type', 'Branch Types'), ('branch', 'Branches')):
        if k in sample:
            entity_key = k
            entity_title = title
            break

    mode_labels = {
        'paid_not_bought':     'Fee Paid but Books Not Purchased',
        'not_paid_not_bought': 'Fee Not Paid & Books Not Purchased',
        'both':                'Books Not Purchased Issue (either condition)',
    }
    lines = [f"{entity_title} with {mode_labels.get(mode, 'books not purchased issue')}:"]
    for item in results:
        parts = []
        entity_val = item.get(entity_key, item.get('branch', ''))
        if target_metric == 'CY_FP_BN' and 'CY_FP_BN' in item:
            parts.append(f"Fee Paid-Books Not Purchased: {item['CY_FP_BN']:,}")
        elif target_metric == 'CY_FN_BN' and 'CY_FN_BN' in item:
            parts.append(f"Fee Not Paid-Books Not Purchased: {item['CY_FN_BN']:,}")
        else:
            if 'CY_FP_BN' in item:
                parts.append(f"Fee Paid-Books Not Purchased: {item['CY_FP_BN']:,}")
            if 'CY_FN_BN' in item:
                parts.append(f"Fee Not Paid-Books Not Purchased: {item['CY_FN_BN']:,}")
        rank_str = f"{item['rank']}. " if 'rank' in item else ""
        lines.append(f"{rank_str}{entity_val} — " + ", ".join(parts))
    return "\n".join(lines)


def format_fee_yoy(
    results: list[dict],
    ascending: bool = False,
    group_col: str | None = None,
) -> str:
    if not results:
        return "No fee due year-over-year data is available for the current filters."

    sample = results[0]
    entity_key = 'branch'
    entity_title = 'Branches'
    for k, title in (('zone', 'Zones'), ('ri', 'RIs'), ('agm', 'AGMs'), ('s_type', 'Branch Types'), ('branch', 'Branches')):
        if k in sample:
            entity_key = k
            entity_title = title
            break

    heading = 'reduced' if ascending else 'increased'
    lines = [f"{entity_title} ranked by change in Fee Due ({heading} most first):"]
    for item in results:
        entity_val = item.get(entity_key, item.get('branch', ''))
        chg = item.get('difference', item.get('change', 0.0))
        sign = '+' if chg >= 0 else ''
        rank_str = f"{item['rank']}. " if 'rank' in item else ""
        lines.append(
            f"{rank_str}{entity_val} — "
            f"LY {_fmt_currency(item['last_year'])} → "
            f"CY {_fmt_currency(item['current_year'])} "
            f"({sign}{_fmt_currency(chg)})"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Revenue vs Salary formatters
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Revenue vs Salary formatters (with Intent-Based Output Projection)
# ---------------------------------------------------------------------------

def format_revenue_salary_summary(res: dict, target_metric: str = 'summary') -> str:
    if not res or res.get('branch_count', 0) == 0:
        return "No revenue vs salary data is available for the current filters."
    
    seg_lbl = res.get('segment_label', 'Total Overall')
    s_note = f" ({seg_lbl})" if res.get('segment', 'TOT') != 'TOT' else ""

    if target_metric == 'total_students':
        return f"Total Student Count{s_note}: {res['total_students']:,}"
    if target_metric == 'total_employees':
        return f"Total Employee Count{s_note}: {res['total_employees']:,}"
    if target_metric == 'total_salary':
        return f"Total Employee Salary Cost{s_note}: {_fmt_currency(res['total_salary'])}"
    if target_metric == 'total_revenue':
        return f"Total Net Revenue{s_note}: {_fmt_currency(res['total_revenue'])}"
    if target_metric == 'surplus':
        return f"Net Surplus{s_note}: {_fmt_currency(res['surplus'])}"
    if target_metric == 'cost_per_student':
        return f"Salary Cost per Student{s_note}: {_fmt_currency(res['cost_per_student'])}"
    if target_metric == 'fee_average':
        return f"Fee Average per Student{s_note}: {_fmt_currency(res['fee_average'])}"
    if target_metric == 'salary_vs_revenue_pct':
        return f"Salary vs Revenue %{s_note}: {res['salary_vs_revenue_pct']:.2f}%"
    if target_metric == 'student_teacher_ratio':
        return f"Student Teacher Ratio{s_note}: {res['student_teacher_ratio']:.2f}"
    
    if target_metric == 'revenue_vs_salary':
        return "\n".join([
            f"Revenue vs Salary Overview{s_note}:",
            f"- Total Net Revenue: {_fmt_currency(res['total_revenue'])}",
            f"- Total Employee Salary: {_fmt_currency(res['total_salary'])}",
            f"- Net Surplus: {_fmt_currency(res['surplus'])}",
            f"- Salary vs Revenue %: {res['salary_vs_revenue_pct']:.2f}%",
        ])

    lines = [
        f"Revenue vs Salary Summary ({seg_lbl}):",
        f"- Total Net Revenue: {_fmt_currency(res['total_revenue'])}",
        f"- Total Employee Salary: {_fmt_currency(res['total_salary'])}",
        f"- Net Surplus: {_fmt_currency(res['surplus'])}",
        f"- Total Student Count: {res['total_students']:,}",
        f"- Total Employee Count: {res['total_employees']:,}",
        f"- Fee Average per Student: {_fmt_currency(res['fee_average'])}",
        f"- Salary Cost per Student: {_fmt_currency(res['cost_per_student'])}",
        f"- Salary vs Revenue %: {res['salary_vs_revenue_pct']:.2f}%",
        f"- Student Teacher Ratio: {res['student_teacher_ratio']:.2f}",
    ]
    return "\n".join(lines)


def format_revenue_salary_segment_comparison(
    results: list[dict],
    target_metric: str = 'summary',
    segments_filter: list[str] | None = None
) -> str:
    if not results:
        return "No segment breakdown data is available for the current filters."

    filtered_res = results
    if segments_filter:
        filtered_res = [r for r in results if r['segment'] in segments_filter]
        if not filtered_res:
            filtered_res = results

    if len(filtered_res) == 2 and target_metric in ('total_revenue', 'total_salary', 'surplus', 'total_students'):
        s1, s2 = filtered_res[0], filtered_res[1]
        m_key = target_metric
        v1, v2 = s1[m_key], s2[m_key]
        diff = abs(v1 - v2)
        higher = s1 if v1 >= v2 else s2
        
        m_label = {
            'total_revenue': 'Revenue',
            'total_salary': 'Salary Cost',
            'surplus': 'Surplus',
            'total_students': 'Student Count'
        }.get(target_metric, 'Value')

        fmt_fn = _fmt_currency if 'revenue' in m_key or 'salary' in m_key or 'surplus' in m_key else (lambda x: f"{x:,}")

        lines = [
            f"{s1['segment_label']} vs {s2['segment_label']} {m_label}:",
            f"- {s1['segment_label']} ({s1['segment']}): {fmt_fn(v1)}",
            f"- {s2['segment_label']} ({s2['segment']}): {fmt_fn(v2)}",
            f"Difference: {fmt_fn(diff)}",
            f"Higher: {higher['segment_label']}"
        ]
        return "\n".join(lines)

    if target_metric == 'total_revenue':
        lines = ["Revenue Comparison across Academic Segments:"]
        for r in filtered_res:
            lines.append(f"- {r['segment_label']} ({r['segment']}): {_fmt_currency(r['total_revenue'])}")
        return "\n".join(lines)

    if target_metric == 'total_salary':
        lines = ["Salary Cost Comparison across Academic Segments:"]
        for r in filtered_res:
            lines.append(f"- {r['segment_label']} ({r['segment']}): {_fmt_currency(r['total_salary'])}")
        return "\n".join(lines)

    if target_metric == 'surplus':
        lines = ["Surplus Comparison across Academic Segments:"]
        for r in filtered_res:
            lines.append(f"- {r['segment_label']} ({r['segment']}): {_fmt_currency(r['surplus'])}")
        return "\n".join(lines)

    if target_metric == 'total_students':
        lines = ["Student Count Comparison across Academic Segments:"]
        for r in filtered_res:
            lines.append(f"- {r['segment_label']} ({r['segment']}): {r['total_students']:,}")
        return "\n".join(lines)

    if target_metric == 'student_teacher_ratio':
        lines = ["Student Teacher Ratio Comparison across Academic Segments:"]
        for r in filtered_res:
            lines.append(f"- {r['segment_label']} ({r['segment']}): {r['student_teacher_ratio']:.2f}")
        return "\n".join(lines)

    if target_metric == 'cost_per_student':
        lines = ["Cost per Student Comparison across Academic Segments:"]
        for r in filtered_res:
            lines.append(f"- {r['segment_label']} ({r['segment']}): {_fmt_currency(r['cost_per_student'])}")
        return "\n".join(lines)

    lines = ["Revenue vs Salary Comparison across Academic Segments:"]
    for res in filtered_res:
        lines.append(
            f"- {res['segment_label']} ({res['segment']}): "
            f"Revenue {_fmt_currency(res['total_revenue'])} | "
            f"Salary {_fmt_currency(res['total_salary'])} | "
            f"Surplus {_fmt_currency(res['surplus'])} | "
            f"Sal vs Rev {res['salary_vs_revenue_pct']:.2f}%"
        )
    return "\n".join(lines)


def format_revenue_salary_ranking(
    results: list[dict],
    metric_label: str,
    target_metric: str = 'total_revenue',
    group_dim: str = 'branch',
    ascending: bool = False
) -> str:
    if not results:
        return f"No ranking data available for {metric_label}."
    heading = 'lowest' if ascending else 'highest'
    g_low = group_dim.lower()
    dim_plural = 'Branches' if g_low == 'branch' else ('AGMs' if g_low == 'agm' else ('RIs' if g_low == 'ri' else f"{group_dim.capitalize()}s"))
    lines = [f"{dim_plural} ranked by {metric_label} ({heading} first):"]

    for item in results:
        entity = item['entity']
        rank = item['rank']
        if target_metric == 'total_students':
            lines.append(f"{rank}. {entity} — Total Students: {item['total_students']:,}")
        elif target_metric == 'total_employees':
            lines.append(f"{rank}. {entity} — Total Employees: {item['total_employees']:,}")
        elif target_metric == 'total_salary':
            lines.append(f"{rank}. {entity} — Salary Cost: {_fmt_currency(item['total_salary'])}")
        elif target_metric == 'total_revenue':
            lines.append(f"{rank}. {entity} — Net Revenue: {_fmt_currency(item['total_revenue'])}")
        elif target_metric == 'surplus':
            lines.append(
                f"{rank}. {entity} — Surplus: {_fmt_currency(item['surplus'])} "
                f"(Revenue: {_fmt_currency(item['total_revenue'])} | Salary: {_fmt_currency(item['total_salary'])})"
            )
        elif target_metric == 'cost_per_student':
            lines.append(f"{rank}. {entity} — Cost per Student: {_fmt_currency(item['cost_per_student'])}")
        elif target_metric == 'fee_average':
            lines.append(f"{rank}. {entity} — Fee Average: {_fmt_currency(item['fee_average'])}")
        elif target_metric == 'salary_vs_revenue_pct':
            lines.append(f"{rank}. {entity} — Salary vs Revenue %: {item['salary_vs_revenue_pct']:.2f}%")
        elif target_metric == 'student_teacher_ratio':
            lines.append(f"{rank}. {entity} — Student Teacher Ratio: {item['student_teacher_ratio']:.2f}")
        else:
            lines.append(
                f"{rank}. {entity} — "
                f"Revenue: {_fmt_currency(item['total_revenue'])} | "
                f"Salary: {_fmt_currency(item['total_salary'])} | "
                f"Surplus: {_fmt_currency(item['surplus'])} | "
                f"Sal vs Rev: {item['salary_vs_revenue_pct']:.2f}%"
            )
    return "\n".join(lines)


def format_revenue_salary_threshold(
    results: list[dict],
    metric_label: str,
    target_metric: str = 'total_revenue',
    op: str = '>',
    value: float = 0.0,
    group_dim: str = 'branch'
) -> str:
    op_symbol = {'>': 'above', 'gt': 'above', '>=': 'at least', 'gte': 'at least',
                 '<': 'below', 'lt': 'below', '<=': 'at most', 'lte': 'at most'}.get(op, op)
    g_low = group_dim.lower()
    dim_plural = 'Branches' if g_low == 'branch' else ('AGMs' if g_low == 'agm' else ('RIs' if g_low == 'ri' else f"{group_dim.capitalize()}s"))
    fmt_val = _fmt_currency(value) if target_metric in ('total_revenue', 'total_salary', 'surplus', 'cost_per_student', 'fee_average') else f"{value}"

    if not results:
        return f"No {dim_plural.lower()} found with {metric_label} {op_symbol} {fmt_val}."

    lines = [f"{len(results)} {dim_plural.lower()} with {metric_label} {op_symbol} {fmt_val}:"]
    for item in results:
        if target_metric == 'total_revenue':
            lines.append(f"- {item['entity']} — Net Revenue: {_fmt_currency(item['total_revenue'])}")
        elif target_metric == 'total_salary':
            lines.append(f"- {item['entity']} — Salary Cost: {_fmt_currency(item['total_salary'])}")
        elif target_metric == 'surplus':
            lines.append(f"- {item['entity']} — Surplus: {_fmt_currency(item['surplus'])}")
        elif target_metric == 'total_students':
            lines.append(f"- {item['entity']} — Students: {item['total_students']:,}")
        elif target_metric == 'cost_per_student':
            lines.append(f"- {item['entity']} — Cost per Student: {_fmt_currency(item['cost_per_student'])}")
        elif target_metric == 'salary_vs_revenue_pct':
            lines.append(f"- {item['entity']} — Sal vs Rev %: {item['salary_vs_revenue_pct']:.2f}%")
        else:
            lines.append(
                f"- {item['entity']} — Revenue: {_fmt_currency(item['total_revenue'])} | "
                f"Salary: {_fmt_currency(item['total_salary'])} | Surplus: {_fmt_currency(item['surplus'])}"
            )
    return "\n".join(lines)


