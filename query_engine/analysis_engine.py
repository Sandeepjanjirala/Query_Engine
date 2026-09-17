from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re
import pandas as pd

from .glossary import AGM_COLUMN, BRANCH_COLUMN, RI_COLUMN, ZONE_COLUMN
from .metric_registry import get_default_metric_registry, MetricSpec


@dataclass
class AnalysisResult:
    direct_answer: str
    headers: List[str]
    rows: List[List[str]]
    metric: str = ''
    group_dimension: str = 'Branch'
    operation: str = 'ranking'
    sections: List[Dict[str, Any]] = field(default_factory=list)
    evidence_title: str = "Detailed Evidence"


def ordinal_str(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


def format_display_ri_name(raw_name: str) -> str:
    s = str(raw_name).strip()
    s = re.sub(r'^mr\.?\s*', 'Mr. ', s, flags=re.IGNORECASE)
    s = re.sub(r'\b([A-Z])\.(?=[A-Za-z])', r'\1. ', s)
    return s.strip()


def determine_kpi_direction(metric_id: str, metric_spec: Optional[MetricSpec] = None) -> str:
    if metric_spec and metric_spec.kpi_direction:
        return metric_spec.kpi_direction

    m_lower = metric_id.lower()
    if any(k in m_lower for k in ['dpp', 'dropout', 'dp', 'fee_due', 'fd', 'vacant', 'vacancy', 'cost']):
        return 'negative'
    return 'positive'


def determine_data_type(metric_id: str, metric_spec: Optional[MetricSpec] = None) -> str:
    if metric_spec and metric_spec.data_type:
        return metric_spec.data_type
    m_lower = metric_id.lower()
    if any(k in m_lower for k in ['dpp', 'pct', 'percent', 'rate', 'ratio', 'occupancy', 'vacancy', 'sps']):
        return 'percentage'
    if any(k in m_lower for k in ['fd', 'fee', 'rev', 'salary', 'surplus', 'cost']):
        return 'currency'
    if any(k in m_lower for k in ['count', 'dp', 'nos', 'nocr', 'noor', 'novr', 'sc', 'zp', 'fdc']):
        return 'count'
    return 'numeric'


def format_value_str(val: float | int | None, data_type: str) -> str:
    if val is None or pd.isna(val):
        return "N/A"
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return str(val)

    if data_type == 'count':
        return f"{int(round(fval)):,}"
    elif data_type == 'percentage':
        return f"{fval:.2f}%"
    elif data_type == 'currency':
        v = int(round(fval))
        s = str(abs(v))
        prefix = "-" if v < 0 else ""
        if len(s) <= 3:
            fmt = s
        else:
            rest, last3 = s[:-3], s[-3:]
            parts = []
            while rest:
                parts.append(rest[-2:])
                rest = rest[:-2]
            fmt = f"{','.join(reversed(parts))},{last3}"
        return f"{prefix}₹{fmt}"
    else:
        return f"{fval:.2f}"


def format_diff_str(diff: float | int | None, data_type: str) -> str:
    if diff is None or pd.isna(diff):
        return "N/A"
    try:
        fdiff = float(diff)
    except (ValueError, TypeError):
        return str(diff)

    sign = "+" if fdiff >= 0 else ""
    if data_type == 'percentage':
        return f"{sign}{fdiff:.2f} percentage points"
    elif data_type == 'count':
        return f"{sign}{int(round(fdiff)):,}"
    elif data_type == 'currency':
        v = int(round(fdiff))
        s = str(abs(v))
        prefix = "-" if v < 0 else "+" if v > 0 else ""
        if len(s) <= 3:
            fmt = s
        else:
            rest, last3 = s[:-3], s[-3:]
            parts = []
            while rest:
                parts.append(rest[-2:])
                rest = rest[:-2]
            fmt = f"{prefix}₹{fmt}"
        return f"{prefix}₹{fmt}"
    else:
        return f"{sign}{fdiff:.2f}"


def format_compact_currency(val: float | int | None) -> str:
    if val is None or pd.isna(val):
        return "₹0"
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return str(val)
    if fval == 0:
        return "₹0"
    abs_val = abs(fval)
    sign = "-" if fval < 0 else ""
    if abs_val >= 100_00_000:
        cr_val = abs_val / 100_00_000
        formatted = f"{cr_val:.2f}".rstrip('0').rstrip('.')
        return f"{sign}₹{formatted} Cr"
    elif abs_val >= 100_000:
        lakh_val = abs_val / 100_000
        formatted = f"{lakh_val:.2f}".rstrip('0').rstrip('.')
        return f"{sign}₹{formatted} Lakh"
    elif abs_val >= 1_000:
        k_val = abs_val / 1_000
        formatted = f"{k_val:.2f}".rstrip('0').rstrip('.')
        return f"{sign}₹{formatted} K"
    else:
        v = int(round(abs_val))
        return f"{sign}₹{v:,}"


def format_compact_count(val: float | int | None) -> str:
    if val is None or pd.isna(val):
        return "0"
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return str(val)
    if fval == 0:
        return "0"
    abs_val = abs(fval)
    sign = "-" if fval < 0 else ""
    if abs_val >= 100_00_000:
        cr_val = abs_val / 100_00_000
        formatted = f"{cr_val:.2f}".rstrip('0').rstrip('.')
        return f"{sign}{formatted} Cr"
    elif abs_val >= 100_000:
        lakh_val = abs_val / 100_000
        formatted = f"{lakh_val:.2f}".rstrip('0').rstrip('.')
        return f"{sign}{formatted} Lakh"
    elif abs_val >= 1_000:
        k_val = abs_val / 1_000
        formatted = f"{k_val:.2f}".rstrip('0').rstrip('.')
        return f"{sign}{formatted} K"
    else:
        v = int(round(abs_val))
        return f"{sign}{v}"


def evaluate_status(diff: float | None, kpi_direction: str) -> str:
    if diff is None or pd.isna(diff):
        return '⚪ Not Comparable'
    if abs(diff) < 1e-6:
        return '⚪ Unchanged'
    if diff > 0:
        return '🟢 Improved' if kpi_direction == 'positive' else '🔴 Worsened'
    else:
        return '🔴 Worsened' if kpi_direction == 'positive' else '🟢 Improved'


def analyze_result(
    data: List[Dict[str, Any]],
    metric: str = 'CY-DPP',
    operation: str = 'ranking',
    group_dimension: str = 'Branch',
    context: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> AnalysisResult:
    if operation == 'group_by':
        return build_group_analysis(data, metric=metric, group_dimension=group_dimension, context=context)
    if operation == 'lookup':
        return build_lookup_analysis(data, columns=[metric], context=context)
    return build_ranking_analysis(data, metric=metric, ascending=False, group_dimension=group_dimension, context=context)


_EXTRA_LABELS = {
    'Avg-SPS': 'Average Students Per Section',
    'occupancy_rate': 'Room Occupancy Percentage',
    'vacancy_rate': 'Room Vacancy Percentage',
    'CY-DPP': 'Current Year Dropout Percentage',
    'LY-DPP': 'Last Year Dropout Percentage',
    'DPP': 'Dropout Percentage',
}


def get_clean_metric_label(col: str) -> str:
    """Returns human-readable metric label with clear Current Year / Last Year context."""
    if not col:
        return 'Value'
    if col in _EXTRA_LABELS:
        return _EXTRA_LABELS[col]

    is_cy = bool(re.search(r'^(?:CY[-_ ]|CY$)', col)) or 'CY-DPP' in col or 'CY_DPP' in col
    is_ly = bool(re.search(r'^(?:LY[-_ ]|LY$)', col)) or 'LY-DPP' in col or 'LY_DPP' in col
    base = re.sub(r'^(?:CY|LY)[-_ ]', '', col)

    registry = get_default_metric_registry()
    spec = registry.get(base) or registry.get(col)
    from .glossary import ABBREVIATIONS
    base_label = spec.display_name if spec else (ABBREVIATIONS.get(base) or base)

    if base_label.lower() in ('dropouts percentage', 'dropout percentage', 'dpp'):
        base_label = 'Dropout Percentage'

    if is_cy:
        return f"Current Year {base_label}"
    if is_ly:
        return f"Last Year {base_label}"
    return base_label


def build_lookup_analysis(results: List[Dict[str, Any]], columns: List[str], context: Optional[Dict[str, Any]] = None) -> AnalysisResult:
    """Concise direct answer card for single-entity metric lookups (e.g. Kakinada 1 dropout %)."""
    registry = get_default_metric_registry()
    if not results:
        return AnalysisResult(
            direct_answer="No matching entity data found for the current filters.",
            headers=[],
            rows=[],
            operation='lookup',
        )

    headers = ['Entity']
    for c in columns:
        lbl = get_clean_metric_label(c)
        headers.extend([f"CY {lbl}", f"LY {lbl}", "Change", "Status"])

    rows = []
    summary_lines = []

    for entry in results:
        entity = entry.get('branch') or entry.get('group') or entry.get('name') or 'Entity'
        row = [str(entity)]
        entity_parts = []

        for c in columns:
            spec = registry.get(c)
            kpi_dir = determine_kpi_direction(c, spec)
            data_type = determine_data_type(c, spec)
            lbl = get_clean_metric_label(c)

            cy = entry.get('current_year', entry.get(c))
            ly = entry.get('previous_year')
            diff = entry.get('difference')

            if cy is None and isinstance(entry.get(c), (int, float)):
                cy = entry.get(c)

            status = evaluate_status(diff, kpi_dir)
            cy_str = format_value_str(cy, data_type)
            ly_str = format_value_str(ly, data_type)
            diff_str = format_diff_str(diff, data_type)

            row.extend([cy_str, ly_str, diff_str, status])

            if ly is not None:
                entity_parts.append(f"{lbl}: {cy_str} (Last Year: {ly_str}, Change: {diff_str}, Status: {status})")
            else:
                entity_parts.append(f"{lbl}: {cy_str}")

        if len(entity_parts) == 1:
            summary_lines.append(f"**{entity} — {entity_parts[0]}**")
        else:
            summary_lines.append(f"**{entity}** — " + ", ".join(entity_parts))
        rows.append(row)

    direct_answer = "\n\n".join(summary_lines)
    return AnalysisResult(
        direct_answer=direct_answer,
        headers=headers,
        rows=rows,
        operation='lookup',
    )


def build_ranking_analysis(
    results: List[Dict[str, Any]],
    metric: str = 'CY-DPP',
    ascending: bool = False,
    group_dimension: str = 'Branch',
    operation: str = 'ranking',
    context: Optional[Dict[str, Any]] = None,
    is_fallback: bool = False,
    direction: Optional[str] = None,
) -> AnalysisResult:
    """Ranked evidence table + terminology-correct summary sentence (Highest/Worst vs Top Performer; Lowest)."""
    registry = get_default_metric_registry()
    spec = registry.get(metric)

    kpi_dir = determine_kpi_direction(metric, spec)
    data_type = determine_data_type(metric, spec)
    metric_label = spec.display_name if spec else metric

    group_dim_hdr = group_dimension.upper() if group_dimension.lower() in ('ri', 'agm') else group_dimension.title()
    diff_col_name = 'Difference' if (metric in ('SD', 'NSD') or operation == 'yoy') else 'Change'

    if not results:
        return AnalysisResult(
            direct_answer=f"No data available for {metric_label} with the current filters.",
            headers=['Rank', group_dim_hdr, 'Current Year', 'Last Year', diff_col_name, 'Status'],
            rows=[],
            metric=metric,
            group_dimension=group_dimension,
            operation=operation,
        )

    # Determine heading terminology
    if operation == 'yoy':
        if direction == 'negative':
            heading_title = f"Branches with Biggest Improvement in {metric_label}" if kpi_dir == 'negative' else f"Branches with Largest Decline in {metric_label}"
        elif direction == 'positive':
            heading_title = f"Branches with Largest Increase in {metric_label}" if kpi_dir == 'negative' else f"Top Performing Branches by {metric_label} Growth"
        else:
            heading_title = f"Branches by {metric_label} Change"
    elif kpi_dir == 'negative':
        heading_title = f"Lowest {metric_label} Branches" if ascending else f"Highest {metric_label} Branches"
    else:
        heading_title = f"Lowest Performing Branches by {metric_label}" if ascending else f"Top Performing Branches by {metric_label}"

    headers = ['Rank', group_dim_hdr, 'Current Year', 'Last Year', diff_col_name, 'Status']
    rows = []

    for idx, item in enumerate(results, start=1):
        rank = item.get('rank', idx)
        name = item.get('branch') or item.get('group') or item.get('name') or f"{group_dim_hdr} {idx}"
        cy = item.get('current_year', item.get('value', 0))
        ly = item.get('previous_year')
        diff = item.get('difference', item.get('change'))

        if diff is None and cy is not None and ly is not None:
            diff = cy - ly

        status = evaluate_status(diff, kpi_dir)
        cy_str = format_value_str(cy, data_type)
        ly_str = format_value_str(ly, data_type)
        diff_str = format_diff_str(diff, data_type)

        rows.append([str(rank), str(name), cy_str, ly_str, diff_str, status])

    top_entity = rows[0][1]
    top_val = rows[0][2]

    scope_str = ""
    if context:
        if context.get('ri') and str(context['ri']).lower() != 'all':
            scope_str = f" under RI {context['ri']}"
        elif context.get('agm') and str(context['agm']).lower() != 'all':
            scope_str = f" under AGM {context['agm']}"
        elif context.get('zone') and str(context['zone']).lower() != 'all':
            scope_str = f" in {context['zone']} Zone"

    fallback_prefix = ""
    if is_fallback:
        target_scope = scope_str if scope_str else " in this scope"
        fallback_prefix = f"No branches{target_scope} are above the 10% dropout threshold. Showing all branches for completeness.\n\n"

    if operation == 'yoy':
        top_diff = rows[0][4]
        if direction == 'negative':
            summary_label = "Biggest improvement" if kpi_dir == 'negative' else "Largest decline"
        elif direction == 'positive':
            summary_label = "Largest increase" if kpi_dir == 'negative' else "Largest gain"
        else:
            summary_label = "Largest change"
        summary_sentence = f"**{heading_title}**: {summary_label}{scope_str} is **{top_entity}** (Change: {top_diff}, Current: {top_val})."
    elif kpi_dir == 'negative':
        term = "Lowest" if ascending else "Highest"
        summary_sentence = f"{fallback_prefix}**{heading_title}**: {term} branch{scope_str} is **{top_entity}** ({top_val})."
    else:
        term = "Lowest" if ascending else "Top"
        summary_sentence = f"**{heading_title}**: {term} performer is **{top_entity}** ({top_val})."

    return AnalysisResult(
        direct_answer=summary_sentence,
        headers=headers,
        rows=rows,
        metric=metric,
        group_dimension=group_dimension,
        operation='ranking',
    )


def build_group_analysis(
    results: List[Dict[str, Any]],
    metric: str = 'DP',
    group_dimension: str = 'Zone',
    context: Optional[Dict[str, Any]] = None,
    is_fallback: bool = False,
    year: Optional[str] = None,
) -> AnalysisResult:
    """Group summary table with derived weighted metric totals."""
    registry = get_default_metric_registry()
    spec = registry.get(metric)

    kpi_dir = determine_kpi_direction(metric, spec)
    data_type = determine_data_type(metric, spec)
    metric_label = spec.display_name if spec else metric
    if metric_label.lower() in ('dropouts percentage', 'dropout percentage', 'dpp'):
        metric_label = 'Dropout Percentage'

    dim_hdr = group_dimension.upper() if group_dimension.lower() in ('ri', 'agm') else group_dimension.title()

    if not results:
        return AnalysisResult(
            direct_answer=f"No data available to aggregate {metric_label} by {dim_hdr}.",
            headers=[dim_hdr, 'Current Year', 'Last Year', 'Difference', 'Status'],
            rows=[],
            metric=metric,
            group_dimension=group_dimension,
            operation='group_by',
        )

    # If this is a single entity lookup with an explicit year (e.g. "RI Padmaja current year dropout percentage")
    if len(results) == 1 and year in ('CY', 'LY'):
        item = results[0]
        entity_name = item.get('group') or item.get('name') or dim_hdr
        if year == 'CY':
            val = item.get('current_year', item.get('value', 0))
            val_str = format_value_str(val, data_type)
            ans = f"**{dim_hdr} {entity_name} — Current Year {metric_label}: {val_str}**"
        else:
            val = item.get('previous_year', item.get('value', 0))
            val_str = format_value_str(val, data_type)
            ans = f"**{dim_hdr} {entity_name} — Last Year {metric_label}: {val_str}**"

        return AnalysisResult(
            direct_answer=ans,
            headers=[],
            rows=[],
            metric=metric,
            group_dimension=group_dimension,
            operation='lookup',
        )

    scope_str = ""
    if context:
        if context.get('agm') and str(context['agm']).lower() != 'all':
            scope_str = f" under AGM {context['agm']}"
        elif context.get('zone') and str(context['zone']).lower() != 'all':
            scope_str = f" in {context['zone']} Zone"

    fallback_prefix = ""
    if is_fallback:
        target_scope = scope_str if scope_str else " in this scope"
        fallback_prefix = f"No {dim_hdr}s{target_scope} are above the 10% dropout threshold. Showing all {dim_hdr}s for completeness.\n\n"

    headers = [dim_hdr, 'Current Year', 'Last Year', 'Difference', 'Status']
    rows = []
    for item in results:
        group_name = item.get('group') or item.get('name') or 'Group'
        cy = item.get('current_year', item.get('value', 0))
        ly = item.get('previous_year')
        diff = item.get('difference', item.get('change'))

        if diff is None and cy is not None and ly is not None:
            diff = cy - ly

        status = evaluate_status(diff, kpi_dir)
        cy_str = format_value_str(cy, data_type)
        ly_str = format_value_str(ly, data_type)
        diff_str = format_diff_str(diff, data_type)

        rows.append([str(group_name), cy_str, ly_str, diff_str, status])

    if len(results) == 1:
        summary_sentence = f"**{dim_hdr} {rows[0][0]} — {metric_label}**: Current Year **{rows[0][1]}**, Last Year **{rows[0][2]}** ({rows[0][3]}, {rows[0][4]})."
    else:
        summary_sentence = f"{fallback_prefix}**{metric_label} by {dim_hdr}**: Aggregated across {len(results)} {group_dimension.lower()}s."

    return AnalysisResult(
        direct_answer=summary_sentence,
        headers=headers,
        rows=rows,
        metric=metric,
        group_dimension=group_dimension,
        operation='group_by',
    )


def extract_existing_new_stats(df_scoped: pd.DataFrame) -> Dict[str, Any]:
    if 'E-CY-DP' not in df_scoped.columns or 'N-CY-DP' not in df_scoped.columns:
        return {'available': False}

    e_dp = float(pd.to_numeric(df_scoped['E-CY-DP'], errors='coerce').sum())
    n_dp = float(pd.to_numeric(df_scoped['N-CY-DP'], errors='coerce').sum())
    tot_dp = e_dp + n_dp

    e_pct = (e_dp / tot_dp * 100) if tot_dp > 0 else 0.0
    n_pct = (n_dp / tot_dp * 100) if tot_dp > 0 else 0.0

    levels = {}
    for code, label in [('PP', 'Pre Primary'), ('PS', 'Primary School'), ('HS', 'High School')]:
        e_col = "PP-E-CY-DP" if code == 'PP' else ("PS-E-CY-DP" if code == 'PS' else "HS-E-CY-DP")
        n_col = "PP-N-CY-DP" if code == 'PP' else ("PS-N-CY-DP" if code == 'PS' else "HS-N-CY-DP")
        c_e = float(pd.to_numeric(df_scoped[e_col], errors='coerce').sum()) if e_col in df_scoped.columns else 0.0
        c_n = float(pd.to_numeric(df_scoped[n_col], errors='coerce').sum()) if n_col in df_scoped.columns else 0.0
        c_tot = c_e + c_n
        levels[code] = {
            'label': label,
            'e_dp': c_e,
            'n_dp': c_n,
            'e_pct': (c_e / c_tot * 100) if c_tot > 0 else 0.0,
            'n_pct': (c_n / c_tot * 100) if c_tot > 0 else 0.0,
        }

    return {
        'available': True,
        'e_dp': e_dp,
        'n_dp': n_dp,
        'tot_dp': tot_dp,
        'e_pct': e_pct,
        'n_pct': n_pct,
        'levels': levels,
    }


def build_ri_analysis(df: pd.DataFrame, ri_name: str, context: Optional[Dict[str, Any]] = None) -> AnalysisResult:
    """Complete Executive Management Review for RI Performance."""
    ri_clean = str(ri_name).casefold().replace('.', '').replace('mr', '').strip()
    ri_series = df[RI_COLUMN].astype(str).str.casefold().str.replace('.', '', regex=False).str.replace('mr', '', regex=False).str.strip()
    ri_df = df[ri_series == ri_clean]

    if ri_df.empty:
        return AnalysisResult(
            direct_answer=f"# RI Analysis — {ri_name}\n\nNo performance data found for RI {ri_name}.",
            headers=['Branch', 'This Year', 'Last Year', 'Change', 'Dropout %', 'Last Year %', 'Change'],
            rows=[],
            operation='analysis',
            evidence_title="Detailed Branch Data",
        )

    matched_ri_official = ri_df[RI_COLUMN].iloc[0]
    display_ri_name = format_display_ri_name(matched_ri_official)
    ri_last_name = display_ri_name.split()[-1] if display_ri_name.split() else display_ri_name

    ri_branches = ri_df[BRANCH_COLUMN].dropna().unique()
    n_ri = len(ri_branches)
    ri_zones = ri_df[ZONE_COLUMN].dropna().unique()
    zone_str = ", ".join(ri_zones)

    # Zone context & coverage
    zone_df = df[df[ZONE_COLUMN].isin(ri_zones)]
    n_zone = zone_df[BRANCH_COLUMN].nunique()
    coverage_pct = (n_ri / n_zone * 100) if n_zone > 0 else 0

    # Overall Dropout Health
    cy_dp = float(pd.to_numeric(ri_df['CY-DP'], errors='coerce').sum()) if 'CY-DP' in ri_df.columns else 0.0
    ly_dp = float(pd.to_numeric(ri_df['LY-DP'], errors='coerce').sum()) if 'LY-DP' in ri_df.columns else 0.0
    dp_change = cy_dp - ly_dp
    dp_change_pct = (dp_change / ly_dp * 100) if ly_dp > 0 else 0.0

    cy_ns = float(pd.to_numeric(ri_df['CY-NS'], errors='coerce').sum()) if 'CY-NS' in ri_df.columns else 0.0
    ly_ns = float(pd.to_numeric(ri_df['LY-NS'], errors='coerce').sum()) if 'LY-NS' in ri_df.columns else 0.0

    cy_dpp = (cy_dp / cy_ns * 100) if cy_ns > 0 else 0.0
    ly_dpp = (ly_dp / ly_ns * 100) if ly_ns > 0 else 0.0
    dpp_change = cy_dpp - ly_dpp

    # Level counts
    pp_dp_val = float(pd.to_numeric(ri_df['CY-PP-DP'] if 'CY-PP-DP' in ri_df.columns else ri_df['PP-CY-DP'], errors='coerce').sum()) if ('CY-PP-DP' in ri_df.columns or 'PP-CY-DP' in ri_df.columns) else 0.0
    ps_dp_val = float(pd.to_numeric(ri_df['CY-PS-DP'] if 'CY-PS-DP' in ri_df.columns else ri_df['PS-CY-DP'], errors='coerce').sum()) if ('CY-PS-DP' in ri_df.columns or 'PS-CY-DP' in ri_df.columns) else 0.0
    hs_dp_val = float(pd.to_numeric(ri_df['CY-HS-DP'] if 'CY-HS-DP' in ri_df.columns else ri_df['HS-CY-DP'], errors='coerce').sum()) if ('CY-HS-DP' in ri_df.columns or 'HS-CY-DP' in ri_df.columns) else 0.0

    pp_ns_val = float(pd.to_numeric(ri_df['CY-PP-NS'] if 'CY-PP-NS' in ri_df.columns else ri_df['PP-CY-NS'], errors='coerce').sum()) if ('CY-PP-NS' in ri_df.columns or 'PP-CY-NS' in ri_df.columns) else 0.0
    ps_ns_val = float(pd.to_numeric(ri_df['CY-PS-NS'] if 'CY-PS-NS' in ri_df.columns else ri_df['PS-CY-NS'], errors='coerce').sum()) if ('CY-PS-NS' in ri_df.columns or 'PS-CY-NS' in ri_df.columns) else 0.0
    hs_ns_val = float(pd.to_numeric(ri_df['CY-HS-NS'] if 'CY-HS-NS' in ri_df.columns else ri_df['HS-CY-NS'], errors='coerce').sum()) if ('CY-HS-NS' in ri_df.columns or 'HS-CY-NS' in ri_df.columns) else 0.0

    pp_ly_dp = float(pd.to_numeric(ri_df['LY-PP-DP'] if 'LY-PP-DP' in ri_df.columns else ri_df['PP-LY-DP'], errors='coerce').sum()) if ('LY-PP-DP' in ri_df.columns or 'PP-LY-DP' in ri_df.columns) else 0.0
    ps_ly_dp = float(pd.to_numeric(ri_df['LY-PS-DP'] if 'LY-PS-DP' in ri_df.columns else ri_df['PS-LY-DP'], errors='coerce').sum()) if ('LY-PS-DP' in ri_df.columns or 'PS-LY-DP' in ri_df.columns) else 0.0
    hs_ly_dp = float(pd.to_numeric(ri_df['LY-HS-DP'] if 'LY-HS-DP' in ri_df.columns else ri_df['HS-LY-DP'], errors='coerce').sum()) if ('LY-HS-DP' in ri_df.columns or 'HS-LY-DP' in ri_df.columns) else 0.0

    pp_ly_ns = float(pd.to_numeric(ri_df['LY-PP-NS'] if 'LY-PP-NS' in ri_df.columns else ri_df['PP-LY-NS'], errors='coerce').sum()) if ('LY-PP-NS' in ri_df.columns or 'PP-LY-NS' in ri_df.columns) else 0.0
    ps_ly_ns = float(pd.to_numeric(ri_df['LY-PS-NS'] if 'LY-PS-NS' in ri_df.columns else ri_df['PS-LY-NS'], errors='coerce').sum()) if ('LY-PS-NS' in ri_df.columns or 'PS-LY-NS' in ri_df.columns) else 0.0
    hs_ly_ns = float(pd.to_numeric(ri_df['LY-HS-NS'] if 'LY-HS-NS' in ri_df.columns else ri_df['HS-LY-NS'], errors='coerce').sum()) if ('LY-HS-NS' in ri_df.columns or 'HS-LY-NS' in ri_df.columns) else 0.0

    pp_cy_dpp = (pp_dp_val / pp_ns_val * 100) if pp_ns_val > 0 else 0.0
    ps_cy_dpp = (ps_dp_val / ps_ns_val * 100) if ps_ns_val > 0 else 0.0
    hs_cy_dpp = (hs_dp_val / hs_ns_val * 100) if hs_ns_val > 0 else 0.0

    pp_ly_dpp = (pp_ly_dp / pp_ly_ns * 100) if pp_ly_ns > 0 else 0.0
    ps_ly_dpp = (ps_ly_dp / ps_ly_ns * 100) if ps_ly_ns > 0 else 0.0
    hs_ly_dpp = (hs_ly_dp / hs_ly_ns * 100) if hs_ly_ns > 0 else 0.0

    # Zone Rankings for branches under RI
    zone_work = zone_df.copy()
    zone_work['CY-DPP'] = pd.to_numeric(zone_work['CY-DPP'], errors='coerce')
    zone_work = zone_work.sort_values('CY-DPP', ascending=False)
    zone_work['zone_rank'] = range(1, len(zone_work) + 1)

    branch_rank_map = dict(zip(zone_work[BRANCH_COLUMN], zone_work['zone_rank']))

    # Process all RI branches sorted by CY-DPP descending
    ri_df_sorted = ri_df.copy()
    ri_df_sorted['CY-DPP'] = pd.to_numeric(ri_df_sorted['CY-DPP'], errors='coerce')
    ri_df_sorted = ri_df_sorted.sort_values('CY-DPP', ascending=False)

    evidence_rows = []
    high_risk_list = []
    all_branches_info = []

    imp_cnt = 0
    worsened_cnt = 0
    unchanged_cnt = 0
    improved_branch_names = []

    for rank, (_, row) in enumerate(ri_df_sorted.iterrows(), start=1):
        b_name = str(row[BRANCH_COLUMN])
        b_cy_dp = float(row['CY-DP']) if 'CY-DP' in row.index and not pd.isna(row['CY-DP']) else 0.0
        b_ly_dp = float(row['LY-DP']) if 'LY-DP' in row.index and not pd.isna(row['LY-DP']) else 0.0
        b_dp_diff = b_cy_dp - b_ly_dp

        b_cy_dpp = float(row['CY-DPP']) if 'CY-DPP' in row.index and not pd.isna(row['CY-DPP']) else 0.0
        b_ly_dpp = float(row['LY-DPP']) if 'LY-DPP' in row.index and not pd.isna(row['LY-DPP']) else 0.0
        b_dpp_diff = b_cy_dpp - b_ly_dpp

        z_rank = branch_rank_map.get(b_name, rank)
        z_pos_str = f"{ordinal_str(z_rank)} highest of {n_zone}"

        status_emoji = "🟢" if b_dpp_diff < -1e-6 else ("🔴" if b_dpp_diff > 1e-6 else "⚪")

        branch_item = {
            'branch': b_name,
            'cy_dp': b_cy_dp,
            'ly_dp': b_ly_dp,
            'cy_dpp': b_cy_dpp,
            'ly_dpp': b_ly_dpp,
            'diff': b_dpp_diff,
            'status_emoji': status_emoji,
            'zone_rank_num': z_rank,
            'zone_pos_str': z_pos_str,
        }
        all_branches_info.append(branch_item)

        if b_dpp_diff < -1e-6:
            imp_cnt += 1
            improved_branch_names.append(b_name)
        elif b_dpp_diff > 1e-6:
            worsened_cnt += 1
        else:
            unchanged_cnt += 1

        if b_cy_dpp > 10.0:
            high_risk_list.append(branch_item)

        evidence_rows.append([
            b_name,
            f"{int(round(b_cy_dp)):,}",
            f"{int(round(b_ly_dp)):,}",
            f"{'+' if b_dp_diff >= 0 else ''}{int(round(b_dp_diff)):,}",
            f"{b_cy_dpp:.2f}%",
            f"{b_ly_dpp:.2f}%",
            f"{'+' if b_dpp_diff >= 0 else ''}{b_dpp_diff:.2f}% {status_emoji}",
        ])

    # Highest current dropout branch and Biggest increase branch
    highest_current_branch = all_branches_info[0] if all_branches_info else None
    worsened_branches = [b for b in all_branches_info if b['diff'] > 0]
    biggest_increase_branch = max(worsened_branches, key=lambda x: x['diff']) if worsened_branches else None

    # Section 5: Dropouts by School Level (PP, PS, HS)
    level_data = [
        {'level': 'Pre Primary', 'cy_dp': pp_dp_val, 'cy_ns': pp_ns_val, 'cy_dpp': pp_cy_dpp, 'ly_dpp': pp_ly_dpp, 'change': pp_cy_dpp - pp_ly_dpp},
        {'level': 'Primary School', 'cy_dp': ps_dp_val, 'cy_ns': ps_ns_val, 'cy_dpp': ps_cy_dpp, 'ly_dpp': ps_ly_dpp, 'change': ps_cy_dpp - ps_ly_dpp},
        {'level': 'High School', 'cy_dp': hs_dp_val, 'cy_ns': hs_ns_val, 'cy_dpp': hs_cy_dpp, 'ly_dpp': hs_ly_dpp, 'change': hs_cy_dpp - hs_ly_dpp},
    ]
    for l in level_data:
        chg = l['change']
        emoji = "🟢" if chg < -1e-6 else ("🔴" if chg > 1e-6 else "⚪")
        arrow = "↓ " if chg < -1e-6 else ("↑ " if chg > 1e-6 else "")
        l['change_str'] = f"{arrow}{abs(chg):.2f}% {emoji}"

    highest_level = max(level_data, key=lambda x: x['cy_dpp']) if level_data else None
    lowest_level = min(level_data, key=lambda x: x['cy_dpp']) if level_data else None

    improved_levels = [l for l in level_data if l['change'] < -1.0]
    best_level = min(improved_levels, key=lambda x: x['change']) if improved_levels else None

    # Build Sections
    # 1. About This RI
    sec1_content = (
        f"{display_ri_name} is responsible for **{n_ri} branches** in the {zone_str} zone.\n\n"
        f"* {zone_str} has **{n_zone} branches**\n"
        f"* {ri_last_name} manages **{n_ri} of them**\n"
        f"* This is **{coverage_pct:.0f}% of the zone's branches**"
    )

    # 2. Dropout Situation
    dp_verb = "increased" if dp_change >= 0 else "decreased"
    health_status_str = "become worse" if dpp_change > 0 else "improved"
    health_emoji = "🔴" if dpp_change > 0 else "🟢"
    sec2_content = (
        f"{ri_last_name}'s {n_ri} branches have **{int(round(cy_dp)):,} dropouts this year**, compared with **{int(round(ly_dp)):,} last year**.\n"
        f"These include **{int(round(pp_dp_val)):,} Pre Primary, {int(round(ps_dp_val)):,} Primary School, and {int(round(hs_dp_val)):,} High School dropouts**.\n\n"
        f"* **Dropouts count:** {int(round(cy_dp)):,} → {int(round(ly_dp)):,} last year (change: {'' if dp_change < 0 else '+'}{int(round(dp_change)):,} students / PP: {int(round(pp_dp_val)):,}, PS: {int(round(ps_dp_val)):,}, HS: {int(round(hs_dp_val)):,})\n"
        f"* **Dropout percentage:** {ly_dpp:.2f}% → {cy_dpp:.2f}% ({'' if dpp_change < 0 else '+'}{dpp_change:.2f} percentage points / PP: {pp_ly_dpp:.2f}% → {pp_cy_dpp:.2f}%, PS: {ps_ly_dpp:.2f}% → {ps_cy_dpp:.2f}%, HS: {hs_ly_dpp:.2f}% → {hs_cy_dpp:.2f}%)\n"
        f"* **Total dropouts percentage change:** {'' if dp_change_pct < 0 else '+'}{dp_change_pct:.2f}%\n"
        f"* This means the dropout situation has **{health_status_str}** this year. {health_emoji}"
    )

    # 3. Existing vs New Student Dropouts
    en_stats = extract_existing_new_stats(ri_df)
    if en_stats['available']:
        sec3_content = (
            f"Of the current-year dropouts across {ri_last_name}'s {n_ri} branches:\n\n"
            f"* **Existing students:** {int(round(en_stats['e_dp'])):,} dropouts (**{en_stats['e_pct']:.1f}%**)\n"
            f"* **New students:** {int(round(en_stats['n_dp'])):,} dropouts (**{en_stats['n_pct']:.1f}%**)\n\n"
            f"**By school level:**\n"
            f"* **Pre Primary:** Existing {int(round(en_stats['levels']['PP']['e_dp'])):,} ({en_stats['levels']['PP']['e_pct']:.1f}%), New {int(round(en_stats['levels']['PP']['n_dp'])):,} ({en_stats['levels']['PP']['n_pct']:.1f}%)\n"
            f"* **Primary School:** Existing {int(round(en_stats['levels']['PS']['e_dp'])):,} ({en_stats['levels']['PS']['e_pct']:.1f}%), New {int(round(en_stats['levels']['PS']['n_dp'])):,} ({en_stats['levels']['PS']['n_pct']:.1f}%)\n"
            f"* **High School:** Existing {int(round(en_stats['levels']['HS']['e_dp'])):,} ({en_stats['levels']['HS']['e_pct']:.1f}%), New {int(round(en_stats['levels']['HS']['n_dp'])):,} ({en_stats['levels']['HS']['n_pct']:.1f}%)"
        )
    else:
        sec3_content = "Existing vs New student dropout breakdown is not available in the current dataset."

    # 4. Branches with High Dropout
    n_hr = len(high_risk_list)
    hr_count_str = f"Only **{n_hr} of {ri_last_name}'s {n_ri} branches** is" if n_hr == 1 else f"**{n_hr} of {ri_last_name}'s {n_ri} branches** are"
    if n_hr == 0:
        hr_count_str = f"None of {ri_last_name}'s {n_ri} branches are"

    hr_table_lines = [
        "| Branch | This Year | Last Year | Change | Position in Zone |",
        "| :--- | ---: | ---: | ---: | ---: |",
    ]
    for h in high_risk_list:
        hr_table_lines.append(f"| {h['branch']} | {h['cy_dpp']:.2f}% | {h['ly_dpp']:.2f}% | +{h['diff']:.2f}% | {h['zone_pos_str']} |")

    hr_note = ""
    if high_risk_list:
        b_names_hr = ", ".join([h['branch'] for h in high_risk_list])
        hr_note = f"\n\n**{b_names_hr} need{'s' if n_hr == 1 else ''} attention** because its dropout percentage is already above 10% and has increased from last year. 🔴"

    sec4_content = (
        f"The risk level is set at **10% dropout**.\n\n"
        f"{hr_count_str} above this level:\n\n"
        + "\n".join(hr_table_lines) + hr_note
    ) if high_risk_list else f"The risk level is set at **10% dropout**.\n\n{hr_count_str} above this level. 🟢"

    # 5. Which School Level Has More Dropouts?
    level_table_lines = [
        "Looking at PP, PS and HS:\n",
        "| Level | Dropouts | Students | Dropout % | Last Year | Change |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for l in level_data:
        level_table_lines.append(
            f"| {l['level']} | {int(round(l['cy_dp'])):,} | {int(round(l['cy_ns'])):,} | "
            f"{l['cy_dpp']:.2f}% | {l['ly_dpp']:.2f}% | {l['change_str']} |"
        )
    level_summary_lines = []
    if highest_level and lowest_level:
        level_summary_lines.append(f"\n\n**Main finding:** {highest_level['level']} has the **highest dropout percentage at {highest_level['cy_dpp']:.2f}%**.")
        level_summary_lines.append(f"\n\n{lowest_level['level']} has the **lowest dropout percentage at {lowest_level['cy_dpp']:.2f}%**.")
    if best_level:
        level_summary_lines.append(f"\n\nThere is also a positive point: **{best_level['level']} improved significantly**, falling from {best_level['ly_dpp']:.2f}% to {best_level['cy_dpp']:.2f}%.")

    sec5_content = "\n".join(level_table_lines) + "".join(level_summary_lines)

    # 6. What Happened Across the Branches?
    direction_conclusion = "**most of the branches are moving in the wrong direction**." if worsened_cnt > imp_cnt else "**most of the branches are improving or stable**."
    sec6_content = (
        f"Out of the {n_ri} branches:\n\n"
        f"* 🟢 **{imp_cnt} branch{'es' if imp_cnt != 1 else ''} improved**\n"
        f"* 🔴 **{worsened_cnt} branch{'es' if worsened_cnt != 1 else ''} became worse**\n"
        f"* ⚪ **{unchanged_cnt} branch{'es' if unchanged_cnt != 1 else ''} stayed the same**\n\n"
        f"So the main concern is that {direction_conclusion}"
    )

    # 7. Branches That Need Attention
    sec7_parts = ["There are two different things to look at:\n"]
    if highest_current_branch:
        sec7_parts.append(
            f"**Highest current dropout**\n\n"
            f"🔴 **{highest_current_branch['branch']} — {highest_current_branch['cy_dpp']:.2f}%**\n\n"
            f"It is {'above' if highest_current_branch['cy_dpp'] >= 10.0 else 'near'} the 10% risk level and is the **{highest_current_branch['zone_pos_str']}**.\n"
        )
    if biggest_increase_branch:
        sec7_parts.append(
            f"**Biggest increase from last year**\n\n"
            f"⚠️ **{biggest_increase_branch['branch']} — {biggest_increase_branch['cy_dpp']:.2f}%**\n\n"
            f"Its dropout percentage increased by **{biggest_increase_branch['diff']:.2f} percentage points**, which is the biggest increase among {ri_last_name}'s {n_ri} branches.\n\n"
            f"So although {biggest_increase_branch['branch']} is currently {'below' if biggest_increase_branch['cy_dpp'] < 10.0 else 'at'} 10%, its situation is **getting worse faster than the other branches**."
        )
    sec7_content = "\n".join(sec7_parts)

    # 8. Overall Conclusion
    sec8_lines = [f"**{ri_last_name}'s overall dropout situation needs attention.**\n"]
    if high_risk_list:
        sec8_lines.append(f"The biggest concern is **{high_risk_list[0]['branch']}**, because it is already above the 10% risk level.")
    elif highest_current_branch:
        sec8_lines.append(f"The highest dropout branch is **{highest_current_branch['branch']}** at {highest_current_branch['cy_dpp']:.2f}%.")

    if biggest_increase_branch:
        sec8_lines.append(f"The second concern is **{biggest_increase_branch['branch']}**, because it has the biggest increase from last year.")

    sec8_lines.append(f"Also, **{worsened_cnt} out of {n_ri} branches have worsened**, which shows that the problem is not limited to one branch.")

    pos_points = []
    if best_level:
        pos_points.append(f"**{best_level['level']} dropout has improved strongly**")
    if improved_branch_names:
        imp_str = ", ".join(improved_branch_names)
        pos_points.append(f"**{imp_str} is the only branch that improved overall**" if len(improved_branch_names) == 1 else f"**{imp_str} improved overall**")

    if pos_points:
        sec8_lines.append("On the positive side, " + " and ".join(pos_points) + ".")

    sec8_content = "\n\n".join(sec8_lines)

    sections = [
        {'title': '1. About This RI', 'content': sec1_content},
        {'title': '2. Dropout Situation', 'content': sec2_content},
        {'title': '3. Existing vs New Student Dropouts', 'content': sec3_content},
        {'title': '4. Branches with High Dropout', 'content': sec4_content},
        {'title': '5. Which School Level Has More Dropouts?', 'content': sec5_content},
        {'title': '6. What Happened Across Branches?', 'content': sec6_content},
        {'title': '7. Branches That Need Attention', 'content': sec7_content},
        {'title': '8. Overall Conclusion', 'content': sec8_content},
    ]

    direct_answer = f"# RI Statistics — {display_ri_name}"
    headers = ['Branch', 'This Year', 'Last Year', 'Change', 'Dropout %', 'Last Year %', 'Change']

    return AnalysisResult(
        direct_answer=direct_answer,
        headers=headers,
        rows=evidence_rows,
        metric='CY-DPP',
        group_dimension='Branch',
        operation='analysis',
        sections=sections,
        evidence_title="Detailed Branch Data",
    )


def build_agm_analysis(df: pd.DataFrame, agm_name: str, context: Optional[Dict[str, Any]] = None) -> AnalysisResult:
    """Complete 11-Section Executive Management Review for AGM Performance."""
    agm_clean = str(agm_name).casefold().replace('.', '').replace('mr', '').strip()
    agm_series = df[AGM_COLUMN].astype(str).str.casefold().str.replace('.', '', regex=False).str.replace('mr', '', regex=False).str.strip()
    agm_df = df[agm_series == agm_clean]

    if agm_df.empty:
        return AnalysisResult(
            direct_answer=f"# AGM Statistics — {agm_name}\n\nNo performance data found for AGM {agm_name}.",
            headers=['Rank', 'Branch', 'Zone', 'RI', 'This Year', 'Last Year', 'Change', 'Dropout %', 'Last Year %', 'Change', 'Status'],
            rows=[],
            operation='analysis',
            evidence_title="Detailed Branch Data",
        )

    matched_agm_official = agm_df[AGM_COLUMN].iloc[0]
    display_agm_name = format_display_ri_name(matched_agm_official)
    agm_last_name = display_agm_name.split()[-1] if display_agm_name.split() else display_agm_name

    agm_branches = agm_df[BRANCH_COLUMN].dropna().unique()
    n_branches = len(agm_branches)

    agm_zones = agm_df[ZONE_COLUMN].dropna().unique()
    n_zones = len(agm_zones)

    agm_ris = agm_df[RI_COLUMN].dropna().unique()
    n_ris = len(agm_ris)

    # 1. About This AGM
    zone_breakdown_lines = []
    for z in agm_zones:
        z_cnt = agm_df[agm_df[ZONE_COLUMN] == z][BRANCH_COLUMN].nunique()
        zone_breakdown_lines.append(f"* **{z}**: {z_cnt} branches")

    sec1_content = (
        f"{display_agm_name} manages **{n_zones} zones, {n_ris} RIs and {n_branches} branches**.\n\n"
        f"**Zone breakdown:**\n" +
        "\n".join(zone_breakdown_lines) +
        f"\n\nTotal: **{n_branches} branches**"
    )

    # 2. Overall Dropout Situation
    cy_dp = float(pd.to_numeric(agm_df['CY-DP'], errors='coerce').sum()) if 'CY-DP' in agm_df.columns else 0.0
    ly_dp = float(pd.to_numeric(agm_df['LY-DP'], errors='coerce').sum()) if 'LY-DP' in agm_df.columns else 0.0
    dp_change = cy_dp - ly_dp
    dp_change_pct = (dp_change / ly_dp * 100) if ly_dp > 0 else 0.0

    cy_ns = float(pd.to_numeric(agm_df['CY-NS'], errors='coerce').sum()) if 'CY-NS' in agm_df.columns else 0.0
    ly_ns = float(pd.to_numeric(agm_df['LY-NS'], errors='coerce').sum()) if 'LY-NS' in agm_df.columns else 0.0

    cy_dpp = (cy_dp / cy_ns * 100) if cy_ns > 0 else 0.0
    ly_dpp = (ly_dp / ly_ns * 100) if ly_ns > 0 else 0.0
    dpp_change = cy_dpp - ly_dpp

    # Level counts
    pp_dp_val = float(pd.to_numeric(agm_df['CY-PP-DP'] if 'CY-PP-DP' in agm_df.columns else agm_df['PP-CY-DP'], errors='coerce').sum()) if ('CY-PP-DP' in agm_df.columns or 'PP-CY-DP' in agm_df.columns) else 0.0
    ps_dp_val = float(pd.to_numeric(agm_df['CY-PS-DP'] if 'CY-PS-DP' in agm_df.columns else agm_df['PS-CY-DP'], errors='coerce').sum()) if ('CY-PS-DP' in agm_df.columns or 'PS-CY-DP' in agm_df.columns) else 0.0
    hs_dp_val = float(pd.to_numeric(agm_df['CY-HS-DP'] if 'CY-HS-DP' in agm_df.columns else agm_df['HS-CY-DP'], errors='coerce').sum()) if ('CY-HS-DP' in agm_df.columns or 'HS-CY-DP' in agm_df.columns) else 0.0

    # Level DPPs
    pp_ns_val = float(pd.to_numeric(agm_df['CY-PP-NS'] if 'CY-PP-NS' in agm_df.columns else agm_df['PP-CY-NS'], errors='coerce').sum()) if ('CY-PP-NS' in agm_df.columns or 'PP-CY-NS' in agm_df.columns) else 0.0
    ps_ns_val = float(pd.to_numeric(agm_df['CY-PS-NS'] if 'CY-PS-NS' in agm_df.columns else agm_df['PS-CY-NS'], errors='coerce').sum()) if ('CY-PS-NS' in agm_df.columns or 'PS-CY-NS' in agm_df.columns) else 0.0
    hs_ns_val = float(pd.to_numeric(agm_df['CY-HS-NS'] if 'CY-HS-NS' in agm_df.columns else agm_df['HS-CY-NS'], errors='coerce').sum()) if ('CY-HS-NS' in agm_df.columns or 'HS-CY-NS' in agm_df.columns) else 0.0

    pp_ly_dp = float(pd.to_numeric(agm_df['LY-PP-DP'] if 'LY-PP-DP' in agm_df.columns else agm_df['PP-LY-DP'], errors='coerce').sum()) if ('LY-PP-DP' in agm_df.columns or 'PP-LY-DP' in agm_df.columns) else 0.0
    ps_ly_dp = float(pd.to_numeric(agm_df['LY-PS-DP'] if 'LY-PS-DP' in agm_df.columns else agm_df['PS-LY-DP'], errors='coerce').sum()) if ('LY-PS-DP' in agm_df.columns or 'PS-LY-DP' in agm_df.columns) else 0.0
    hs_ly_dp = float(pd.to_numeric(agm_df['LY-HS-DP'] if 'LY-HS-DP' in agm_df.columns else agm_df['HS-LY-DP'], errors='coerce').sum()) if ('LY-HS-DP' in agm_df.columns or 'HS-LY-DP' in agm_df.columns) else 0.0

    pp_ly_ns = float(pd.to_numeric(agm_df['LY-PP-NS'] if 'LY-PP-NS' in agm_df.columns else agm_df['PP-LY-NS'], errors='coerce').sum()) if ('LY-PP-NS' in agm_df.columns or 'PP-LY-NS' in agm_df.columns) else 0.0
    ps_ly_ns = float(pd.to_numeric(agm_df['LY-PS-NS'] if 'LY-PS-NS' in agm_df.columns else agm_df['PS-LY-NS'], errors='coerce').sum()) if ('LY-PS-NS' in agm_df.columns or 'PS-LY-NS' in agm_df.columns) else 0.0
    hs_ly_ns = float(pd.to_numeric(agm_df['LY-HS-NS'] if 'LY-HS-NS' in agm_df.columns else agm_df['HS-LY-NS'], errors='coerce').sum()) if ('LY-HS-NS' in agm_df.columns or 'HS-LY-NS' in agm_df.columns) else 0.0

    pp_cy_dpp = (pp_dp_val / pp_ns_val * 100) if pp_ns_val > 0 else 0.0
    ps_cy_dpp = (ps_dp_val / ps_ns_val * 100) if ps_ns_val > 0 else 0.0
    hs_cy_dpp = (hs_dp_val / hs_ns_val * 100) if hs_ns_val > 0 else 0.0

    pp_ly_dpp = (pp_ly_dp / pp_ly_ns * 100) if pp_ly_ns > 0 else 0.0
    ps_ly_dpp = (ps_ly_dp / ps_ly_ns * 100) if ps_ly_ns > 0 else 0.0
    hs_ly_dpp = (hs_ly_dp / hs_ly_ns * 100) if hs_ly_ns > 0 else 0.0

    health_status_str = "become worse" if dpp_change > 0 else "improved"
    health_emoji = "🔴" if dpp_change > 0 else "🟢"

    sec2_content = (
        f"The AGM's {n_branches} branches have **{int(round(cy_dp)):,} dropouts this year**, compared with **{int(round(ly_dp)):,} last year**.\n"
        f"These include **{int(round(pp_dp_val)):,} Pre Primary, {int(round(ps_dp_val)):,} Primary School, and {int(round(hs_dp_val)):,} High School dropouts**.\n\n"
        f"* **Dropouts count:** {int(round(cy_dp)):,} → {int(round(ly_dp)):,} last year (change: {'' if dp_change < 0 else '+'}{int(round(dp_change)):,} students / PP: {int(round(pp_dp_val)):,}, PS: {int(round(ps_dp_val)):,}, HS: {int(round(hs_dp_val)):,})\n"
        f"* **Dropout percentage:** {ly_dpp:.2f}% → {cy_dpp:.2f}% ({'' if dpp_change < 0 else '+'}{dpp_change:.2f} percentage points / PP: {pp_ly_dpp:.2f}% → {pp_cy_dpp:.2f}%, PS: {ps_ly_dpp:.2f}% → {ps_cy_dpp:.2f}%, HS: {hs_ly_dpp:.2f}% → {hs_cy_dpp:.2f}%)\n"
        f"* **Total dropouts percentage change:** {'' if dp_change_pct < 0 else '+'}{dp_change_pct:.2f}%\n"
        f"* Overall status: **{health_status_str}** {health_emoji}"
    )

    # 3. Existing vs New Student Dropouts
    en_stats = extract_existing_new_stats(agm_df)
    if en_stats['available']:
        sec3_content = (
            f"Of the current-year dropouts across {display_agm_name}'s {n_branches} branches:\n\n"
            f"* **Existing students:** {int(round(en_stats['e_dp'])):,} dropouts (**{en_stats['e_pct']:.1f}%**)\n"
            f"* **New students:** {int(round(en_stats['n_dp'])):,} dropouts (**{en_stats['n_pct']:.1f}%**)\n\n"
            f"**By school level:**\n"
            f"* **Pre Primary:** Existing {int(round(en_stats['levels']['PP']['e_dp'])):,} ({en_stats['levels']['PP']['e_pct']:.1f}%), New {int(round(en_stats['levels']['PP']['n_dp'])):,} ({en_stats['levels']['PP']['n_pct']:.1f}%)\n"
            f"* **Primary School:** Existing {int(round(en_stats['levels']['PS']['e_dp'])):,} ({en_stats['levels']['PS']['e_pct']:.1f}%), New {int(round(en_stats['levels']['PS']['n_dp'])):,} ({en_stats['levels']['PS']['n_pct']:.1f}%)\n"
            f"* **High School:** Existing {int(round(en_stats['levels']['HS']['e_dp'])):,} ({en_stats['levels']['HS']['e_pct']:.1f}%), New {int(round(en_stats['levels']['HS']['n_dp'])):,} ({en_stats['levels']['HS']['n_pct']:.1f}%)"
        )
    else:
        sec3_content = "Existing vs New student dropout breakdown is not available in the current dataset."

    # 4. Dropouts by School Level
    level_data = [
        {'level': 'Pre Primary', 'cy_dp': pp_dp_val, 'cy_ns': pp_ns_val, 'cy_dpp': pp_cy_dpp, 'ly_dpp': pp_ly_dpp, 'change': pp_cy_dpp - pp_ly_dpp},
        {'level': 'Primary School', 'cy_dp': ps_dp_val, 'cy_ns': ps_ns_val, 'cy_dpp': ps_cy_dpp, 'ly_dpp': ps_ly_dpp, 'change': ps_cy_dpp - ps_ly_dpp},
        {'level': 'High School', 'cy_dp': hs_dp_val, 'cy_ns': hs_ns_val, 'cy_dpp': hs_cy_dpp, 'ly_dpp': hs_ly_dpp, 'change': hs_cy_dpp - hs_ly_dpp},
    ]

    highest_level = max(level_data, key=lambda x: x['cy_dpp'])
    lowest_level = min(level_data, key=lambda x: x['cy_dpp'])

    level_lines = [
        "| Level | Dropouts | Students | Dropout % | Last Year | Change | Status |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | :--- |",
    ]
    for l in level_data:
        chg = l['change']
        emoji = "🟢" if chg < -1e-6 else ("🔴" if chg > 1e-6 else "⚪")
        chg_str = f"{'' if chg < 0 else '+'}{chg:.2f} percentage points"
        level_lines.append(f"| {l['level']} | {int(round(l['cy_dp'])):,} | {int(round(l['cy_ns'])):,} | {l['cy_dpp']:.2f}% | {l['ly_dpp']:.2f}% | {chg_str} | {emoji} |")

    sec4_content = (
        "\n".join(level_lines) +
        f"\n\n**Highest dropout percentage:** {highest_level['level']} — {highest_level['cy_dpp']:.2f}%\n"
        f"**Lowest dropout percentage:** {lowest_level['level']} — {lowest_level['cy_dpp']:.2f}%"
    )

    # 5. Zone Performance
    zone_perf_list = []
    worsened_zones_cnt = 0
    for z in agm_zones:
        z_df = agm_df[agm_df[ZONE_COLUMN] == z]
        z_b_cnt = z_df[BRANCH_COLUMN].nunique()
        z_cy_dp = float(pd.to_numeric(z_df['CY-DP'], errors='coerce').sum())
        z_ly_dp = float(pd.to_numeric(z_df['LY-DP'], errors='coerce').sum())
        z_cy_ns = float(pd.to_numeric(z_df['CY-NS'], errors='coerce').sum())
        z_ly_ns = float(pd.to_numeric(z_df['LY-NS'], errors='coerce').sum())

        z_cy_dpp = (z_cy_dp / z_cy_ns * 100) if z_cy_ns > 0 else 0.0
        z_ly_dpp = (z_ly_dp / z_ly_ns * 100) if z_ly_ns > 0 else 0.0
        z_diff = z_cy_dpp - z_ly_dpp
        z_emoji = "🟢" if z_diff < -1e-6 else ("🔴" if z_diff > 1e-6 else "⚪")
        if z_diff > 1e-6:
            worsened_zones_cnt += 1

        zone_perf_list.append({
            'name': z,
            'branches': z_b_cnt,
            'cy_dpp': z_cy_dpp,
            'ly_dpp': z_ly_dpp,
            'diff': z_diff,
            'emoji': z_emoji,
        })

    zone_perf_list.sort(key=lambda x: x['cy_dpp'], reverse=True)
    highest_zone = zone_perf_list[0]
    worst_worsened_zone = max(zone_perf_list, key=lambda x: x['diff'])
    best_improved_zone = min(zone_perf_list, key=lambda x: x['diff'])

    zone_table_lines = [
        "| Zone | Branches | This Year % | Last Year % | Change | Status |",
        "| :--- | ---: | ---: | ---: | ---: | :--- |",
    ]
    for zp in zone_perf_list:
        zone_table_lines.append(f"| {zp['name']} | {zp['branches']} | {zp['cy_dpp']:.2f}% | {zp['ly_dpp']:.2f}% | {'' if zp['diff'] < 0 else '+'}{zp['diff']:.2f} percentage points | {zp['emoji']} |")

    sec5_content = (
        "\n".join(zone_table_lines) +
        f"\n\n**{worsened_zones_cnt} of {n_zones} zones became worse.**\n\n"
        f"* **Highest dropout zone:** {highest_zone['name']} ({highest_zone['cy_dpp']:.2f}%)\n"
        f"* **Zone with biggest increase in dropouts:** {worst_worsened_zone['name']} (+{worst_worsened_zone['diff']:.2f} percentage points)\n"
        f"* **Biggest improvement zone:** {best_improved_zone['name']} ({'' if best_improved_zone['diff'] < 0 else '+'}{best_improved_zone['diff']:.2f} percentage points)"
    )

    # 6. RI Performance
    ri_perf_list = []
    for r in agm_ris:
        r_df = agm_df[agm_df[RI_COLUMN] == r]
        r_zone = r_df[ZONE_COLUMN].iloc[0] if not r_df.empty else "Zone"
        r_b_cnt = r_df[BRANCH_COLUMN].nunique()
        r_cy_dp = float(pd.to_numeric(r_df['CY-DP'], errors='coerce').sum())
        r_cy_ns = float(pd.to_numeric(r_df['CY-NS'], errors='coerce').sum())
        r_ly_dp = float(pd.to_numeric(r_df['LY-DP'], errors='coerce').sum())
        r_ly_ns = float(pd.to_numeric(r_df['LY-NS'], errors='coerce').sum())

        r_cy_dpp = (r_cy_dp / r_cy_ns * 100) if r_cy_ns > 0 else 0.0
        r_ly_dpp = (r_ly_dp / r_ly_ns * 100) if r_ly_ns > 0 else 0.0
        r_diff = r_cy_dpp - r_ly_dpp
        r_emoji = "🟢" if r_diff < -1e-6 else ("🔴" if r_diff > 1e-6 else "⚪")

        ri_perf_list.append({
            'name': format_display_ri_name(r),
            'zone': r_zone,
            'branches': r_b_cnt,
            'cy_dpp': r_cy_dpp,
            'ly_dpp': r_ly_dpp,
            'diff': r_diff,
            'emoji': r_emoji,
        })

    ri_perf_list.sort(key=lambda x: x['cy_dpp'], reverse=True)
    highest_ri = ri_perf_list[0]
    worst_worsened_ri = max(ri_perf_list, key=lambda x: x['diff'])
    best_improved_ri = min(ri_perf_list, key=lambda x: x['diff'])

    ri_table_lines = [
        "| RI | Zone | Branches | This Year % | Last Year % | Change | Status |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | :--- |",
    ]
    for rp in ri_perf_list:
        ri_table_lines.append(f"| {rp['name']} | {rp['zone']} | {rp['branches']} | {rp['cy_dpp']:.2f}% | {rp['ly_dpp']:.2f}% | {'' if rp['diff'] < 0 else '+'}{rp['diff']:.2f} percentage points | {rp['emoji']} |")

    sec6_content = (
        "\n".join(ri_table_lines) +
        f"\n\n* **Highest dropout RI:** {highest_ri['name']} ({highest_ri['cy_dpp']:.2f}%)\n"
        f"* **RI with biggest increase in dropouts:** {worst_worsened_ri['name']} (+{worst_worsened_ri['diff']:.2f} percentage points)\n"
        f"* **Biggest improvement RI:** {best_improved_ri['name']} ({'' if best_improved_ri['diff'] < 0 else '+'}{best_improved_ri['diff']:.2f} percentage points)"
    )

    # 7. High-Risk Branches (>10%) & Detailed Branch Rows
    zone_df_full = df[df[ZONE_COLUMN].isin(agm_zones)].copy()
    zone_df_full['CY-DPP'] = pd.to_numeric(zone_df_full['CY-DPP'], errors='coerce')
    zone_ranks_map = {}
    for z in agm_zones:
        z_sub = zone_df_full[zone_df_full[ZONE_COLUMN] == z].sort_values('CY-DPP', ascending=False)
        z_tot = z_sub[BRANCH_COLUMN].nunique()
        for rk, (_, r_row) in enumerate(z_sub.iterrows(), start=1):
            zone_ranks_map[str(r_row[BRANCH_COLUMN])] = f"{ordinal_str(rk)} highest of {z_tot}"

    agm_df_sorted = agm_df.copy()
    agm_df_sorted['CY-DPP'] = pd.to_numeric(agm_df_sorted['CY-DPP'], errors='coerce')
    agm_df_sorted = agm_df_sorted.sort_values('CY-DPP', ascending=False)

    high_risk_branches = []
    all_branch_items = []
    evidence_rows = []

    imp_cnt = 0
    worsened_cnt = 0
    unchanged_cnt = 0

    for rank, (_, row) in enumerate(agm_df_sorted.iterrows(), start=1):
        b_name = str(row[BRANCH_COLUMN])
        b_zone = str(row[ZONE_COLUMN])
        b_ri = format_display_ri_name(row[RI_COLUMN])

        b_cy_dp = float(row['CY-DP']) if 'CY-DP' in row.index and not pd.isna(row['CY-DP']) else 0.0
        b_ly_dp = float(row['LY-DP']) if 'LY-DP' in row.index and not pd.isna(row['LY-DP']) else 0.0
        b_dp_diff = b_cy_dp - b_ly_dp

        b_cy_dpp = float(row['CY-DPP']) if 'CY-DPP' in row.index and not pd.isna(row['CY-DPP']) else 0.0
        b_ly_dpp = float(row['LY-DPP']) if 'LY-DPP' in row.index and not pd.isna(row['LY-DPP']) else 0.0
        b_dpp_diff = b_cy_dpp - b_ly_dpp

        status_emoji = "🟢" if b_dpp_diff < -1e-6 else ("🔴" if b_dpp_diff > 1e-6 else "⚪")
        z_pos = zone_ranks_map.get(b_name, "N/A")

        item = {
            'branch': b_name,
            'zone': b_zone,
            'ri': b_ri,
            'cy_dp': b_cy_dp,
            'ly_dp': b_ly_dp,
            'cy_dpp': b_cy_dpp,
            'ly_dpp': b_ly_dpp,
            'diff': b_dpp_diff,
            'status_emoji': status_emoji,
            'zone_pos': z_pos,
        }
        all_branch_items.append(item)

        if b_dpp_diff < -1e-6:
            imp_cnt += 1
        elif b_dpp_diff > 1e-6:
            worsened_cnt += 1
        else:
            unchanged_cnt += 1

        if b_cy_dpp > 10.0:
            high_risk_branches.append(item)

        evidence_rows.append([
            str(rank),
            b_name,
            b_zone,
            b_ri,
            f"{int(round(b_cy_dp)):,}",
            f"{int(round(b_ly_dp)):,}",
            f"{'+' if b_dp_diff >= 0 else ''}{int(round(b_dp_diff)):,}",
            f"{b_cy_dpp:.2f}%",
            f"{b_ly_dpp:.2f}%",
            f"{'+' if b_dpp_diff >= 0 else ''}{b_dpp_diff:.2f}% {status_emoji}",
        ])

    n_hr = len(high_risk_branches)
    hr_table_lines = [
        "| Branch | RI | Zone | This Year % | Last Year % | Change | Zone Position |",
        "| :--- | :--- | :--- | ---: | ---: | ---: | ---: |",
    ]
    for h in high_risk_branches:
        hr_table_lines.append(f"| {h['branch']} | {h['ri']} | {h['zone']} | {h['cy_dpp']:.2f}% | {h['ly_dpp']:.2f}% | {'' if h['diff'] < 0 else '+'}{h['diff']:.2f} percentage points | {h['zone_pos']} |")

    sec7_content = (
        f"The risk level is set at **10% dropout**.\n\n"
        f"**{n_hr} of {n_branches} branches** are above this level:\n\n"
        + "\n".join(hr_table_lines)
    ) if high_risk_branches else f"The risk level is set at **10% dropout**.\n\n**None of {display_agm_name}'s {n_branches} branches** are above this level. 🟢"

    # 8. Biggest Changes
    worsened_b_list = [b for b in all_branch_items if b['diff'] > 0]
    improved_b_list = [b for b in all_branch_items if b['diff'] < 0]

    biggest_increase_b = max(worsened_b_list, key=lambda x: x['diff']) if worsened_b_list else None
    biggest_improvement_b = min(improved_b_list, key=lambda x: x['diff']) if improved_b_list else None

    sec8_lines = []
    if biggest_increase_b:
        sec8_lines.append(f"* ⚠️ **Biggest increase in dropout percentage:** {biggest_increase_b['branch']} ({biggest_increase_b['ri']} / {biggest_increase_b['zone']}) — {biggest_increase_b['cy_dpp']:.2f}% (+{biggest_increase_b['diff']:.2f} percentage points)")
    if biggest_improvement_b:
        sec8_lines.append(f"* 🟢 **Biggest improvement in dropout percentage:** {biggest_improvement_b['branch']} ({biggest_improvement_b['ri']} / {biggest_improvement_b['zone']}) — {biggest_improvement_b['cy_dpp']:.2f}% ({biggest_improvement_b['diff']:.2f} percentage points)")
    sec8_content = "\n".join(sec8_lines) or "No significant branch movement detected."

    # 9. What Happened Across the Branches?
    sec9_content = (
        f"Across all {n_branches} branches under {display_agm_name}:\n\n"
        f"* 🟢 **{imp_cnt} branches improved**\n"
        f"* 🔴 **{worsened_cnt} branches became worse**\n"
        f"* ⚪ **{unchanged_cnt} branches stayed the same**"
    )

    # 10. What Needs Attention
    p1_list = [b for b in high_risk_branches if b['diff'] > 0]
    p2_list = [b for b in high_risk_branches if b['diff'] < 0]
    p3_list = [b for b in all_branch_items if b['cy_dpp'] <= 10.0 and b['diff'] >= 1.0]
    p4_list = [b for b in all_branch_items if b['diff'] <= -1.0]

    sec10_lines = ["Prioritized management action areas:\n"]
    if p1_list:
        p1_str = ", ".join([f"**{b['branch']}** ({b['cy_dpp']:.2f}%, +{b['diff']:.2f} pp)" for b in p1_list[:3]])
        sec10_lines.append(f"1. 🔴 **High risk + became worse:** {p1_str} — Priority action required.")
    if p2_list:
        p2_str = ", ".join([f"**{b['branch']}** ({b['cy_dpp']:.2f}%, {b['diff']:.2f} pp)" for b in p2_list[:3]])
        sec10_lines.append(f"2. 🟠 **High risk + improving:** {p2_str} — High risk, but progress is being made.")
    if p3_list:
        p3_str = ", ".join([f"**{b['branch']}** ({b['cy_dpp']:.2f}%, +{b['diff']:.2f} pp)" for b in p3_list[:3]])
        sec10_lines.append(f"3. ⚠️ **Below 10% but rapidly increasing:** {p3_str} — Early warning alert.")
    if p4_list:
        p4_str = ", ".join([f"**{b['branch']}** ({b['cy_dpp']:.2f}%, {b['diff']:.2f} pp)" for b in p4_list[:3]])
        sec10_lines.append(f"4. 🟢 **Strongest improvement:** {p4_str} — Positive model branches.")

    sec10_content = "\n\n".join(sec10_lines)

    # 11. Overall Conclusion
    sec11_lines = [f"**AGM {agm_last_name}'s overall dropout situation needs attention.**\n"]
    if p1_list:
        sec11_lines.append(f"The highest priority concern is **{p1_list[0]['branch']}**, which is above the 10% risk level and became worse.")
    elif high_risk_branches:
        sec11_lines.append(f"The highest risk branch is **{high_risk_branches[0]['branch']}** at {high_risk_branches[0]['cy_dpp']:.2f}%.")

    if biggest_increase_b:
        sec11_lines.append(f"The second concern is **{biggest_increase_b['branch']}**, which showed the biggest increase (+{biggest_increase_b['diff']:.2f} percentage points) across the AGM's branches.")

    sec11_lines.append(f"Overall, **{worsened_cnt} out of {n_branches} branches became worse**, indicating that operational focus is needed across multiple zones.")

    if p4_list:
        sec11_lines.append(f"On the positive side, **{p4_list[0]['branch']}** demonstrated strong improvement ({p4_list[0]['diff']:.2f} percentage points).")

    sec11_content = "\n\n".join(sec11_lines)

    sections = [
        {'title': '1. About This AGM', 'content': sec1_content},
        {'title': '2. Overall Dropout Situation', 'content': sec2_content},
        {'title': '3. Existing vs New Student Dropouts', 'content': sec3_content},
        {'title': '4. Dropouts by School Level', 'content': sec4_content},
        {'title': '5. Zone Performance', 'content': sec5_content},
        {'title': '6. RI Performance', 'content': sec6_content},
        {'title': '7. High-Risk Branches', 'content': sec7_content},
        {'title': '8. Biggest Changes', 'content': sec8_content},
        {'title': '9. What Happened Across Branches?', 'content': sec9_content},
        {'title': '10. What Needs Attention', 'content': sec10_content},
        {'title': '11. Overall Conclusion', 'content': sec11_content},
    ]

    direct_answer = f"# AGM Statistics — {display_agm_name}"
    headers = ['Rank', 'Branch', 'Zone', 'RI', 'This Year', 'Last Year', 'Change', 'Dropout %', 'Last Year %', 'Change', 'Status']

    return AnalysisResult(
        direct_answer=direct_answer,
        headers=headers,
        rows=evidence_rows,
        metric='CY-DPP',
        group_dimension='Branch',
        operation='analysis',
        sections=sections,
        evidence_title="Detailed Branch Data",
    )


def build_branch_analysis(
    df: pd.DataFrame,
    branch_name: str,
    context: Optional[Dict[str, Any]] = None,
) -> AnalysisResult:
    """
    Executes a complete 10-section Branch Statistics Review.
    """
    df_branch = df[df[BRANCH_COLUMN].astype(str).str.strip().str.casefold() == str(branch_name).strip().casefold()]
    if df_branch.empty:
        branch_matches = [b for b in df[BRANCH_COLUMN].dropna().unique() if str(branch_name).strip().casefold() in str(b).casefold()]
        if branch_matches:
            df_branch = df[df[BRANCH_COLUMN] == branch_matches[0]]

    if df_branch.empty:
        return AnalysisResult(
            direct_answer=f"# Branch Statistics — {branch_name}\n\nNo branch data found for '{branch_name}'.",
            headers=[],
            rows=[],
            operation='analysis',
        )

    row = df_branch.iloc[0]
    raw_branch_name = str(row[BRANCH_COLUMN]).strip()
    zone_name = str(row[ZONE_COLUMN]).strip() if pd.notna(row.get(ZONE_COLUMN)) else "N/A"
    ri_name = format_display_ri_name(str(row[RI_COLUMN])) if pd.notna(row.get(RI_COLUMN)) else "N/A"
    agm_name = format_display_ri_name(str(row[AGM_COLUMN])) if pd.notna(row.get(AGM_COLUMN)) else "N/A"

    df_zone = df[df[ZONE_COLUMN] == zone_name]
    n_zone_branches = len(df_zone)
    df_zone_sorted = df_zone.sort_values(by='CY-DPP', ascending=False)
    branch_pos_in_zone = list(df_zone_sorted[BRANCH_COLUMN]).index(raw_branch_name) + 1 if raw_branch_name in list(df_zone_sorted[BRANCH_COLUMN]) else 1
    zone_pos_str = f"{ordinal_str(branch_pos_in_zone)} highest dropout of {n_zone_branches} branches"

    zone_total_dp = float(pd.to_numeric(df_zone['CY-DP'], errors='coerce').sum())
    zone_total_ns = float(pd.to_numeric(df_zone['CY-NS'], errors='coerce').sum())
    zone_dpp = (zone_total_dp / zone_total_ns * 100) if zone_total_ns > 0 else 0.0

    cy_dp = float(pd.to_numeric(row.get('CY-DP', 0), errors='coerce'))
    ly_dp = float(pd.to_numeric(row.get('LY-DP', 0), errors='coerce'))
    dp_diff = cy_dp - ly_dp
    dp_pct_change = ((cy_dp - ly_dp) / ly_dp * 100) if ly_dp > 0 else 0.0

    cy_ns = float(pd.to_numeric(row.get('CY-NS', 0), errors='coerce'))
    ly_ns = float(pd.to_numeric(row.get('LY-NS', 0), errors='coerce'))

    cy_dpp = float(pd.to_numeric(row.get('CY-DPP', 0), errors='coerce'))
    ly_dpp = float(pd.to_numeric(row.get('LY-DPP', 0), errors='coerce'))
    dpp_diff = cy_dpp - ly_dpp

    pp_dp_val = float(pd.to_numeric(row.get('PP-CY-DP', 0), errors='coerce'))
    pp_ly_dp_val = float(pd.to_numeric(row.get('PP-LY-DP', 0), errors='coerce'))
    pp_ns_val = float(pd.to_numeric(row.get('PP-CY-NS', 0), errors='coerce'))
    pp_cy_dpp = float(pd.to_numeric(row.get('PP-CY-DPP', 0), errors='coerce'))
    pp_ly_dpp = float(pd.to_numeric(row.get('PP-LY-DPP', 0), errors='coerce'))

    ps_dp_val = float(pd.to_numeric(row.get('PS-CY-DP', 0), errors='coerce'))
    ps_ly_dp_val = float(pd.to_numeric(row.get('PS-LY-DP', 0), errors='coerce'))
    ps_ns_val = float(pd.to_numeric(row.get('PS-CY-NS', 0), errors='coerce'))
    ps_cy_dpp = float(pd.to_numeric(row.get('PS-CY-DPP', 0), errors='coerce'))
    ps_ly_dpp = float(pd.to_numeric(row.get('PS-LY-DPP', 0), errors='coerce'))

    hs_dp_val = float(pd.to_numeric(row.get('HS-CY-DP', 0), errors='coerce'))
    hs_ly_dp_val = float(pd.to_numeric(row.get('HS-LY-DP', 0), errors='coerce'))
    hs_ns_val = float(pd.to_numeric(row.get('HS-CY-NS', 0), errors='coerce'))
    hs_cy_dpp = float(pd.to_numeric(row.get('HS-CY-DPP', 0), errors='coerce'))
    hs_ly_dpp = float(pd.to_numeric(row.get('HS-LY-DPP', 0), errors='coerce'))

    cy_sc = float(pd.to_numeric(row.get('CY-SC', row.get('SC', 0)), errors='coerce'))
    ly_sc = float(pd.to_numeric(row.get('LY-SC', 0), errors='coerce'))
    str_val = float(pd.to_numeric(row.get('CY-STR', row.get('STR', (cy_ns / cy_sc if cy_sc > 0 else 0))), errors='coerce'))
    ly_str_val = (ly_ns / ly_sc) if ly_sc > 0 else 0.0

    nos_val = int(round(float(pd.to_numeric(row.get('CY-NOS', row.get('NOS', 0)), errors='coerce'))))
    ly_nos_val = int(round(float(pd.to_numeric(row.get('LY-NOS', 0), errors='coerce'))))

    sps_val = float(pd.to_numeric(row.get('CY-Avg-SPS', row.get('Avg-SPS', 0)), errors='coerce'))
    ly_sps_val = float(pd.to_numeric(row.get('LY-Avg-SPS', 0), errors='coerce'))

    nocr_val = int(round(float(pd.to_numeric(row.get('CY-NOCR', row.get('NOCR', 0)), errors='coerce'))))
    ly_nocr_val = int(round(float(pd.to_numeric(row.get('LY-NOCR', 0), errors='coerce'))))

    noor_val = int(round(float(pd.to_numeric(row.get('CY-NOOR', row.get('NOOR', 0)), errors='coerce'))))
    ly_noor_val = int(round(float(pd.to_numeric(row.get('LY-NOOR', 0), errors='coerce'))))

    novr_val = int(round(float(pd.to_numeric(row.get('CY-NOVR', row.get('NOVR', 0)), errors='coerce'))))
    ly_novr_val = int(round(float(pd.to_numeric(row.get('LY-NOVR', 0), errors='coerce'))))

    occupancy_pct = (noor_val / nocr_val * 100) if nocr_val > 0 else 0.0

    # 1. About This Branch
    sec1_content = (
        f"* **Branch:** {raw_branch_name}\n"
        f"* **AGM:** {agm_name}\n"
        f"* **RI:** {ri_name}\n"
        f"* **Zone:** {zone_name}\n\n"
        f"{raw_branch_name} is one of the branches under **{ri_name}** in the **{zone_name} zone**.\n\n"
        f"* **Position in zone:** {zone_pos_str}\n"
        f"* **Current students:** {int(round(cy_ns)):,}\n"
        f"* **Staff:** {int(round(cy_sc)):,}\n"
        f"* **Sections:** {nos_val:,}\n"
        f"* **Class rooms:** {nocr_val:,}\n"
        f"* **Occupied rooms:** {noor_val:,}\n"
        f"* **Empty rooms:** {novr_val:,}"
    )

    # 2. Overall Branch Situation
    health_verdict = "🔴 **The branch dropout situation has become worse this year.**" if dpp_diff > 0 else "🟢 **The branch dropout situation has improved this year.**"
    sign_dp = "+" if dp_diff >= 0 else ""
    sign_dpp = "+" if dpp_diff >= 0 else ""
    sign_pct = "+" if dp_pct_change >= 0 else ""

    sec2_content = (
        f"**{raw_branch_name} has {int(round(cy_dp)):,} dropouts this year, compared with {int(round(ly_dp)):,} last year. "
        f"These include {int(round(pp_dp_val)):,} Pre Primary, {int(round(ps_dp_val)):,} Primary School, and {int(round(hs_dp_val)):,} High School dropouts.**\n\n"
        f"* **Dropouts count:** {int(round(cy_dp)):,} → {int(round(ly_dp)):,} last year (change: {sign_dp}{int(round(dp_diff)):,} students / PP: {int(round(pp_dp_val)):,}, PS: {int(round(ps_dp_val)):,}, HS: {int(round(hs_dp_val)):,})\n"
        f"* **Dropout percentage:** {ly_dpp:.2f}% → {cy_dpp:.2f}% ({sign_dpp}{dpp_diff:.2f} percentage points / PP: {pp_ly_dpp:.2f}% → {pp_cy_dpp:.2f}%, PS: {ps_ly_dpp:.2f}% → {ps_cy_dpp:.2f}%, HS: {hs_ly_dpp:.2f}% → {hs_cy_dpp:.2f}%)\n"
        f"* **Total dropouts percentage change:** {sign_pct}{dp_pct_change:.2f}%\n\n"
        f"{health_verdict}"
    )

    # 3. Existing vs New Student Dropouts
    en_info = extract_existing_new_stats(df_branch)
    if en_info.get('available'):
        e_dp = en_info['e_dp']
        n_dp = en_info['n_dp']
        tot_dp = en_info['tot_dp']
        e_pct = en_info['e_pct']
        n_pct = en_info['n_pct']

        sec3_lines = [
            f"Of the branch's current-year dropouts ({int(round(tot_dp)):,} total):\n",
            f"* **Existing students:** {int(round(e_dp)):,} dropouts (**{e_pct:.1f}%**)",
            f"* **New students:** {int(round(n_dp)):,} dropouts (**{n_pct:.1f}%**)\n",
            "**By school level:**",
        ]
        for code, lvl in [('PP', 'Pre Primary'), ('PS', 'Primary School'), ('HS', 'High School')]:
            ld = en_info['levels'][code]
            sec3_lines.append(f"* **{lvl}:** Existing {int(round(ld['e_dp'])):,} ({ld['e_pct']:.1f}%), New {int(round(ld['n_dp'])):,} ({ld['n_pct']:.1f}%)")
        sec3_content = "\n".join(sec3_lines)
    else:
        sec3_content = "Existing vs New student dropout data is not available for this branch."

    # 4. Dropouts by School Level
    level_data = [
        {'level': 'Pre Primary', 'cy_dp': pp_dp_val, 'cy_ns': pp_ns_val, 'cy_dpp': pp_cy_dpp, 'ly_dpp': pp_ly_dpp, 'change': pp_cy_dpp - pp_ly_dpp},
        {'level': 'Primary School', 'cy_dp': ps_dp_val, 'cy_ns': ps_ns_val, 'cy_dpp': ps_cy_dpp, 'ly_dpp': ps_ly_dpp, 'change': ps_cy_dpp - ps_ly_dpp},
        {'level': 'High School', 'cy_dp': hs_dp_val, 'cy_ns': hs_ns_val, 'cy_dpp': hs_cy_dpp, 'ly_dpp': hs_ly_dpp, 'change': hs_cy_dpp - hs_ly_dpp},
    ]
    level_table_lines = [
        "| Level | Dropouts | Students | Dropout % | Last Year % | Change |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for l in level_data:
        chg = l['change']
        emoji = "🟢" if chg < -1e-6 else ("🔴" if chg > 1e-6 else "⚪")
        arrow = "↓ " if chg < -1e-6 else ("↑ " if chg > 1e-6 else "")
        chg_str = f"{arrow}{abs(chg):.2f}% {emoji}"
        level_table_lines.append(
            f"| {l['level']} | {int(round(l['cy_dp'])):,} | {int(round(l['cy_ns'])):,} | "
            f"{l['cy_dpp']:.2f}% | {l['ly_dpp']:.2f}% | {chg_str} |"
        )

    highest_dpp_lvl = max(level_data, key=lambda x: x['cy_dpp'])
    highest_count_lvl = max(level_data, key=lambda x: x['cy_dp'])

    sec4_summary = [
        f"\n\n**{highest_dpp_lvl['level']} has the highest dropout percentage at {highest_dpp_lvl['cy_dpp']:.2f}%.**",
        f"\n\n**{highest_count_lvl['level']} has the highest number of dropouts with {int(round(highest_count_lvl['cy_dp'])):,} students.**",
    ]
    sec4_content = "\n".join(level_table_lines) + "".join(sec4_summary)

    # 5. What Changed From Last Year?
    sec5_lines = [
        f"Compared with last year, the branch's dropout percentage {'increased' if dpp_diff >= 0 else 'improved'} by **{abs(dpp_diff):.2f} percentage points**.\n",
    ]
    for l in level_data:
        chg = l['change']
        action = "improved" if chg < 0 else "increased"
        sec5_lines.append(f"* **{l['level']}:** {action} by **{abs(chg):.2f} percentage points**")

    worsened_lvls = [l for l in level_data if l['change'] > 0]
    improved_lvls = [l for l in level_data if l['change'] < 0]

    biggest_inc_lvl = max(worsened_lvls, key=lambda x: x['change']) if worsened_lvls else None
    biggest_imp_lvl = min(improved_lvls, key=lambda x: x['change']) if improved_lvls else None

    sec5_lines.append("\n**Biggest increase**")
    if biggest_inc_lvl:
        sec5_lines.append(f"🔴 **{biggest_inc_lvl['level']}** had the biggest increase in dropout percentage: **+{biggest_inc_lvl['change']:.2f} percentage points**.")
    else:
        sec5_lines.append("No school level experienced an increase in dropout percentage.")

    sec5_lines.append("\n**Biggest improvement**")
    if biggest_imp_lvl:
        sec5_lines.append(f"🟢 **{biggest_imp_lvl['level']}** improved by **{biggest_imp_lvl['change']:.2f} percentage points**.")
    else:
        sec5_lines.append("No school level showed an improvement in dropout percentage.")

    sec5_content = "\n".join(sec5_lines)

    # 6. Position in the Zone
    diff_from_zone = cy_dpp - zone_dpp
    sign_zone_diff = "+" if diff_from_zone >= 0 else ""
    zone_comp_analysis = (
        f"**Analysis:** {raw_branch_name}'s dropout rate ({cy_dpp:.2f}%) is {'above' if cy_dpp >= 10.0 else 'below'} the 10% risk level, "
        f"and is {'higher' if diff_from_zone > 0 else 'lower'} than the {zone_name} zone average of {zone_dpp:.2f}%."
    )

    sec6_content = (
        f"### Position in {zone_name} Zone\n\n"
        f"{raw_branch_name} has a **{cy_dpp:.2f}% dropout rate**.\n\n"
        f"🔴 It is the **{ordinal_str(branch_pos_in_zone)} highest dropout branch among {n_zone_branches} branches in {zone_name} zone**.\n\n"
        f"* **Zone average dropout rate:** {zone_dpp:.2f}%\n"
        f"* **Branch dropout rate:** {cy_dpp:.2f}%\n"
        f"* **Difference from zone average:** {sign_zone_diff}{diff_from_zone:.2f} percentage points\n\n"
        f"{zone_comp_analysis}"
    )

    # 7. Branch Health
    sec7_content = (
        f"### Student & Staff\n"
        f"* **Total students:** {int(round(cy_ns)):,}\n"
        f"* **Staff count:** {int(round(cy_sc)):,}\n"
        f"* **Student-to-staff ratio:** {str_val:.2f}\n\n"
        f"### Infrastructure\n"
        f"* **Sections:** {nos_val:,}\n"
        f"* **Class rooms:** {nocr_val:,}\n"
        f"* **Occupied rooms:** {noor_val:,}\n"
        f"* **Empty rooms:** {novr_val:,}\n"
        f"* **Room occupancy:** {occupancy_pct:.2f}%\n\n"
        f"### Strength\n"
        f"* **Average students per section:** {sps_val:.2f}\n\n"
        f"The branch has **{int(round(cy_ns)):,} students and {int(round(cy_sc)):,} staff**, giving a student-to-staff ratio of **{str_val:.2f}**. "
        f"There are **{nos_val:,} sections and {nocr_val:,} classrooms**, with **{novr_val:,} empty classroom{'s' if novr_val != 1 else ''}**."
    )

    # 8. What Needs Attention
    sec8_bullets = []
    if cy_dpp >= 10.0:
        sec8_bullets.append(f"🔴 **Dropout:** Dropout percentage is **{cy_dpp:.2f}%**, which is above the 10% risk level.")
    else:
        sec8_bullets.append(f"🟢 **Dropout:** Dropout percentage is **{cy_dpp:.2f}%**, which is within the 10% risk level.")

    if dpp_diff > 0:
        sec8_bullets.append(f"🔴 **Increase:** Dropout percentage increased by **{dpp_diff:.2f} percentage points** from last year.")
    else:
        sec8_bullets.append(f"🟢 **Improvement:** Dropout percentage improved by **{abs(dpp_diff):.2f} percentage points** from last year.")

    sec8_bullets.append(f"🔴 **School Level:** **{highest_dpp_lvl['level']}** has the highest dropout percentage at **{highest_dpp_lvl['cy_dpp']:.2f}%**.")

    if biggest_imp_lvl:
        sec8_bullets.append(f"🟢 **Positive Point:** **{biggest_imp_lvl['level']} dropout decreased by {abs(biggest_imp_lvl['change']):.2f} percentage points**, showing improvement in that level.")

    sec8_content = "\n\n".join(sec8_bullets)

    # 9. Overall Conclusion
    need_verdict = "needs attention" if (cy_dpp >= 10.0 or dpp_diff > 0) else "is performing well"
    sec9_content = (
        f"### Overall\n\n"
        f"**{raw_branch_name} {need_verdict} this year.**\n\n"
        f"The branch has a **{cy_dpp:.2f}% dropout rate**, which is {'above' if cy_dpp >= 10.0 else 'below'} the 10% risk level, "
        f"and it has {'increased' if dpp_diff >= 0 else 'improved'} from **{ly_dpp:.2f}% last year**.\n\n"
        f"The main area to look at is **{highest_dpp_lvl['level']}**, which has the highest dropout percentage.\n\n"
        f"{'At the same time, the branch should continue the improvement seen in ' + biggest_imp_lvl['level'] + '.' if biggest_imp_lvl else ''}"
    )

    evidence_rows = [
        ['Dropouts', f"{int(round(cy_dp)):,}", f"{int(round(ly_dp)):,}", f"{'+' if dp_diff >= 0 else ''}{int(round(dp_diff)):,}", "🔴" if dp_diff > 0 else "🟢"],
        ['Dropout %', f"{cy_dpp:.2f}%", f"{ly_dpp:.2f}%", f"{'+' if dpp_diff >= 0 else ''}{dpp_diff:.2f} percentage points", "🔴" if dpp_diff > 0 else "🟢"],
        ['Net Strength', f"{int(round(cy_ns)):,}", f"{int(round(ly_ns)):,}", f"{'+' if cy_ns - ly_ns >= 0 else ''}{int(round(cy_ns - ly_ns)):,}", "🟢" if cy_ns >= ly_ns else "🔴"],
        ['Staff', f"{int(round(cy_sc)):,}", f"{int(round(ly_sc)):,}", f"{'+' if cy_sc - ly_sc >= 0 else ''}{int(round(cy_sc - ly_sc)):,}", "⚪"],
        ['Student/Staff Ratio', f"{str_val:.2f}", f"{ly_str_val:.2f}" if ly_str_val > 0 else "N/A", f"{'+' if str_val - ly_str_val >= 0 else ''}{str_val - ly_str_val:.2f}" if ly_str_val > 0 else "N/A", "🟢" if str_val <= 40 else "⚪"],
        ['Sections', f"{nos_val:,}", f"{ly_nos_val:,}", f"{'+' if nos_val - ly_nos_val >= 0 else ''}{nos_val - ly_nos_val:,}", "⚪"],
        ['Avg Strength/Section', f"{sps_val:.2f}", f"{ly_sps_val:.2f}", f"{'+' if sps_val - ly_sps_val >= 0 else ''}{sps_val - ly_sps_val:.2f}", "⚪"],
        ['Class Rooms', f"{nocr_val:,}", f"{ly_nocr_val:,}", f"{'+' if nocr_val - ly_nocr_val >= 0 else ''}{nocr_val - ly_nocr_val:,}", "⚪"],
        ['Occupied Rooms', f"{noor_val:,}", f"{ly_noor_val:,}", f"{'+' if noor_val - ly_noor_val >= 0 else ''}{noor_val - ly_noor_val:,}", "⚪"],
        ['Empty Rooms', f"{novr_val:,}", f"{ly_novr_val:,}", f"{'+' if novr_val - ly_novr_val >= 0 else ''}{novr_val - ly_novr_val:,}", "⚪"],
    ]

    sections = [
        {'title': '1. About This Branch', 'content': sec1_content},
        {'title': '2. Overall Branch Situation', 'content': sec2_content},
        {'title': '3. Existing vs New Student Dropouts', 'content': sec3_content},
        {'title': '4. Dropouts by School Level', 'content': sec4_content},
        {'title': '5. What Changed From Last Year?', 'content': sec5_content},
        {'title': '6. Position in the Zone', 'content': sec6_content},
        {'title': '7. Branch Health', 'content': sec7_content},
        {'title': '8. What Needs Attention', 'content': sec8_content},
        {'title': '9. Overall Conclusion', 'content': sec9_content},
    ]

    direct_answer = f"# Branch Statistics — {raw_branch_name}"
    headers = ['Metric', 'This Year', 'Last Year', 'Change', 'Status']

    return AnalysisResult(
        direct_answer=direct_answer,
        headers=headers,
        rows=evidence_rows,
        metric='CY-DPP',
        group_dimension='Branch',
        operation='analysis',
        sections=sections,
        evidence_title="Detailed Branch Data",
    )


def build_agm_fee_due_analysis(df: pd.DataFrame, agm_name: str, context: dict | None = None) -> AnalysisResult:
    display_agm_name = format_display_ri_name(agm_name)
    agm_df = df[df['AGM Name'] == agm_name]
    if agm_df.empty and 'AGM' in df.columns:
        agm_df = df[df['AGM'] == agm_name]

    n_zones = agm_df['Zone'].nunique() if 'Zone' in agm_df.columns else 0
    n_ris = agm_df['RI Name'].nunique() if 'RI Name' in agm_df.columns else 0
    n_branches = agm_df['Branch'].nunique() if 'Branch' in agm_df.columns else 0

    ly_fdc = float(agm_df['LY_FDC'].sum()) if 'LY_FDC' in agm_df.columns else 0.0
    ly_fd = float(agm_df['LY_FD'].sum()) if 'LY_FD' in agm_df.columns else 0.0
    cy_a_fdc = float(agm_df['CY_A_FDC'].sum()) if 'CY_A_FDC' in agm_df.columns else 0.0
    cy_a_fd = float(agm_df['CY_A_FD'].sum()) if 'CY_A_FD' in agm_df.columns else 0.0
    cy_a_zp = float(agm_df['CY_A_ZP'].sum()) if 'CY_A_ZP' in agm_df.columns else 0.0
    cy_zp = float(agm_df['CY_ZP'].sum()) if 'CY_ZP' in agm_df.columns else 0.0
    cy_zp_fd = float(agm_df['CY_ZP_FD'].sum()) if 'CY_ZP_FD' in agm_df.columns else 0.0
    cy_fp_bn = float(agm_df['CY_FP_BN'].sum()) if 'CY_FP_BN' in agm_df.columns else 0.0
    cy_fn_bn = float(agm_df['CY_FN_BN'].sum()) if 'CY_FN_BN' in agm_df.columns else 0.0

    # 1. About This AGM
    sec1_content = (
        f"* **AGM:** {display_agm_name}\n"
        f"* **Number of Zones:** {n_zones}\n"
        f"* **Number of RIs:** {n_ris}\n"
        f"* **Number of Branches:** {n_branches}"
    )

    # 2. Last Year Fee Due
    sec2_content = f"Last year, {format_compact_count(ly_fdc)} students had fee due, with a total pending amount of {format_compact_currency(ly_fd)}."

    # 3. Current Year
    zp_wording = "none" if int(round(cy_a_zp)) == 0 else format_compact_count(cy_a_zp)
    sec3_content = (
        f"Among the continuing students, {format_compact_count(cy_a_fdc)} had fee due for last year, "
        f"with {format_compact_currency(cy_a_fd)} pending, and {zp_wording} had zero payment for last year's fees.\n\n"
        f"In the current year, {format_compact_count(cy_zp)} students have not paid any fee, "
        f"with {format_compact_currency(cy_zp_fd)} still pending."
    )

    # 4. Books Status
    sec4_content = (
        f"Currently, {format_compact_count(cy_fp_bn)} students have paid fees but not purchased books, "
        f"while {format_compact_count(cy_fn_bn)} students have neither paid fees nor purchased books."
    )

    # 5. Zone Performance
    zone_rows = []
    zone_table_lines = [
        "| Zone | Continuing Students With Fee Due | Current Fee Due Amount | Current Year Zero-Paid Students | Current Year Zero-Paid Fee Due Balance |",
        "| :--- | ---: | ---: | ---: | ---: |",
    ]
    if 'Zone' in agm_df.columns:
        for z_name, z_group in agm_df.groupby('Zone'):
            z_fdc = float(z_group['CY_A_FDC'].sum())
            z_fd = float(z_group['CY_A_FD'].sum())
            z_zp = float(z_group['CY_ZP'].sum())
            z_zp_fd = float(z_group['CY_ZP_FD'].sum())
            zone_rows.append({'zone': z_name, 'fdc': z_fdc, 'fd': z_fd, 'zp': z_zp, 'zp_fd': z_zp_fd})
            zone_table_lines.append(f"| {z_name} | {format_compact_count(z_fdc)} | {format_compact_currency(z_fd)} | {format_compact_count(z_zp)} | {format_compact_currency(z_zp_fd)} |")

    top_zone = max(zone_rows, key=lambda x: x['fd']) if zone_rows else None
    sec5_note = f"\n\n**Among the Zones, {top_zone['zone']} has the highest fee due ({format_compact_currency(top_zone['fd'])}) and zero-paid fee balance ({format_compact_currency(top_zone['zp_fd'])}).**" if top_zone else ""
    sec5_content = "\n".join(zone_table_lines) + sec5_note

    # 6. RI Performance
    ri_rows = []
    ri_table_lines = [
        "| RI | Number of Branches | Continuing Students With Fee Due | Current Fee Due Amount | Current Year Zero-Paid Students | Current Year Zero-Paid Fee Due Balance |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    if 'RI Name' in agm_df.columns:
        for r_raw, r_group in agm_df.groupby('RI Name'):
            r_disp = format_display_ri_name(r_raw)
            r_n_branches = r_group['Branch'].nunique() if 'Branch' in r_group.columns else 0
            r_fdc = float(r_group['CY_A_FDC'].sum())
            r_fd = float(r_group['CY_A_FD'].sum())
            r_zp = float(r_group['CY_ZP'].sum())
            r_zp_fd = float(r_group['CY_ZP_FD'].sum())
            ri_rows.append({'ri': r_disp, 'n_branches': r_n_branches, 'fdc': r_fdc, 'fd': r_fd, 'zp': r_zp, 'zp_fd': r_zp_fd})
            ri_table_lines.append(f"| {r_disp} | {r_n_branches} | {format_compact_count(r_fdc)} | {format_compact_currency(r_fd)} | {format_compact_count(r_zp)} | {format_compact_currency(r_zp_fd)} |")

    highest_fd_ri = max(ri_rows, key=lambda x: x['fd']) if ri_rows else None
    sec6_notes = []
    if highest_fd_ri:
        sec6_notes.append(f"\n\n**Among the RIs, RI {highest_fd_ri['ri']} has the highest fee due ({format_compact_currency(highest_fd_ri['fd'])}) and zero-paid fee balance ({format_compact_currency(highest_fd_ri['zp_fd'])}).**")
    sec6_content = "\n".join(ri_table_lines) + "".join(sec6_notes)

    # 7. Branches Needing Attention
    branch_rows = []
    for _, r in agm_df.iterrows():
        branch_rows.append({
            'branch': str(r['Branch']),
            'fd': float(r['CY_A_FD']),
            'zp_fd': float(r['CY_ZP_FD']),
            'zp': float(r['CY_ZP']),
            'fn_bn': float(r['CY_FN_BN']),
        })

    top_fd_b = max(branch_rows, key=lambda x: x['fd']) if branch_rows else None
    top_zp_fd_b = max(branch_rows, key=lambda x: x['zp_fd']) if branch_rows else None
    top_zp_b = max(branch_rows, key=lambda x: x['zp']) if branch_rows else None
    top_fn_bn_b = max(branch_rows, key=lambda x: x['fn_bn']) if branch_rows else None

    sec7_bullets = []
    if top_fd_b:
        sec7_bullets.append(f"* **Highest fee due:** **{top_fd_b['branch']}** — {format_compact_currency(top_fd_b['fd'])}")
    if top_zp_b:
        sec7_bullets.append(f"* **Highest zero-paid students:** **{top_zp_b['branch']}** — {format_compact_count(top_zp_b['zp'])} students")
    if top_zp_fd_b:
        sec7_bullets.append(f"* **Highest zero-paid fee due:** **{top_zp_fd_b['branch']}** — {format_compact_currency(top_zp_fd_b['zp_fd'])}")
    if top_fn_bn_b:
        sec7_bullets.append(f"* **Highest fee-not-paid and books-not-purchased:** **{top_fn_bn_b['branch']}** — {format_compact_count(top_fn_bn_b['fn_bn'])} students")
    sec7_content = "\n".join(sec7_bullets)

    # 8. Conclusion
    top_zone_str = top_zone['zone'] if top_zone else ""
    top_ri_str = highest_fd_ri['ri'] if highest_fd_ri else ""
    top_b_str = top_fd_b['branch'] if top_fd_b else ""
    sec8_content = (
        f"AGM {display_agm_name} has **{format_compact_currency(cy_a_fd)}** in fee due across **{format_compact_count(cy_a_fdc)} continuing students**.\n\n"
        f"**{format_compact_count(cy_zp)} students** are zero-paid, with **{format_compact_currency(cy_zp_fd)}** pending. "
        f"Zone **{top_zone_str}**, RI **{top_ri_str}**, and branch **{top_b_str}** require primary review."
    )

    evidence_rows = []
    for _, r in agm_df.iterrows():
        evidence_rows.append([
            str(r['Branch']),
            format_compact_count(r['CY_A_FDC']),
            format_compact_currency(r['CY_A_FD']),
            format_compact_count(r['CY_ZP']),
            format_compact_currency(r['CY_ZP_FD']),
            format_compact_count(r['CY_FN_BN']),
        ])

    sections = [
        {'title': '1. About This AGM', 'content': sec1_content},
        {'title': '2. Last Year Fee Due', 'content': sec2_content},
        {'title': '3. Current Year', 'content': sec3_content},
        {'title': '4. Books Status', 'content': sec4_content},
        {'title': '5. Zone Performance', 'content': sec5_content},
        {'title': '6. RI Performance', 'content': sec6_content},
        {'title': '7. Branches Needing Attention', 'content': sec7_content},
        {'title': '8. Conclusion', 'content': sec8_content},
    ]

    return AnalysisResult(
        direct_answer=f"# AGM Fee Due Statistics — {display_agm_name}",
        headers=['Branch', 'Last Year Continuing Students With Fee Due', 'Last Year Students with Current Fee Due Amount', 'Current Year Zero-Paid Students', 'Current Year Zero-Paid Fee Due Balance', 'Fee Not Paid & Books Not Purchased'],
        rows=evidence_rows,
        metric='CY_A_FD',
        group_dimension='AGM',
        operation='analysis',
        sections=sections,
        evidence_title="Detailed Branch Fee Due Data",
    )


def build_ri_fee_due_analysis(df: pd.DataFrame, ri_name: str, context: dict | None = None) -> AnalysisResult:
    display_ri_name = format_display_ri_name(ri_name)
    ri_df = df[df['RI Name'] == ri_name]
    if ri_df.empty and 'RI' in df.columns:
        ri_df = df[df['RI'] == ri_name]

    zone_str = str(ri_df['Zone'].iloc[0]) if not ri_df.empty and 'Zone' in ri_df.columns else ""
    n_branches = ri_df['Branch'].nunique() if 'Branch' in ri_df.columns else 0

    ly_fdc = float(ri_df['LY_FDC'].sum()) if 'LY_FDC' in ri_df.columns else 0.0
    ly_fd = float(ri_df['LY_FD'].sum()) if 'LY_FD' in ri_df.columns else 0.0
    cy_a_fdc = float(ri_df['CY_A_FDC'].sum()) if 'CY_A_FDC' in ri_df.columns else 0.0
    cy_a_fd = float(ri_df['CY_A_FD'].sum()) if 'CY_A_FD' in ri_df.columns else 0.0
    cy_a_zp = float(ri_df['CY_A_ZP'].sum()) if 'CY_A_ZP' in ri_df.columns else 0.0
    cy_zp = float(ri_df['CY_ZP'].sum()) if 'CY_ZP' in ri_df.columns else 0.0
    cy_zp_fd = float(ri_df['CY_ZP_FD'].sum()) if 'CY_ZP_FD' in ri_df.columns else 0.0
    cy_fp_bn = float(ri_df['CY_FP_BN'].sum()) if 'CY_FP_BN' in ri_df.columns else 0.0
    cy_fn_bn = float(ri_df['CY_FN_BN'].sum()) if 'CY_FN_BN' in ri_df.columns else 0.0

    # 1. About This RI
    sec1_content = (
        f"* **RI:** {display_ri_name}\n"
        f"* **Zone:** {zone_str}\n"
        f"* **Number of Branches:** {n_branches}"
    )

    # 2. Last Year Fee Due
    sec2_content = f"Last year, {format_compact_count(ly_fdc)} students had fee due, with a total pending amount of {format_compact_currency(ly_fd)}."

    # 3. Current Year
    zp_wording = "none" if int(round(cy_a_zp)) == 0 else format_compact_count(cy_a_zp)
    sec3_content = (
        f"Among the continuing students, {format_compact_count(cy_a_fdc)} had fee due for last year, "
        f"with {format_compact_currency(cy_a_fd)} pending, and {zp_wording} had zero payment for last year's fees.\n\n"
        f"In the current year, {format_compact_count(cy_zp)} students have not paid any fee, "
        f"with {format_compact_currency(cy_zp_fd)} still pending."
    )

    # 4. Books Status
    sec4_content = (
        f"Currently, {format_compact_count(cy_fp_bn)} students have paid fees but not purchased books, "
        f"while {format_compact_count(cy_fn_bn)} students have neither paid fees nor purchased books."
    )

    # 5. Branches Needing Attention (Branch Performance summary table completely removed!)
    branch_rows = []
    for _, r in ri_df.iterrows():
        branch_rows.append({
            'branch': str(r['Branch']),
            'fd': float(r['CY_A_FD']),
            'zp_fd': float(r['CY_ZP_FD']),
            'zp': float(r['CY_ZP']),
            'fn_bn': float(r['CY_FN_BN']),
        })

    top_fd_b = max(branch_rows, key=lambda x: x['fd']) if branch_rows else None
    top_zp_fd_b = max(branch_rows, key=lambda x: x['zp_fd']) if branch_rows else None
    top_zp_b = max(branch_rows, key=lambda x: x['zp']) if branch_rows else None
    top_fn_bn_b = max(branch_rows, key=lambda x: x['fn_bn']) if branch_rows else None

    sec5_bullets = []
    if top_fd_b:
        sec5_bullets.append(f"* **Highest fee due:** **{top_fd_b['branch']}** — {format_compact_currency(top_fd_b['fd'])}")
    if top_zp_b:
        sec5_bullets.append(f"* **Highest zero-paid students:** **{top_zp_b['branch']}** — {format_compact_count(top_zp_b['zp'])} students")
    if top_zp_fd_b:
        sec5_bullets.append(f"* **Highest zero-paid fee due:** **{top_zp_fd_b['branch']}** — {format_compact_currency(top_zp_fd_b['zp_fd'])}")
    if top_fn_bn_b:
        sec5_bullets.append(f"* **Highest fee-not-paid and books-not-purchased:** **{top_fn_bn_b['branch']}** — {format_compact_count(top_fn_bn_b['fn_bn'])} students")
    sec5_content = "\n".join(sec5_bullets)

    # 6. Conclusion
    first_b_name = top_fd_b['branch'] if top_fd_b else "high fee due branches"
    sec6_content = (
        f"RI {display_ri_name} has **{format_compact_currency(cy_a_fd)}** in current fee due across **{n_branches} branches**.\n\n"
        f"**{format_compact_count(cy_zp)} students** are zero-paid with **{format_compact_currency(cy_zp_fd)}** pending. "
        f"Branch **{first_b_name}** should be prioritized for review."
    )

    evidence_rows = []
    for _, r in ri_df.iterrows():
        evidence_rows.append([
            str(r['Branch']),
            format_compact_count(r['CY_A_FDC']),
            format_compact_currency(r['CY_A_FD']),
            format_compact_count(r['CY_ZP']),
            format_compact_currency(r['CY_ZP_FD']),
            format_compact_count(r['CY_FN_BN']),
        ])

    sections = [
        {'title': '1. About This RI', 'content': sec1_content},
        {'title': '2. Last Year Fee Due', 'content': sec2_content},
        {'title': '3. Current Year', 'content': sec3_content},
        {'title': '4. Books Status', 'content': sec4_content},
        {'title': '5. Branches Needing Attention', 'content': sec5_content},
        {'title': '6. Conclusion', 'content': sec6_content},
    ]

    return AnalysisResult(
        direct_answer=f"# RI Fee Due Statistics — {display_ri_name}",
        headers=['Branch', 'Last Year Continuing Students With Fee Due', 'Last Year Students with Current Fee Due Amount', 'Current Year Zero-Paid Students', 'Current Year Zero-Paid Fee Due Balance', 'Fee Not Paid & Books Not Purchased'],
        rows=evidence_rows,
        metric='CY_A_FD',
        group_dimension='RI',
        operation='analysis',
        sections=sections,
        evidence_title="Detailed Branch Fee Due Data",
    )


def build_branch_fee_due_analysis(df: pd.DataFrame, branch_name: str, context: dict | None = None) -> AnalysisResult:
    b_df = df[df['Branch'] == branch_name]
    if b_df.empty:
        raw_branch_name = branch_name
        agm_name = "N/A"
        ri_name = "N/A"
        zone_name = "N/A"
        ly_fdc = ly_fd = cy_a_fdc = cy_a_fd = cy_a_zp = cy_zp = cy_zp_fd = cy_fp_bn = cy_fn_bn = 0.0
    else:
        raw_branch_name = branch_name
        r0 = b_df.iloc[0]
        agm_name = format_display_ri_name(r0.get('AGM Name') or r0.get('AGM') or '')
        ri_name = format_display_ri_name(r0.get('RI Name') or r0.get('RI') or '')
        zone_name = str(r0.get('Zone', ''))
        ly_fdc = float(r0.get('LY_FDC', 0))
        ly_fd = float(r0.get('LY_FD', 0))
        cy_a_fdc = float(r0.get('CY_A_FDC', 0))
        cy_a_fd = float(r0.get('CY_A_FD', 0))
        cy_a_zp = float(r0.get('CY_A_ZP', 0))
        cy_zp = float(r0.get('CY_ZP', 0))
        cy_zp_fd = float(r0.get('CY_ZP_FD', 0))
        cy_fp_bn = float(r0.get('CY_FP_BN', 0))
        cy_fn_bn = float(r0.get('CY_FN_BN', 0))

    # 1. About This Branch
    sec1_content = (
        f"* **Branch:** {raw_branch_name}\n"
        f"* **AGM:** {agm_name}\n"
        f"* **RI:** {ri_name}\n"
        f"* **Zone:** {zone_name}"
    )

    # 2. Last Year Fee Due
    sec2_content = f"Last year, {format_compact_count(ly_fdc)} students had fee due, with a total pending amount of {format_compact_currency(ly_fd)}."

    # 3. Current Year
    zp_wording = "none" if int(round(cy_a_zp)) == 0 else format_compact_count(cy_a_zp)
    sec3_content = (
        f"Among the continuing students, {format_compact_count(cy_a_fdc)} had fee due for last year, "
        f"with {format_compact_currency(cy_a_fd)} pending, and {zp_wording} had zero payment for last year's fees.\n\n"
        f"In the current year, {format_compact_count(cy_zp)} students have not paid any fee, "
        f"with {format_compact_currency(cy_zp_fd)} still pending."
    )

    # 4. Books Status
    sec4_content = (
        f"Currently, {format_compact_count(cy_fp_bn)} students have paid fees but not purchased books, "
        f"while {format_compact_count(cy_fn_bn)} students have neither paid fees nor purchased books."
    )

    # 5. Conclusion
    sec5_content = (
        f"**{raw_branch_name}** has **{format_compact_currency(cy_a_fd)}** in current fee due across **{format_compact_count(cy_a_fdc)} continuing students**.\n\n"
        f"**{format_compact_count(cy_zp)} students** are zero-paid with **{format_compact_currency(cy_zp_fd)}** pending."
    )

    sections = [
        {'title': '1. About This Branch', 'content': sec1_content},
        {'title': '2. Last Year Fee Due', 'content': sec2_content},
        {'title': '3. Current Year', 'content': sec3_content},
        {'title': '4. Books Status', 'content': sec4_content},
        {'title': '5. Conclusion', 'content': sec5_content},
    ]

    evidence_rows = [
        ['Last Year Fee Due Students', format_compact_count(ly_fdc)],
        ['Last Year Fee Due Amount', format_compact_currency(ly_fd)],
        ['Last Year Continuing Students With Fee Due', format_compact_count(cy_a_fdc)],
        ['Last Year Students with Current Fee Due Amount', format_compact_currency(cy_a_fd)],
        ['Last Year Continuing Students with Zero Payment for Last Year’s Fees', format_compact_count(cy_a_zp)],
        ['Current Year Zero-Paid Students', format_compact_count(cy_zp)],
        ['Current Year Zero-Paid Fee Due Balance', format_compact_currency(cy_zp_fd)],
        ['Fee Paid But Books Not Purchased', format_compact_count(cy_fp_bn)],
        ['Fee Not Paid & Books Not Purchased', format_compact_count(cy_fn_bn)],
    ]

    return AnalysisResult(
        direct_answer=f"# Branch Fee Due Statistics — {raw_branch_name}",
        headers=['Metric', 'Value'],
        rows=evidence_rows,
        metric='CY_A_FD',
        group_dimension='Branch',
        operation='analysis',
        sections=sections,
        evidence_title="Detailed Branch Fee Due Data",
    )


def _get_percentage_fraction_wording(sal_pct: float) -> tuple[str, str]:
    if sal_pct <= 25:
        return "one-quarter", "three-quarters"
    elif sal_pct <= 35:
        return "one-third", "two-thirds"
    elif sal_pct <= 45:
        return "nearly half", "over half"
    elif sal_pct <= 55:
        return "about half", "about half"
    else:
        return "more than half", "less than half"


def build_agm_revenue_salary_analysis(df: pd.DataFrame, agm_name: str, context: dict | None = None) -> AnalysisResult:
    display_agm_name = format_display_ri_name(agm_name)
    if agm_name == 'All':
        agm_df = df
    else:
        agm_df = df[df['AGM Name'] == agm_name]
        if agm_df.empty and 'AGM' in df.columns:
            agm_df = df[df['AGM'] == agm_name]

    n_zones = agm_df['Zone'].nunique() if 'Zone' in agm_df.columns else 0
    ri_col = 'RI Name' if 'RI Name' in agm_df.columns else ('RI' if 'RI' in agm_df.columns else None)
    n_ris = agm_df[ri_col].nunique() if ri_col else 0
    n_branches = agm_df['Branch'].nunique() if 'Branch' in agm_df.columns else 0

    tot_rev = float(agm_df['TOT_REV_N'].sum()) if 'TOT_REV_N' in agm_df.columns else 0.0
    tot_sal = float(agm_df['TOT_SAL'].sum()) if 'TOT_SAL' in agm_df.columns else 0.0
    surplus = tot_rev - tot_sal
    tot_ns = float(agm_df['TOT_NS'].sum()) if 'TOT_NS' in agm_df.columns else 0.0
    tot_sc = float(agm_df['TOT_SC'].sum()) if 'TOT_SC' in agm_df.columns else 0.0

    sal_v_rev_pct = (tot_sal / tot_rev * 100) if tot_rev > 0 else 0.0
    surplus_pct = 100.0 - sal_v_rev_pct if tot_rev > 0 else 0.0
    fee_avg = (tot_rev / tot_ns) if tot_ns > 0 else 0.0
    cost_per_stu = (tot_sal / tot_ns) if tot_ns > 0 else 0.0
    str_ratio = (tot_ns / tot_sc) if tot_sc > 0 else 0.0

    sal_frac, surplus_frac = _get_percentage_fraction_wording(sal_v_rev_pct)

    # 1. About This AGM
    sec1_content = (
        f"* **AGM:** {display_agm_name}\n"
        f"* **Number of Zones:** {n_zones}\n"
        f"* **Number of RIs:** {n_ris}\n"
        f"* **Number of Branches:** {n_branches}"
    )

    # 2. Overall Financial Summary (Percentage-First)
    sec2_content = (
        f"Across {n_branches} branches, salary costs were **{sal_v_rev_pct:.2f}%** of total revenue.\n\n"
        f"The average fee per student is {format_compact_currency(fee_avg)}, with an employee cost of {format_compact_currency(cost_per_stu)} per student "
        f"and an overall student-teacher ratio of {str_ratio:.2f}."
    )

    # 3. Segment Breakdown (Percentage-First: LPS + UPS combined into PS)
    pp_rev = float(agm_df['PP_REV_N'].sum()) if 'PP_REV_N' in agm_df.columns else 0.0
    lps_rev = float(agm_df['LPS_REV_N'].sum()) if 'LPS_REV_N' in agm_df.columns else 0.0
    ups_rev = float(agm_df['UPS_REV_N'].sum()) if 'UPS_REV_N' in agm_df.columns else 0.0
    hs_rev = float(agm_df['HS_REV_N'].sum()) if 'HS_REV_N' in agm_df.columns else 0.0

    pp_sal = float(agm_df['PP_SAL'].sum()) if 'PP_SAL' in agm_df.columns else 0.0
    lps_sal = float(agm_df['LPS_SAL'].sum()) if 'LPS_SAL' in agm_df.columns else 0.0
    ups_sal = float(agm_df['UPS_SAL'].sum()) if 'UPS_SAL' in agm_df.columns else 0.0
    hs_sal = float(agm_df['HS_SAL'].sum()) if 'HS_SAL' in agm_df.columns else 0.0

    ps_rev = lps_rev + ups_rev
    ps_sal = lps_sal + ups_sal

    pp_pct = (pp_sal / pp_rev * 100) if pp_rev > 0 else 0.0
    ps_pct = (ps_sal / ps_rev * 100) if ps_rev > 0 else 0.0
    hs_pct = (hs_sal / hs_rev * 100) if hs_rev > 0 else 0.0

    sec3_content = (
        f"* **Pre Primary (PP):** Salary burden is **{pp_pct:.2f}%** of segment revenue\n"
        f"* **Primary School (PS):** Salary burden is **{ps_pct:.2f}%** of segment revenue\n"
        f"* **High School (HS):** Salary burden is **{hs_pct:.2f}%** of segment revenue"
    )

    # 4. Zone Performance (Percentage-First)
    zone_rows = []
    zone_table_lines = [
        "| Zone | Salary vs Revenue % | Surplus % | Student-Teacher Ratio | Fee Average |",
        "| :--- | ---: | ---: | ---: | ---: |",
    ]
    if 'Zone' in agm_df.columns:
        for z_name, z_group in agm_df.groupby('Zone'):
            z_rev = float(z_group['TOT_REV_N'].sum())
            z_sal = float(z_group['TOT_SAL'].sum())
            z_ns = float(z_group['TOT_NS'].sum()) if 'TOT_NS' in z_group.columns else 0.0
            z_sc = float(z_group['TOT_SC'].sum()) if 'TOT_SC' in z_group.columns else 0.0
            z_sal_v_rev = (z_sal / z_rev * 100) if z_rev > 0 else 0.0
            z_surplus_pct = 100.0 - z_sal_v_rev if z_rev > 0 else 0.0
            z_str = (z_ns / z_sc) if z_sc > 0 else 0.0
            z_fa = (z_rev / z_ns) if z_ns > 0 else 0.0
            zone_rows.append({'zone': z_name, 'sal_v_rev': z_sal_v_rev, 'surplus_pct': z_surplus_pct, 'str': z_str, 'fa': z_fa})
            zone_table_lines.append(f"| {z_name} | {z_sal_v_rev:.2f}% | {z_surplus_pct:.2f}% | {z_str:.2f} | {format_compact_currency(z_fa)} |")

    top_zone = min(zone_rows, key=lambda x: x['sal_v_rev']) if zone_rows else None
    sec4_note = f"\n\n**Among the Zones, {top_zone['zone']} achieved the lowest salary burden at {top_zone['sal_v_rev']:.2f}% of revenue.**" if top_zone else ""
    sec4_content = "\n".join(zone_table_lines) + sec4_note

    # 5. RI Performance (Percentage-First)
    ri_rows = []
    ri_table_lines = [
        "| RI | Number of Branches | Salary vs Revenue % | Surplus % | Student-Teacher Ratio | Fee Average |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    if ri_col and ri_col in agm_df.columns:
        for r_raw, r_group in agm_df.groupby(ri_col):
            r_disp = format_display_ri_name(r_raw)
            r_n_b = r_group['Branch'].nunique() if 'Branch' in r_group.columns else 0
            r_rev = float(r_group['TOT_REV_N'].sum())
            r_sal = float(r_group['TOT_SAL'].sum())
            r_ns = float(r_group['TOT_NS'].sum()) if 'TOT_NS' in r_group.columns else 0.0
            r_sc = float(r_group['TOT_SC'].sum()) if 'TOT_SC' in r_group.columns else 0.0
            r_sal_v_rev = (r_sal / r_rev * 100) if r_rev > 0 else 0.0
            r_surplus_pct = 100.0 - r_sal_v_rev if r_rev > 0 else 0.0
            r_str = (r_ns / r_sc) if r_sc > 0 else 0.0
            r_fa = (r_rev / r_ns) if r_ns > 0 else 0.0
            ri_rows.append({'ri': r_disp, 'n_branches': r_n_b, 'sal_v_rev': r_sal_v_rev, 'surplus_pct': r_surplus_pct, 'str': r_str, 'fa': r_fa})
            ri_table_lines.append(f"| {r_disp} | {r_n_b} | {r_sal_v_rev:.2f}% | {r_surplus_pct:.2f}% | {r_str:.2f} | {format_compact_currency(r_fa)} |")

    top_ri = min(ri_rows, key=lambda x: x['sal_v_rev']) if ri_rows else None
    sec5_note = f"\n\n**Among the RIs, RI {top_ri['ri']} maintained the lowest salary burden at {top_ri['sal_v_rev']:.2f}% of revenue across {top_ri['n_branches']} branches.**" if top_ri else ""
    sec5_content = "\n".join(ri_table_lines) + sec5_note

    # 6. Branches Needing Attention (Percentage-First)
    b_list = []
    for _, r in agm_df.iterrows():
        r_rev = float(r.get('TOT_REV_N', 0))
        r_sal = float(r.get('TOT_SAL', 0))
        r_ns = float(r.get('TOT_NS', 0))
        r_pct = (r_sal / r_rev * 100) if r_rev > 0 else 0.0
        r_cs = (r_sal / r_ns) if r_ns > 0 else 0.0
        b_list.append({
            'branch': str(r['Branch']),
            'sal_v_rev': r_pct,
            'cs': r_cs,
        })

    lowest_sal_pct_b = min(b_list, key=lambda x: x['sal_v_rev']) if b_list else None
    highest_sal_pct_b = max(b_list, key=lambda x: x['sal_v_rev']) if b_list else None
    highest_cs_b = max(b_list, key=lambda x: x['cs']) if b_list else None

    sec6_bullets = []
    if lowest_sal_pct_b:
        sec6_bullets.append(f"* **Lowest Salary Burden:** **{lowest_sal_pct_b['branch']}** — **{lowest_sal_pct_b['sal_v_rev']:.2f}%** of revenue")
    if highest_sal_pct_b:
        rounded_high_pct = int(round(highest_sal_pct_b['sal_v_rev']))
        sec6_bullets.append(f"* **Highest Salary Burden:** **{highest_sal_pct_b['branch']}** — **{highest_sal_pct_b['sal_v_rev']:.2f}%** of revenue")
    if highest_cs_b:
        sec6_bullets.append(f"* **Highest Employee Cost per Student:** **{highest_cs_b['branch']}** — {format_compact_currency(highest_cs_b['cs'])} per student")
    sec6_content = "\n".join(sec6_bullets)

    # 7. Conclusion (Percentage-First)
    top_z_str = top_zone['zone'] if top_zone else "N/A"
    top_r_str = top_ri['ri'] if top_ri else "N/A"
    highest_sal_branch_str = highest_sal_pct_b['branch'] if highest_sal_pct_b else 'N/A'
    highest_sal_pct_str = f"{highest_sal_pct_b['sal_v_rev']:.2f}%" if highest_sal_pct_b else 'N/A'
    sec7_content = (
        f"AGM {display_agm_name} operates with an overall salary burden of **{sal_v_rev_pct:.2f}%** of total revenue.\n\n"
        f"Zone **{top_z_str}** and RI **{top_r_str}** maintain the strongest operational efficiency. "
        f"Branch **{highest_sal_branch_str}** ({highest_sal_pct_str} salary ratio) should be prioritized for staff cost review."
    )

    evidence_rows = []
    for _, r in agm_df.iterrows():
        r_rev = float(r.get('TOT_REV_N', 0))
        r_sal = float(r.get('TOT_SAL', 0))
        r_surplus = r_rev - r_sal
        r_ns = float(r.get('TOT_NS', 0))
        r_sc = float(r.get('TOT_SC', 0))
        r_pct = (r_sal / r_rev * 100) if r_rev > 0 else 0.0
        r_fa = (r_rev / r_ns) if r_ns > 0 else 0.0
        r_cs = (r_sal / r_ns) if r_ns > 0 else 0.0
        r_str = (r_ns / r_sc) if r_sc > 0 else 0.0
        evidence_rows.append([
            str(r['Branch']),
            format_compact_currency(r_rev),
            format_compact_currency(r_sal),
            format_compact_currency(r_surplus),
            f"{r_pct:.2f}%",
            format_compact_currency(r_fa),
            format_compact_currency(r_cs),
            f"{r_str:.2f}",
        ])

    sections = [
        {'title': '1. About This AGM', 'content': sec1_content},
        {'title': '2. Overall Financial Summary', 'content': sec2_content},
        {'title': '3. Segment Breakdown', 'content': sec3_content},
        {'title': '4. Zone Performance', 'content': sec4_content},
        {'title': '5. RI Performance', 'content': sec5_content},
        {'title': '6. Branches Needing Attention', 'content': sec6_content},
        {'title': '7. Conclusion', 'content': sec7_content},
    ]

    return AnalysisResult(
        direct_answer=f"# AGM Revenue vs Salary Statistics — {display_agm_name}",
        headers=['Branch', 'Net Revenue', 'Salary Cost', 'Surplus', 'Salary vs Revenue %', 'Fee Average', 'Cost per Student', 'Student Teacher Ratio'],
        rows=evidence_rows,
        metric='TOT_REV_N',
        group_dimension='AGM',
        operation='analysis',
        sections=sections,
        evidence_title="Detailed Branch Revenue vs Salary Data",
    )


def build_ri_revenue_salary_analysis(df: pd.DataFrame, ri_name: str, context: dict | None = None) -> AnalysisResult:
    display_ri_name = format_display_ri_name(ri_name)
    ri_col = 'RI Name' if 'RI Name' in df.columns else ('RI' if 'RI' in df.columns else None)
    if ri_name == 'All':
        ri_df = df
    else:
        ri_df = df[df[ri_col] == ri_name] if ri_col else df

    zone_str = str(ri_df['Zone'].iloc[0]) if not ri_df.empty and 'Zone' in ri_df.columns else "N/A"
    n_branches = ri_df['Branch'].nunique() if 'Branch' in ri_df.columns else 0

    tot_rev = float(ri_df['TOT_REV_N'].sum()) if 'TOT_REV_N' in ri_df.columns else 0.0
    tot_sal = float(ri_df['TOT_SAL'].sum()) if 'TOT_SAL' in ri_df.columns else 0.0
    surplus = tot_rev - tot_sal
    tot_ns = float(ri_df['TOT_NS'].sum()) if 'TOT_NS' in ri_df.columns else 0.0
    tot_sc = float(ri_df['TOT_SC'].sum()) if 'TOT_SC' in ri_df.columns else 0.0

    sal_v_rev_pct = (tot_sal / tot_rev * 100) if tot_rev > 0 else 0.0
    surplus_pct = 100.0 - sal_v_rev_pct if tot_rev > 0 else 0.0
    fee_avg = (tot_rev / tot_ns) if tot_ns > 0 else 0.0
    cost_per_stu = (tot_sal / tot_ns) if tot_ns > 0 else 0.0
    str_ratio = (tot_ns / tot_sc) if tot_sc > 0 else 0.0

    sal_frac, surplus_frac = _get_percentage_fraction_wording(sal_v_rev_pct)

    # 1. About This RI
    sec1_content = (
        f"* **RI:** {display_ri_name}\n"
        f"* **Zone:** {zone_str}\n"
        f"* **Number of Branches:** {n_branches}"
    )

    # 2. Overall Financial Summary (Percentage-First)
    sec2_content = (
        f"Across {n_branches} branches in {zone_str} Zone, salary costs were **{sal_v_rev_pct:.2f}%** of total revenue.\n\n"
        f"The average fee per student stands at {format_compact_currency(fee_avg)}, with an employee cost of {format_compact_currency(cost_per_stu)} per student "
        f"and a student-teacher ratio of {str_ratio:.2f}."
    )

    # 3. Segment Breakdown (Percentage-First: LPS + UPS combined into PS)
    pp_rev = float(ri_df['PP_REV_N'].sum()) if 'PP_REV_N' in ri_df.columns else 0.0
    lps_rev = float(ri_df['LPS_REV_N'].sum()) if 'LPS_REV_N' in ri_df.columns else 0.0
    ups_rev = float(ri_df['UPS_REV_N'].sum()) if 'UPS_REV_N' in ri_df.columns else 0.0
    hs_rev = float(ri_df['HS_REV_N'].sum()) if 'HS_REV_N' in ri_df.columns else 0.0

    pp_sal = float(ri_df['PP_SAL'].sum()) if 'PP_SAL' in ri_df.columns else 0.0
    lps_sal = float(ri_df['LPS_SAL'].sum()) if 'LPS_SAL' in ri_df.columns else 0.0
    ups_sal = float(ri_df['UPS_SAL'].sum()) if 'UPS_SAL' in ri_df.columns else 0.0
    hs_sal = float(ri_df['HS_SAL'].sum()) if 'HS_SAL' in ri_df.columns else 0.0

    ps_rev = lps_rev + ups_rev
    ps_sal = lps_sal + ups_sal

    pp_pct = (pp_sal / pp_rev * 100) if pp_rev > 0 else 0.0
    ps_pct = (ps_sal / ps_rev * 100) if ps_rev > 0 else 0.0
    hs_pct = (hs_sal / hs_rev * 100) if hs_rev > 0 else 0.0

    sec3_content = (
        f"* **Pre Primary (PP):** Salary burden is **{pp_pct:.2f}%** of segment revenue\n"
        f"* **Primary School (PS):** Salary burden is **{ps_pct:.2f}%** of segment revenue\n"
        f"* **High School (HS):** Salary burden is **{hs_pct:.2f}%** of segment revenue"
    )

    # 4. Branches Needing Attention (Percentage-First, Branch Performance summary table removed!)
    b_list = []
    for _, r in ri_df.iterrows():
        r_rev = float(r.get('TOT_REV_N', 0))
        r_sal = float(r.get('TOT_SAL', 0))
        r_ns = float(r.get('TOT_NS', 0))
        r_pct = (r_sal / r_rev * 100) if r_rev > 0 else 0.0
        r_cs = (r_sal / r_ns) if r_ns > 0 else 0.0
        b_list.append({
            'branch': str(r['Branch']),
            'sal_v_rev': r_pct,
            'cs': r_cs,
        })

    lowest_sal_pct_b = min(b_list, key=lambda x: x['sal_v_rev']) if b_list else None
    highest_sal_pct_b = max(b_list, key=lambda x: x['sal_v_rev']) if b_list else None
    highest_cs_b = max(b_list, key=lambda x: x['cs']) if b_list else None

    sec4_bullets = []
    if lowest_sal_pct_b:
        sec4_bullets.append(f"* **Lowest Salary Burden:** **{lowest_sal_pct_b['branch']}** — **{lowest_sal_pct_b['sal_v_rev']:.2f}%** of revenue")
    if highest_sal_pct_b:
        rounded_high_pct = int(round(highest_sal_pct_b['sal_v_rev']))
        sec4_bullets.append(f"* **Highest Salary Burden:** **{highest_sal_pct_b['branch']}** — **{highest_sal_pct_b['sal_v_rev']:.2f}%** of revenue")
    if highest_cs_b:
        sec4_bullets.append(f"* **Highest Employee Cost per Student:** **{highest_cs_b['branch']}** — {format_compact_currency(highest_cs_b['cs'])} per student")
    sec4_content = "\n".join(sec4_bullets)

    # 5. Conclusion (Percentage-First)
    lowest_sal_branch = lowest_sal_pct_b['branch'] if lowest_sal_pct_b else 'N/A'
    highest_sal_branch = highest_sal_pct_b['branch'] if highest_sal_pct_b else 'N/A'
    highest_sal_val = f"{highest_sal_pct_b['sal_v_rev']:.2f}%" if highest_sal_pct_b else 'N/A'
    sec5_content = (
        f"RI {display_ri_name} maintains an overall salary burden of **{sal_v_rev_pct:.2f}%** across **{n_branches} branches**.\n\n"
        f"Branch **{lowest_sal_branch}** leads in operational efficiency, while **{highest_sal_branch}** ({highest_sal_val} salary burden) should be reviewed for cost optimization."
    )

    evidence_rows = []
    for _, r in ri_df.iterrows():
        r_rev = float(r.get('TOT_REV_N', 0))
        r_sal = float(r.get('TOT_SAL', 0))
        r_surplus = r_rev - r_sal
        r_ns = float(r.get('TOT_NS', 0))
        r_sc = float(r.get('TOT_SC', 0))
        r_pct = (r_sal / r_rev * 100) if r_rev > 0 else 0.0
        r_fa = (r_rev / r_ns) if r_ns > 0 else 0.0
        r_cs = (r_sal / r_ns) if r_ns > 0 else 0.0
        r_str = (r_ns / r_sc) if r_sc > 0 else 0.0
        evidence_rows.append([
            str(r['Branch']),
            format_compact_currency(r_rev),
            format_compact_currency(r_sal),
            format_compact_currency(r_surplus),
            f"{r_pct:.2f}%",
            format_compact_currency(r_fa),
            format_compact_currency(r_cs),
            f"{r_str:.2f}",
        ])

    sections = [
        {'title': '1. About This RI', 'content': sec1_content},
        {'title': '2. Overall Financial Summary', 'content': sec2_content},
        {'title': '3. Segment Breakdown', 'content': sec3_content},
        {'title': '4. Branches Needing Attention', 'content': sec4_content},
        {'title': '5. Conclusion', 'content': sec5_content},
    ]

    return AnalysisResult(
        direct_answer=f"# RI Revenue vs Salary Statistics — {display_ri_name}",
        headers=['Branch', 'Net Revenue', 'Salary Cost', 'Surplus', 'Salary vs Revenue %', 'Fee Average', 'Cost per Student', 'Student Teacher Ratio'],
        rows=evidence_rows,
        metric='TOT_REV_N',
        group_dimension='RI',
        operation='analysis',
        sections=sections,
        evidence_title="Detailed Branch Revenue vs Salary Data",
    )


def build_branch_revenue_salary_analysis(df: pd.DataFrame, branch_name: str, context: dict | None = None) -> AnalysisResult:
    b_df = df[df['Branch'] == branch_name]
    if b_df.empty:
        raw_branch_name = branch_name
        agm_name = "N/A"
        ri_name = "N/A"
        zone_name = "N/A"
        tot_rev = tot_sal = surplus = tot_ns = tot_sc = sal_v_rev_pct = fee_avg = cost_per_stu = str_ratio = 0.0
        pp_rev = pp_sal = lps_rev = lps_sal = ups_rev = ups_sal = hs_rev = hs_sal = 0.0
    else:
        raw_branch_name = branch_name
        r0 = b_df.iloc[0]
        agm_name = format_display_ri_name(r0.get('AGM Name') or r0.get('AGM') or '')
        ri_name = format_display_ri_name(r0.get('RI Name') or r0.get('RI') or '')
        zone_name = str(r0.get('Zone', ''))
        tot_rev = float(r0.get('TOT_REV_N', 0))
        tot_sal = float(r0.get('TOT_SAL', 0))
        surplus = tot_rev - tot_sal
        tot_ns = float(r0.get('TOT_NS', 0))
        tot_sc = float(r0.get('TOT_SC', 0))
        sal_v_rev_pct = float(r0.get('TOT_SAL_V_REV', (tot_sal / tot_rev * 100) if tot_rev > 0 else 0))
        fee_avg = float(r0.get('TOT_FA', (tot_rev / tot_ns) if tot_ns > 0 else 0))
        cost_per_stu = float(r0.get('TOT_CS', (tot_sal / tot_ns) if tot_ns > 0 else 0))
        str_ratio = float(r0.get('TOT_STR', (tot_ns / tot_sc) if tot_sc > 0 else 0))

        pp_rev = float(r0.get('PP_REV_N', 0))
        pp_sal = float(r0.get('PP_SAL', 0))
        lps_rev = float(r0.get('LPS_REV_N', 0))
        lps_sal = float(r0.get('LPS_SAL', 0))
        ups_rev = float(r0.get('UPS_REV_N', 0))
        ups_sal = float(r0.get('UPS_SAL', 0))
        hs_rev = float(r0.get('HS_REV_N', 0))
        hs_sal = float(r0.get('HS_SAL', 0))

    surplus_pct = 100.0 - sal_v_rev_pct if tot_rev > 0 else 0.0
    rounded_sal_pct = int(round(sal_v_rev_pct))

    ps_rev = lps_rev + ups_rev
    ps_sal = lps_sal + ups_sal

    pp_pct = (pp_sal / pp_rev * 100) if pp_rev > 0 else 0.0
    ps_pct = (ps_sal / ps_rev * 100) if ps_rev > 0 else 0.0
    hs_pct = (hs_sal / hs_rev * 100) if hs_rev > 0 else 0.0

    # 1. About This Branch
    sec1_content = (
        f"* **Branch:** {raw_branch_name}\n"
        f"* **AGM:** {agm_name}\n"
        f"* **RI:** {ri_name}\n"
        f"* **Zone:** {zone_name}"
    )

    # 2. Financial & Operational Overview (Percentage-First)
    sec2_content = (
        f"In **{raw_branch_name}**, employee salary costs accounted for **{sal_v_rev_pct:.2f}%** of total revenue.\n\n"
        f"The branch serves {format_compact_count(tot_ns)} students with {format_compact_count(tot_sc)} employees (student-teacher ratio of {str_ratio:.2f}), "
        f"achieving an average fee per student of {format_compact_currency(fee_avg)} and spending {format_compact_currency(cost_per_stu)} per student on employee costs."
    )

    # 3. Segment Breakdown (Percentage-First: LPS + UPS combined into PS)
    sec3_content = (
        f"* **Pre Primary (PP):** Salary burden is **{pp_pct:.2f}%** of segment revenue\n"
        f"* **Primary School (PS):** Salary burden is **{ps_pct:.2f}%** of segment revenue\n"
        f"* **High School (HS):** Salary burden is **{hs_pct:.2f}%** of segment revenue"
    )

    # 4. Conclusion (Percentage-First)
    sec4_content = (
        f"**{raw_branch_name}** operates with a salary burden of **{sal_v_rev_pct:.2f}%** of total revenue."
    )

    sections = [
        {'title': '1. About This Branch', 'content': sec1_content},
        {'title': '2. Financial & Operational Overview', 'content': sec2_content},
        {'title': '3. Segment Breakdown', 'content': sec3_content},
        {'title': '4. Conclusion', 'content': sec4_content},
    ]

    evidence_rows = [
        ['Total Net Revenue', format_compact_currency(tot_rev)],
        ['Total Employee Salary Cost', format_compact_currency(tot_sal)],
        ['Net Surplus', format_compact_currency(surplus)],
        ['Salary vs Revenue %', f"{sal_v_rev_pct:.2f}%"],
        ['Fee Average', format_compact_currency(fee_avg)],
        ['Cost per Student', format_compact_currency(cost_per_stu)],
        ['Student Teacher Ratio', f"{str_ratio:.2f}"],
        ['Total Student Count', format_compact_count(tot_ns)],
        ['Total Employee Count', format_compact_count(tot_sc)],
    ]

    return AnalysisResult(
        direct_answer=f"# Branch Revenue vs Salary Statistics — {raw_branch_name}",
        headers=['Metric', 'Value'],
        rows=evidence_rows,
        metric='TOT_REV_N',
        group_dimension='Branch',
        operation='analysis',
        sections=sections,
        evidence_title="Detailed Branch Revenue vs Salary Data",
    )


def build_agm_teacher_student_ratio_analysis(df: pd.DataFrame, agm_name: str, context: dict | None = None) -> AnalysisResult:
    display_agm_name = format_display_ri_name(agm_name)
    if agm_name == 'All':
        agm_df = df
    else:
        agm_df = df[df['AGM Name'] == agm_name]
        if agm_df.empty and 'AGM' in df.columns:
            agm_df = df[df['AGM'] == agm_name]

    n_zones = agm_df['Zone'].nunique() if 'Zone' in agm_df.columns else 0
    ri_col = 'RI Name' if 'RI Name' in agm_df.columns else ('RI' if 'RI' in agm_df.columns else None)
    n_ris = agm_df[ri_col].nunique() if ri_col else 0
    n_branches = agm_df['Branch'].nunique() if 'Branch' in agm_df.columns else 0

    tot_ns = float(agm_df['CY-NS'].sum()) if 'CY-NS' in agm_df.columns else 0.0
    tot_sc = float(agm_df['CY-SC'].sum()) if 'CY-SC' in agm_df.columns else 0.0
    ly_ns = float(agm_df['LY-NS'].sum()) if 'LY-NS' in agm_df.columns else 0.0
    ly_sc = float(agm_df['LY-SC'].sum()) if 'LY-SC' in agm_df.columns else 0.0

    cy_str = (tot_ns / tot_sc) if tot_sc > 0 else 0.0
    ly_str = (ly_ns / ly_sc) if ly_sc > 0 else 0.0

    tot_nos = float(agm_df['NOS'].sum()) if 'NOS' in agm_df.columns else 0.0
    avg_sps = (tot_ns / tot_nos) if tot_nos > 0 else 0.0

    # 1. About This AGM
    sec1_content = (
        f"* **AGM:** {display_agm_name}\n"
        f"* **Number of Zones:** {n_zones}\n"
        f"* **Number of RIs:** {n_ris}\n"
        f"* **Number of Branches:** {n_branches}"
    )

    # 2. Overall Staffing & Ratio Summary
    str_diff = cy_str - ly_str
    diff_sign = "+" if str_diff >= 0 else ""
    sec2_content = (
        f"Across {n_branches} branches, a total student strength of **{format_compact_count(tot_ns)}** is served by **{format_compact_count(tot_sc)}** staff members, "
        f"yielding an overall Student-Teacher Ratio (STR) of **{cy_str:.2f}** ({diff_sign}{str_diff:.2f} vs last year's {ly_str:.2f}).\n\n"
        f"The AGM operates **{format_compact_count(tot_nos)}** total sections with an average of **{avg_sps:.2f}** students per section."
    )

    # 3. Level-Wise Staffing Ratios
    pp_ns = float(agm_df['PP-CY-NS'].sum()) if 'PP-CY-NS' in agm_df.columns else 0.0
    pp_sc = float(agm_df['PP-CY-SC'].sum()) if 'PP-CY-SC' in agm_df.columns else 0.0
    pp_str = (pp_ns / pp_sc) if pp_sc > 0 else 0.0

    ps_ns = float(agm_df['PS-CY-NS'].sum()) if 'PS-CY-NS' in agm_df.columns else 0.0
    ps_sc = float(agm_df['PS-CY-SC'].sum()) if 'PS-CY-SC' in agm_df.columns else 0.0
    ps_str = (ps_ns / ps_sc) if ps_sc > 0 else 0.0

    hs_ns = float(agm_df['HS-CY-NS'].sum()) if 'HS-CY-NS' in agm_df.columns else 0.0
    hs_sc = float(agm_df['HS-CY-SC'].sum()) if 'HS-CY-SC' in agm_df.columns else 0.0
    hs_str = (hs_ns / hs_sc) if hs_sc > 0 else 0.0

    sec3_content = (
        f"* **Pre Primary (PP):** {format_compact_count(pp_ns)} students | {format_compact_count(pp_sc)} staff | STR of **{pp_str:.2f}**\n"
        f"* **Primary School (PS):** {format_compact_count(ps_ns)} students | {format_compact_count(ps_sc)} staff | STR of **{ps_str:.2f}**\n"
        f"* **High School (HS):** {format_compact_count(hs_ns)} students | {format_compact_count(hs_sc)} staff | STR of **{hs_str:.2f}**"
    )

    # 4. Zone Performance
    zone_rows = []
    zone_table_lines = [
        "| Zone | Student Count | Staff Count | Student-Teacher Ratio | Avg Students per Section |",
        "| :--- | ---: | ---: | ---: | ---: |",
    ]
    if 'Zone' in agm_df.columns:
        for z_name, z_group in agm_df.groupby('Zone'):
            z_ns = float(z_group['CY-NS'].sum())
            z_sc = float(z_group['CY-SC'].sum())
            z_nos = float(z_group['NOS'].sum()) if 'NOS' in z_group.columns else 0.0
            z_str = (z_ns / z_sc) if z_sc > 0 else 0.0
            z_sps = (z_ns / z_nos) if z_nos > 0 else 0.0
            zone_rows.append({'zone': z_name, 'ns': z_ns, 'sc': z_sc, 'str': z_str, 'sps': z_sps})
            zone_table_lines.append(f"| {z_name} | {format_compact_count(z_ns)} | {format_compact_count(z_sc)} | {z_str:.2f} | {z_sps:.2f} |")

    top_zone_str = min(zone_rows, key=lambda x: x['str']) if zone_rows else None
    sec4_note = f"\n\n**Among the Zones, {top_zone_str['zone']} has the lowest Student-Teacher Ratio at {top_zone_str['str']:.2f} (most staff-intensive).**" if top_zone_str else ""
    sec4_content = "\n".join(zone_table_lines) + sec4_note

    # 5. RI Performance
    ri_rows = []
    ri_table_lines = [
        "| RI | Number of Branches | Student Count | Staff Count | Student-Teacher Ratio | Avg Students per Section |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    if ri_col and ri_col in agm_df.columns:
        for r_raw, r_group in agm_df.groupby(ri_col):
            r_disp = format_display_ri_name(r_raw)
            r_n_b = r_group['Branch'].nunique() if 'Branch' in r_group.columns else 0
            r_ns = float(r_group['CY-NS'].sum())
            r_sc = float(r_group['CY-SC'].sum())
            r_nos = float(r_group['NOS'].sum()) if 'NOS' in r_group.columns else 0.0
            r_str = (r_ns / r_sc) if r_sc > 0 else 0.0
            r_sps = (r_ns / r_nos) if r_nos > 0 else 0.0
            ri_rows.append({'ri': r_disp, 'n_branches': r_n_b, 'ns': r_ns, 'sc': r_sc, 'str': r_str, 'sps': r_sps})
            ri_table_lines.append(f"| {r_disp} | {r_n_b} | {format_compact_count(r_ns)} | {format_compact_count(r_sc)} | {r_str:.2f} | {r_sps:.2f} |")

    top_ri_str = min(ri_rows, key=lambda x: x['str']) if ri_rows else None
    sec5_note = f"\n\n**Among the RIs, RI {top_ri_str['ri']} has the lowest Student-Teacher Ratio at {top_ri_str['str']:.2f} across {top_ri_str['n_branches']} branches.**" if top_ri_str else ""
    sec5_content = "\n".join(ri_table_lines) + sec5_note

    # 6. Branches Needing Attention
    b_list = []
    for _, r in agm_df.iterrows():
        r_ns = float(r.get('CY-NS', 0))
        r_sc = float(r.get('CY-SC', 0))
        r_str = float(r.get('CY-STR', (r_ns / r_sc) if r_sc > 0 else 0))
        r_sps = float(r.get('Avg-SPS', 0))
        b_list.append({
            'branch': str(r['Branch']),
            'str': r_str,
            'sps': r_sps,
        })

    lowest_str_b = min(b_list, key=lambda x: x['str']) if b_list else None
    highest_str_b = max(b_list, key=lambda x: x['str']) if b_list else None
    highest_sps_b = max(b_list, key=lambda x: x['sps']) if b_list else None

    sec6_bullets = []
    if lowest_str_b:
        sec6_bullets.append(f"* **Lowest Student-Teacher Ratio:** **{lowest_str_b['branch']}** — **{lowest_str_b['str']:.2f}** (most staff-intensive)")
    if highest_str_b:
        sec6_bullets.append(f"* **Highest Student-Teacher Ratio:** **{highest_str_b['branch']}** — **{highest_str_b['str']:.2f}** (highest student load per teacher)")
    if highest_sps_b:
        sec6_bullets.append(f"* **Highest Students per Section:** **{highest_sps_b['branch']}** — **{highest_sps_b['sps']:.2f}** students/section")
    sec6_content = "\n".join(sec6_bullets)

    # 7. Conclusion
    top_z_name = top_zone_str['zone'] if top_zone_str else "N/A"
    top_r_name = top_ri_str['ri'] if top_ri_str else "N/A"
    highest_str_branch = highest_str_b['branch'] if highest_str_b else 'N/A'
    highest_str_val = f"{highest_str_b['str']:.2f}" if highest_str_b else 'N/A'
    sec7_content = (
        f"AGM {display_agm_name} operates with an overall Student-Teacher Ratio of **{cy_str:.2f}** across **{format_compact_count(tot_ns)} students** and **{format_compact_count(tot_sc)} staff**.\n\n"
        f"Zone **{top_z_name}** and RI **{top_r_name}** provide the highest staff intensity. "
        f"Branch **{highest_str_branch}** ({highest_str_val} STR) should be monitored for teacher workload and section balancing."
    )

    evidence_rows = []
    for _, r in agm_df.iterrows():
        r_ns = float(r.get('CY-NS', 0))
        r_sc = float(r.get('CY-SC', 0))
        r_str = float(r.get('CY-STR', (r_ns / r_sc) if r_sc > 0 else 0))
        pp_s = float(r.get('PP-CY-STR', 0))
        ps_s = float(r.get('PS-CY-STR', 0))
        hs_s = float(r.get('HS-CY-STR', 0))
        r_sps = float(r.get('Avg-SPS', 0))
        evidence_rows.append([
            str(r['Branch']),
            format_compact_count(r_ns),
            format_compact_count(r_sc),
            f"{r_str:.2f}",
            f"{pp_s:.2f}" if pp_s > 0 else "N/A",
            f"{ps_s:.2f}" if ps_s > 0 else "N/A",
            f"{hs_s:.2f}" if hs_s > 0 else "N/A",
            f"{r_sps:.2f}",
        ])

    sections = [
        {'title': '1. About This AGM', 'content': sec1_content},
        {'title': '2. Overall Staffing & Ratio Summary', 'content': sec2_content},
        {'title': '3. Level-Wise Staffing Ratios', 'content': sec3_content},
        {'title': '4. Zone Performance', 'content': sec4_content},
        {'title': '5. RI Performance', 'content': sec5_content},
        {'title': '6. Branches Needing Attention', 'content': sec6_content},
        {'title': '7. Conclusion', 'content': sec7_content},
    ]

    return AnalysisResult(
        direct_answer=f"# AGM Teacher Student Ratio Statistics — {display_agm_name}",
        headers=['Branch', 'Student Count', 'Staff Count', 'Student Teacher Ratio', 'Pre Primary STR', 'Primary School STR', 'High School STR', 'Avg Students per Section'],
        rows=evidence_rows,
        metric='CY-STR',
        group_dimension='AGM',
        operation='analysis',
        sections=sections,
        evidence_title="Detailed Branch Teacher Student Ratio Data",
    )


def build_ri_teacher_student_ratio_analysis(df: pd.DataFrame, ri_name: str, context: dict | None = None) -> AnalysisResult:
    display_ri_name = format_display_ri_name(ri_name)
    ri_col = 'RI Name' if 'RI Name' in df.columns else ('RI' if 'RI' in df.columns else None)
    if ri_name == 'All':
        ri_df = df
    else:
        ri_df = df[df[ri_col] == ri_name] if ri_col else df

    zone_str = str(ri_df['Zone'].iloc[0]) if not ri_df.empty and 'Zone' in ri_df.columns else "N/A"
    n_branches = ri_df['Branch'].nunique() if 'Branch' in ri_df.columns else 0

    tot_ns = float(ri_df['CY-NS'].sum()) if 'CY-NS' in ri_df.columns else 0.0
    tot_sc = float(ri_df['CY-SC'].sum()) if 'CY-SC' in ri_df.columns else 0.0
    ly_ns = float(ri_df['LY-NS'].sum()) if 'LY-NS' in ri_df.columns else 0.0
    ly_sc = float(ri_df['LY-SC'].sum()) if 'LY-SC' in ri_df.columns else 0.0

    cy_str = (tot_ns / tot_sc) if tot_sc > 0 else 0.0
    ly_str = (ly_ns / ly_sc) if ly_sc > 0 else 0.0
    tot_nos = float(ri_df['NOS'].sum()) if 'NOS' in ri_df.columns else 0.0
    avg_sps = (tot_ns / tot_nos) if tot_nos > 0 else 0.0

    # 1. About This RI
    sec1_content = (
        f"* **RI:** {display_ri_name}\n"
        f"* **Zone:** {zone_str}\n"
        f"* **Number of Branches:** {n_branches}"
    )

    # 2. Overall Staffing & Ratio Summary
    str_diff = cy_str - ly_str
    diff_sign = "+" if str_diff >= 0 else ""
    sec2_content = (
        f"Across {n_branches} branches in {zone_str} Zone, RI {display_ri_name} serves **{format_compact_count(tot_ns)}** students with **{format_compact_count(tot_sc)}** staff members, "
        f"achieving an overall Student-Teacher Ratio of **{cy_str:.2f}** ({diff_sign}{str_diff:.2f} vs last year's {ly_str:.2f}).\n\n"
        f"The RI operates **{format_compact_count(tot_nos)}** total sections with an average of **{avg_sps:.2f}** students per section."
    )

    # 3. Level-Wise Staffing Ratios
    pp_ns = float(ri_df['PP-CY-NS'].sum()) if 'PP-CY-NS' in ri_df.columns else 0.0
    pp_sc = float(ri_df['PP-CY-SC'].sum()) if 'PP-CY-SC' in ri_df.columns else 0.0
    pp_str = (pp_ns / pp_sc) if pp_sc > 0 else 0.0

    ps_ns = float(ri_df['PS-CY-NS'].sum()) if 'PS-CY-NS' in ri_df.columns else 0.0
    ps_sc = float(ri_df['PS-CY-SC'].sum()) if 'PS-CY-SC' in ri_df.columns else 0.0
    ps_str = (ps_ns / ps_sc) if ps_sc > 0 else 0.0

    hs_ns = float(ri_df['HS-CY-NS'].sum()) if 'HS-CY-NS' in ri_df.columns else 0.0
    hs_sc = float(ri_df['HS-CY-SC'].sum()) if 'HS-CY-SC' in ri_df.columns else 0.0
    hs_str = (hs_ns / hs_sc) if hs_sc > 0 else 0.0

    sec3_content = (
        f"* **Pre Primary (PP):** {format_compact_count(pp_ns)} students | {format_compact_count(pp_sc)} staff | STR of **{pp_str:.2f}**\n"
        f"* **Primary School (PS):** {format_compact_count(ps_ns)} students | {format_compact_count(ps_sc)} staff | STR of **{ps_str:.2f}**\n"
        f"* **High School (HS):** {format_compact_count(hs_ns)} students | {format_compact_count(hs_sc)} staff | STR of **{hs_str:.2f}**"
    )

    # 4. Branches Needing Attention (Branch Performance summary table removed!)
    b_list = []
    for _, r in ri_df.iterrows():
        r_ns = float(r.get('CY-NS', 0))
        r_sc = float(r.get('CY-SC', 0))
        r_str = float(r.get('CY-STR', (r_ns / r_sc) if r_sc > 0 else 0))
        r_sps = float(r.get('Avg-SPS', 0))
        b_list.append({
            'branch': str(r['Branch']),
            'str': r_str,
            'sps': r_sps,
        })

    lowest_str_b = min(b_list, key=lambda x: x['str']) if b_list else None
    highest_str_b = max(b_list, key=lambda x: x['str']) if b_list else None
    highest_sps_b = max(b_list, key=lambda x: x['sps']) if b_list else None

    sec4_bullets = []
    if lowest_str_b:
        sec4_bullets.append(f"* **Lowest Student-Teacher Ratio:** **{lowest_str_b['branch']}** — **{lowest_str_b['str']:.2f}** (highest staff intensity)")
    if highest_str_b:
        sec4_bullets.append(f"* **Highest Student-Teacher Ratio:** **{highest_str_b['branch']}** — **{highest_str_b['str']:.2f}** (highest student load)")
    if highest_sps_b:
        sec4_bullets.append(f"* **Highest Students per Section:** **{highest_sps_b['branch']}** — **{highest_sps_b['sps']:.2f}** students/section")
    sec4_content = "\n".join(sec4_bullets)

    # 5. Conclusion
    sec5_content = (
        f"RI {display_ri_name} maintains an overall Student-Teacher Ratio of **{cy_str:.2f}** across **{n_branches} branches**.\n\n"
        f"Branch **{lowest_str_b['branch'] if lowest_str_b else 'N/A'}** has the most favorable staffing ratio, while **{highest_str_b['branch'] if highest_str_b else 'N/A'}** ({highest_str_b['str']:.2f} STR) should be evaluated for section/teacher alignment."
    )

    evidence_rows = []
    for _, r in ri_df.iterrows():
        r_ns = float(r.get('CY-NS', 0))
        r_sc = float(r.get('CY-SC', 0))
        r_str = float(r.get('CY-STR', (r_ns / r_sc) if r_sc > 0 else 0))
        pp_s = float(r.get('PP-CY-STR', 0))
        ps_s = float(r.get('PS-CY-STR', 0))
        hs_s = float(r.get('HS-CY-STR', 0))
        r_sps = float(r.get('Avg-SPS', 0))
        evidence_rows.append([
            str(r['Branch']),
            format_compact_count(r_ns),
            format_compact_count(r_sc),
            f"{r_str:.2f}",
            f"{pp_s:.2f}" if pp_s > 0 else "N/A",
            f"{ps_s:.2f}" if ps_s > 0 else "N/A",
            f"{hs_s:.2f}" if hs_s > 0 else "N/A",
            f"{r_sps:.2f}",
        ])

    sections = [
        {'title': '1. About This RI', 'content': sec1_content},
        {'title': '2. Overall Staffing & Ratio Summary', 'content': sec2_content},
        {'title': '3. Level-Wise Staffing Ratios', 'content': sec3_content},
        {'title': '4. Branches Needing Attention', 'content': sec4_content},
        {'title': '5. Conclusion', 'content': sec5_content},
    ]

    return AnalysisResult(
        direct_answer=f"# RI Teacher Student Ratio Statistics — {display_ri_name}",
        headers=['Branch', 'Student Count', 'Staff Count', 'Student Teacher Ratio', 'Pre Primary STR', 'Primary School STR', 'High School STR', 'Avg Students per Section'],
        rows=evidence_rows,
        metric='CY-STR',
        group_dimension='RI',
        operation='analysis',
        sections=sections,
        evidence_title="Detailed Branch Teacher Student Ratio Data",
    )


def build_branch_teacher_student_ratio_analysis(df: pd.DataFrame, branch_name: str, context: dict | None = None) -> AnalysisResult:
    b_df = df[df['Branch'] == branch_name]
    if b_df.empty:
        raw_branch_name = branch_name
        agm_name = "N/A"
        ri_name = "N/A"
        zone_name = "N/A"
        tot_ns = tot_sc = cy_str = ly_str = tot_nos = avg_sps = 0.0
        pp_ns = pp_sc = pp_str = ps_ns = ps_sc = ps_str = hs_ns = hs_sc = hs_str = 0.0
    else:
        raw_branch_name = branch_name
        r0 = b_df.iloc[0]
        agm_name = format_display_ri_name(r0.get('AGM Name') or r0.get('AGM') or '')
        ri_name = format_display_ri_name(r0.get('RI Name') or r0.get('RI') or '')
        zone_name = str(r0.get('Zone', ''))
        tot_ns = float(r0.get('CY-NS', 0))
        tot_sc = float(r0.get('CY-SC', 0))
        cy_str = float(r0.get('CY-STR', (tot_ns / tot_sc) if tot_sc > 0 else 0))
        ly_str = float(r0.get('LY-STR', 0))
        tot_nos = float(r0.get('NOS', 0))
        avg_sps = float(r0.get('Avg-SPS', 0))

        pp_ns = float(r0.get('PP-CY-NS', 0))
        pp_sc = float(r0.get('PP-CY-SC', 0))
        pp_str = float(r0.get('PP-CY-STR', (pp_ns / pp_sc) if pp_sc > 0 else 0))

        ps_ns = float(r0.get('PS-CY-NS', 0))
        ps_sc = float(r0.get('PS-CY-SC', 0))
        ps_str = float(r0.get('PS-CY-STR', (ps_ns / ps_sc) if ps_sc > 0 else 0))

        hs_ns = float(r0.get('HS-CY-NS', 0))
        hs_sc = float(r0.get('HS-CY-SC', 0))
        hs_str = float(r0.get('HS-CY-STR', (hs_ns / hs_sc) if hs_sc > 0 else 0))

    str_diff = cy_str - ly_str
    diff_sign = "+" if str_diff >= 0 else ""

    # 1. About This Branch
    sec1_content = (
        f"* **Branch:** {raw_branch_name}\n"
        f"* **AGM:** {agm_name}\n"
        f"* **RI:** {ri_name}\n"
        f"* **Zone:** {zone_name}"
    )

    # 2. Staffing & Operational Overview
    sec2_content = (
        f"In **{raw_branch_name}**, a student strength of **{format_compact_count(tot_ns)}** is managed by **{format_compact_count(tot_sc)}** staff members, "
        f"resulting in a Student-Teacher Ratio of **{cy_str:.2f}** ({diff_sign}{str_diff:.2f} vs last year's {ly_str:.2f}).\n\n"
        f"The branch operates **{format_compact_count(tot_nos)}** sections with an average of **{avg_sps:.2f}** students per section."
    )

    # 3. Level-Wise Staffing Breakdown
    sec3_content = (
        f"* **Pre Primary (PP):** {format_compact_count(pp_ns)} students | {format_compact_count(pp_sc)} staff | STR of **{pp_str:.2f}**\n"
        f"* **Primary School (PS):** {format_compact_count(ps_ns)} students | {format_compact_count(ps_sc)} staff | STR of **{ps_str:.2f}**\n"
        f"* **High School (HS):** {format_compact_count(hs_ns)} students | {format_compact_count(hs_sc)} staff | STR of **{hs_str:.2f}**"
    )

    # 4. Conclusion
    sec4_content = (
        f"**{raw_branch_name}** maintains an overall Student-Teacher Ratio of **{cy_str:.2f}** across **{format_compact_count(tot_nos)}** sections ({avg_sps:.2f} students/section)."
    )

    sections = [
        {'title': '1. About This Branch', 'content': sec1_content},
        {'title': '2. Staffing & Operational Overview', 'content': sec2_content},
        {'title': '3. Level-Wise Staffing Breakdown', 'content': sec3_content},
        {'title': '4. Conclusion', 'content': sec4_content},
    ]

    evidence_rows = [
        ['Current Year Student Strength (CY-NS)', format_compact_count(tot_ns)],
        ['Current Year Staff Count (CY-SC)', format_compact_count(tot_sc)],
        ['Current Year Student Teacher Ratio (CY-STR)', f"{cy_str:.2f}"],
        ['Last Year Student Teacher Ratio (LY-STR)', f"{ly_str:.2f}"],
        ['Total Sections (NOS)', format_compact_count(tot_nos)],
        ['Average Students per Section (Avg-SPS)', f"{avg_sps:.2f}"],
        ['Pre Primary Student Teacher Ratio (PP-CY-STR)', f"{pp_str:.2f}"],
        ['Primary School Student Teacher Ratio (PS-CY-STR)', f"{ps_str:.2f}"],
        ['High School Student Teacher Ratio (HS-CY-STR)', f"{hs_str:.2f}"],
    ]

    return AnalysisResult(
        direct_answer=f"# Branch Teacher Student Ratio Statistics — {raw_branch_name}",
        headers=['Metric', 'Value'],
        rows=evidence_rows,
        metric='CY-STR',
        group_dimension='Branch',
        operation='analysis',
        sections=sections,
        evidence_title="Detailed Branch Teacher Student Ratio Data",
    )



