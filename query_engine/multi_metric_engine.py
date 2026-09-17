"""
query_engine/multi_metric_engine.py

Generic, plan-driven multi-metric analytics engine supporting:
- Multi-metric rankings: 'Top 5 branches by dropout count with dropout percentage'
- Multi-metric groupings: 'RI wise fee due with dropouts'
- Cross-domain multi-metric queries: 'Top 5 AGMs by salary percentage with fee paid but books not purchased'
- Teacher-student ratio (STR), Dropout, Fee Due, Revenue vs Salary
- MetricSpec registry as the single source of truth
- Canonical hierarchy join keys (_clean_str) with clean display preservation
- Year compatibility tracking (explaining when historical LY is unavailable)
- Explicit scope precedence (Dashboard Context < Question Scope < Global Override)
- Strict raw group sum derivation (SUM(num)/SUM(den), never average of averages)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from .dataset_loader import load_dataset
from .filters import apply_filter_context, _clean_str
from .analysis_engine import format_value_str, AnalysisResult


# -----------------------------------------------------------------------------
# Metric Specification & Registry
# -----------------------------------------------------------------------------

@dataclass
class MetricSpec:
    id: str
    display_name: str
    dataset: str
    metric_type: str  # 'raw' | 'derived'
    display_type: str  # 'count' | 'percentage' | 'currency' | 'numeric'
    dependencies: List[str] = field(default_factory=list)
    raw_col: Optional[str] = None
    numerator: Optional[str] = None
    denominator: Optional[str] = None
    formula: str = 'sum'  # 'sum' | 'ratio_percentage' | 'ratio_numeric' | 'subtraction'
    multiplier: float = 1.0
    supports_ranking: bool = True
    supported_years: List[str] = field(default_factory=lambda: ['CY'])

    def supports_year(self, year: str) -> bool:
        return str(year).upper() in self.supported_years


METRIC_REGISTRY: Dict[str, MetricSpec] = {
    # -------------------------------------------------------------------------
    # Dropout Domain (branch_analytics)
    # -------------------------------------------------------------------------
    'dropout_count': MetricSpec(
        id='dropout_count',
        display_name='Dropout Count',
        dataset='branch_analytics',
        metric_type='raw',
        display_type='count',
        raw_col='CY-DP',
        dependencies=['CY-DP'],
        supported_years=['CY', 'LY'],
    ),
    'dropout_percentage': MetricSpec(
        id='dropout_percentage',
        display_name='Dropout %',
        dataset='branch_analytics',
        metric_type='derived',
        display_type='percentage',
        numerator='CY-DP',
        denominator='CY-NS',
        formula='ratio_percentage',
        multiplier=100.0,
        dependencies=['CY-DP', 'CY-NS'],
        supported_years=['CY', 'LY'],
    ),
    'ly_dropout_count': MetricSpec(
        id='ly_dropout_count',
        display_name='Previous Year Dropout Count',
        dataset='branch_analytics',
        metric_type='raw',
        display_type='count',
        raw_col='LY-DP',
        dependencies=['LY-DP'],
        supported_years=['LY'],
    ),
    'ly_dropout_percentage': MetricSpec(
        id='ly_dropout_percentage',
        display_name='Previous Year Dropout %',
        dataset='branch_analytics',
        metric_type='derived',
        display_type='percentage',
        numerator='LY-DP',
        denominator='LY-NS',
        formula='ratio_percentage',
        multiplier=100.0,
        dependencies=['LY-DP', 'LY-NS'],
        supported_years=['LY'],
    ),
    'existing_dropout': MetricSpec(
        id='existing_dropout',
        display_name='Existing Student Dropouts',
        dataset='branch_analytics',
        metric_type='raw',
        display_type='count',
        raw_col='E-CY-DP',
        dependencies=['E-CY-DP'],
        supported_years=['CY', 'LY'],
    ),
    'new_dropout': MetricSpec(
        id='new_dropout',
        display_name='New Student Dropouts',
        dataset='branch_analytics',
        metric_type='raw',
        display_type='count',
        raw_col='N-CY-DP',
        dependencies=['N-CY-DP'],
        supported_years=['CY', 'LY'],
    ),
    'net_strength': MetricSpec(
        id='net_strength',
        display_name='Net Strength',
        dataset='branch_analytics',
        metric_type='raw',
        display_type='count',
        raw_col='CY-NS',
        dependencies=['CY-NS'],
        supported_years=['CY', 'LY'],
    ),

    # -------------------------------------------------------------------------
    # Fee Due Domain (fee_analysis)
    # -------------------------------------------------------------------------
    'fee_due': MetricSpec(
        id='fee_due',
        display_name='2025-26 Fee Due',
        dataset='fee_analysis',
        metric_type='raw',
        display_type='currency',
        raw_col='CY_A_FD',
        dependencies=['CY_A_FD'],
        supported_years=['CY', 'LY'],
    ),
    'fee_due_count': MetricSpec(
        id='fee_due_count',
        display_name='Fee Due Count',
        dataset='fee_analysis',
        metric_type='raw',
        display_type='count',
        raw_col='CY_A_FDC',
        dependencies=['CY_A_FDC'],
        supported_years=['CY', 'LY'],
    ),
    'ly_fee_due': MetricSpec(
        id='ly_fee_due',
        display_name='2024-25 Fee Due',
        dataset='fee_analysis',
        metric_type='raw',
        display_type='currency',
        raw_col='LY_FD',
        dependencies=['LY_FD'],
        supported_years=['LY'],
    ),
    'ly_fee_due_count': MetricSpec(
        id='ly_fee_due_count',
        display_name='2024-25 Fee Due Count',
        dataset='fee_analysis',
        metric_type='raw',
        display_type='count',
        raw_col='LY_FDC',
        dependencies=['LY_FDC'],
        supported_years=['LY'],
    ),
    'zero_paid_count': MetricSpec(
        id='zero_paid_count',
        display_name='Zero Paid Count',
        dataset='fee_analysis',
        metric_type='raw',
        display_type='count',
        raw_col='CY_A_ZP',
        dependencies=['CY_A_ZP'],
        supported_years=['CY', 'LY'],
    ),
    'zero_paid_fee_due': MetricSpec(
        id='zero_paid_fee_due',
        display_name='Zero Paid Fee Due',
        dataset='fee_analysis',
        metric_type='raw',
        display_type='currency',
        raw_col='CY_ZP_FD',
        dependencies=['CY_ZP_FD'],
        supported_years=['CY', 'LY'],
    ),
    'fee_paid_books_not_purchased': MetricSpec(
        id='fee_paid_books_not_purchased',
        display_name='Fee Paid, Books Not Purchased',
        dataset='fee_analysis',
        metric_type='raw',
        display_type='count',
        raw_col='CY_FP_BN',
        dependencies=['CY_FP_BN'],
        supported_years=['CY', 'LY'],
    ),
    'fee_not_paid_books_not_purchased': MetricSpec(
        id='fee_not_paid_books_not_purchased',
        display_name='Fee Not Paid, Books Not Purchased',
        dataset='fee_analysis',
        metric_type='raw',
        display_type='count',
        raw_col='CY_FN_BN',
        dependencies=['CY_FN_BN'],
        supported_years=['CY', 'LY'],
    ),

    # -------------------------------------------------------------------------
    # Revenue vs Salary Domain (revenue_vs_salary)
    # -------------------------------------------------------------------------
    'revenue': MetricSpec(
        id='revenue',
        display_name='Total Net Revenue',
        dataset='revenue_vs_salary',
        metric_type='raw',
        display_type='currency',
        raw_col='TOT_REV_N',
        dependencies=['TOT_REV_N'],
        supported_years=['CY'],  # Historical LY unavailable in current dataset
    ),
    'salary': MetricSpec(
        id='salary',
        display_name='Total Staff Salary',
        dataset='revenue_vs_salary',
        metric_type='raw',
        display_type='currency',
        raw_col='TOT_SAL',
        dependencies=['TOT_SAL'],
        supported_years=['CY'],
    ),
    'salary_percentage': MetricSpec(
        id='salary_percentage',
        display_name='Salary %',
        dataset='revenue_vs_salary',
        metric_type='derived',
        display_type='percentage',
        numerator='TOT_SAL',
        denominator='TOT_REV_N',
        formula='ratio_percentage',
        multiplier=100.0,
        dependencies=['TOT_SAL', 'TOT_REV_N'],
        supported_years=['CY'],
    ),
    'surplus': MetricSpec(
        id='surplus',
        display_name='Surplus (Revenue - Salary)',
        dataset='revenue_vs_salary',
        metric_type='derived',
        display_type='currency',
        numerator='TOT_REV_N',
        denominator='TOT_SAL',
        formula='subtraction',
        dependencies=['TOT_REV_N', 'TOT_SAL'],
        supported_years=['CY'],
    ),

    # -------------------------------------------------------------------------
    # Teacher-Student Ratio Domain (branch_analytics)
    # -------------------------------------------------------------------------
    'str': MetricSpec(
        id='str',
        display_name='Student Teacher Ratio',
        dataset='branch_analytics',
        metric_type='derived',
        display_type='numeric',
        numerator='CY-NS',
        denominator='CY-SC',
        formula='ratio_numeric',
        multiplier=1.0,
        dependencies=['CY-NS', 'CY-SC'],
        supported_years=['CY'],
    ),
    'staff_count': MetricSpec(
        id='staff_count',
        display_name='Staff Count',
        dataset='branch_analytics',
        metric_type='raw',
        display_type='count',
        raw_col='CY-SC',
        dependencies=['CY-SC'],
        supported_years=['CY'],
    ),
    'sections': MetricSpec(
        id='sections',
        display_name='Number of Sections',
        dataset='branch_analytics',
        metric_type='raw',
        display_type='count',
        raw_col='NOS',
        dependencies=['NOS'],
        supported_years=['CY'],
    ),
    'students_per_section': MetricSpec(
        id='students_per_section',
        display_name='Students Per Section',
        dataset='branch_analytics',
        metric_type='derived',
        display_type='numeric',
        numerator='CY-NS',
        denominator='NOS',
        formula='ratio_numeric',
        multiplier=1.0,
        dependencies=['CY-NS', 'NOS'],
        supported_years=['CY'],
    ),
}

METRIC_REGISTRY_MAP = METRIC_REGISTRY  # Backwards compatibility alias

# Ordered metric matching patterns (multi-word phrases first to prevent partial collision)
METRIC_PATTERNS: List[Tuple[str, str]] = [
    # Complex phrase mappings to single metrics
    (r'\bpercentage\s+of\s+revenue\s+(?:is\s+)?spent\s+on\s+salary\b', 'salary_percentage'),
    (r'\bpercentage\s+of\s+salary\s+(?:to|vs|of)\s+revenue\b', 'salary_percentage'),
    (r'\brevenue\s*spent\s*on\s*salary\b', 'salary_percentage'),
    (r'\bsalary\s*burden\b', 'salary_percentage'),
    (r'\bsalary\s*(?:percentage|%|ratio)\b', 'salary_percentage'),
    (r'\bsal\s*vs\s*rev\b', 'salary_percentage'),
    (r'\bfee\s+paid\s+(?:but\s+)?books?\s+not\s+purchased\b', 'fee_paid_books_not_purchased'),
    (r'\bfee\s+not\s+paid\s+(?:and\s+)?books?\s+not\s+purchased\b', 'fee_not_paid_books_not_purchased'),
    (r'\bzero\s*paid\s+fee\s+due\b', 'zero_paid_fee_due'),
    (r'\bzero\s*paid\s+(?:count|students?)\b', 'zero_paid_count'),
    (r'\bzero\s*paid\b', 'zero_paid_count'),
    (r'\bfee\s+due\s+count\b', 'fee_due_count'),
    (r'\bfee\s+due\b', 'fee_due'),
    (r'\b(?:dropout|dropouts|drop\s*outs?)\s*(?:percentage|%|pct)\b', 'dropout_percentage'),
    (r'\bdpp\b', 'dropout_percentage'),
    (r'\b(?:dropout|dropouts|drop\s*outs?)\s*count\b', 'dropout_count'),
    (r'\b(?:dropouts|dropout|drop\s*outs?)\b', 'dropout_count'),
    (r'\bsalary\b', 'salary'),
    (r'\b(?:net\s+)?revenue\b', 'revenue'),
    (r'\bsurplus\b', 'surplus'),
    (r'\b(?:student\s*teacher\s*ratio|teacher\s*student\s*ratio|str)\b', 'str'),
    (r'\b(?:staff\s*count|teacher\s*count|teachers?|staff)\b', 'staff_count'),
    (r'\b(?:students?\s*per\s*section|sps)\b', 'students_per_section'),
    (r'\b(?:number\s*of\s*sections|sections)\b', 'sections'),
    (r'\b(?:net\s*strength|student\s*strength)\b', 'net_strength'),
]

DIMENSION_COLS: Dict[str, str] = {
    'branch': 'Branch',
    'ri': 'RI Name',
    'zone': 'Zone',
    'agm': 'AGM Name',
}


# -----------------------------------------------------------------------------
# Structured Query Plan
# -----------------------------------------------------------------------------

@dataclass
class QueryPlan:
    operation: str  # 'ranking', 'group_by'
    group_by: str  # 'branch', 'ri', 'zone', 'agm'
    metrics: List[str]
    rank_by: Optional[str] = None
    direction: str = 'desc'
    limit: Optional[int] = None
    scope: Dict[str, str] = field(default_factory=dict)
    raw_question: str = ""
    notes: List[str] = field(default_factory=list)


def clean_display_name(s: Any) -> str:
    """Strips honorifics/prefixes for clean, professional executive display."""
    val = str(s).strip()
    val = re.sub(r'^(?:mrs|mr|ms|dr)\.?\s*', '', val, flags=re.IGNORECASE).strip()
    val = re.sub(r'^\.\s*', '', val).strip()
    val = re.sub(r'\s+', ' ', val)
    return val


def detect_group_dimension(text: str) -> str:
    """Detects group dimension prioritizing explicit '<dim> wise' and 'wise <dim>' phrases."""
    q = text.lower()
    patterns = [
        (r'\b(?:ri-wise|ri\s+wise|wise\s+ri|by\s+ris?|across\s+ris?|per\s+ri|which\s+ris?)\b', 'ri'),
        (r'\b(?:zone-wise|zone\s+wise|wise\s+zone|by\s+zones?|across\s+zones?|per\s+zone|which\s+zones?)\b', 'zone'),
        (r'\b(?:agm-wise|agm\s+wise|wise\s+agm|by\s+agms?|across\s+agms?|per\s+agm|which\s+agms?)\b', 'agm'),
        (r'\b(?:branch-wise|branch\s+wise|wise\s+branch|by\s+branches?|across\s+branches?|per\s+branch|which\s+branches?)\b', 'branch'),
    ]
    for pat, dim in patterns:
        if re.search(pat, q):
            return dim
    if re.search(r'\b(?:agms?)\b', q) and not re.search(r'\b(?:branches?|ris?|zones?)\b', q):
        return 'agm'
    if re.search(r'\b(?:ris?)\b', q) and not re.search(r'\b(?:branches?|agms?|zones?)\b', q):
        return 'ri'
    if re.search(r'\b(?:zones?)\b', q) and not re.search(r'\b(?:branches?|agms?|ris?)\b', q):
        return 'zone'
    return 'branch'


def extract_metrics_from_text(text: str) -> List[Tuple[int, int, str]]:
    """Returns list of (start_idx, end_idx, metric_id) in order of appearance."""
    # Strip dataset references (e.g. "in revenue vs salary dataset", "fee due sheet")
    text_clean = re.sub(
        r'\b(?:in|from|of)\s+(?:the\s+)?(?:revenue\s*(?:vs|&|and)?\s*salary|fee\s*due|branch\s*analytics)\s+(?:dataset|excel|file|sheet|data|report)\b',
        '',
        text,
        flags=re.IGNORECASE
    )
    t = text_clean.lower()
    matches: List[Tuple[int, int, str]] = []
    occupied: List[Tuple[int, int]] = []

    for pattern, m_id in METRIC_PATTERNS:
        for m in re.finditer(pattern, t):
            s, e = m.start(), m.end()
            if any(max(s, os_) < min(e, oe_) for os_, oe_ in occupied):
                continue
            matches.append((s, e, m_id))
            occupied.append((s, e))

    matches.sort(key=lambda x: x[0])
    return matches


def build_query_plan(question: str, context: Optional[dict] = None) -> Optional[QueryPlan]:
    """
    Parses user question and context into a structured QueryPlan.
    Applies explicit scope precedence:
      1. Global Overrides ('across all agms')
      2. Question Filter ('under AGM Ramana Rao')
      3. Dashboard Context
    """
    q_low = question.lower()
    matches = extract_metrics_from_text(question)
    if not matches:
        return None

    all_found_metrics: List[str] = []
    for _, _, m_id in matches:
        if m_id not in all_found_metrics:
            all_found_metrics.append(m_id)

    has_connector = bool(re.search(r'\b(?:with|along\s+with|plus|and\s+also|including)\b', q_low))
    if len(all_found_metrics) < 2 and not (len(all_found_metrics) == 1 and has_connector):
        return None

    # Determine Operation
    is_ranking = bool(re.search(r'\b(?:top|bottom|highest|lowest|rank|best|worst|fewest)\b', q_low))
    operation = 'ranking' if is_ranking else 'group_by'

    # Determine Group By
    group_by = detect_group_dimension(question)

    # Determine Ranking Metric (rank_by)
    rank_by = None
    if is_ranking:
        by_match = re.search(r'\bby\s+(.+?)(?:\s+(?:with|along\s+with|and|plus|also|,)|$)', q_low)
        if by_match:
            by_phrase = by_match.group(1).strip()
            by_metrics = extract_metrics_from_text(by_phrase)
            if by_metrics:
                rank_by = by_metrics[0][2]
        if not rank_by and all_found_metrics:
            rank_by = all_found_metrics[0]

    # Direction & Limit
    direction = 'asc' if bool(re.search(r'\b(?:bottom|lowest|least|fewest)\b', q_low)) else 'desc'
    limit = None
    if is_ranking:
        n_match = re.search(r'\b(?:top|bottom)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b', q_low)
        if n_match:
            val = n_match.group(1)
            word_map = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
            limit = int(val) if val.isdigit() else word_map.get(val.lower(), 5)
        else:
            limit = 5

    # Scope Precedence Resolution
    # Base: Dashboard Context
    scope: Dict[str, str] = {}
    if context:
        for k, v in context.items():
            if v and str(v).strip().lower() != 'all':
                scope[k] = str(v).strip()

    # Question Global Overrides (e.g. "across all agms" / "all branches")
    if 'all agm' in q_low or 'across agm' in q_low:
        scope['agm'] = 'All'
    if 'all ri' in q_low or 'across ri' in q_low:
        scope['ri'] = 'All'
    if 'all zone' in q_low or 'across zone' in q_low:
        scope['zone'] = 'All'
    if 'all branch' in q_low or 'across branch' in q_low:
        scope['branches'] = ['All']

    # Year compatibility check
    notes = []
    if 'last year' in q_low or 'previous year' in q_low or 'ly' in q_low:
        for m_id in all_found_metrics:
            spec = METRIC_REGISTRY.get(m_id)
            if spec and not spec.supports_year('LY'):
                notes.append(f"Note: Previous year (LY) data is not available for {spec.display_name} in the dataset.")

    return QueryPlan(
        operation=operation,
        group_by=group_by,
        metrics=all_found_metrics,
        rank_by=rank_by,
        direction=direction,
        limit=limit,
        scope=scope,
        raw_question=question,
        notes=notes,
    )


# -----------------------------------------------------------------------------
# Multi-Metric Plan Executor
# -----------------------------------------------------------------------------

def execute_multi_metric_plan(plan: QueryPlan) -> AnalysisResult:
    """
    Executes a structured QueryPlan across datasets using:
    - Canonical hierarchy join keys (_clean_str)
    - Clean display name preservation
    - Pre-aggregation joins
    - Strict raw group sum derivation
    """
    all_metric_ids: List[str] = []
    if plan.rank_by and plan.rank_by not in all_metric_ids:
        all_metric_ids.append(plan.rank_by)
    for m in plan.metrics:
        if m not in all_metric_ids:
            all_metric_ids.append(m)

    # Resolve required datasets and raw columns from MetricSpec registry
    needed_datasets: Dict[str, set] = {}
    for m_id in all_metric_ids:
        spec = METRIC_REGISTRY.get(m_id)
        if not spec:
            continue
        ds = spec.dataset
        if ds not in needed_datasets:
            needed_datasets[ds] = set()
        for dep in spec.dependencies:
            needed_datasets[ds].add(dep)

    dim_col = DIMENSION_COLS.get(plan.group_by.lower(), 'Branch')

    # Load, filter, canonicalize, and pre-aggregate each dataset
    aggregated_dfs: List[pd.DataFrame] = []
    canonical_to_display: Dict[str, str] = {}

    for ds_name, cols in needed_datasets.items():
        df = load_dataset(ds_name)
        df = apply_filter_context(df, plan.scope)

        # Standardize dimension column
        if dim_col not in df.columns:
            for alt in [dim_col, dim_col.replace(' Name', ''), dim_col + ' Name']:
                if alt in df.columns:
                    df[dim_col] = df[alt]
                    break

        if dim_col in df.columns:
            df = df[df[dim_col].notna() & (df[dim_col].astype(str).str.strip() != '') & (df[dim_col].astype(str).str.strip().str.lower() != 'nan')]
            # Create canonical key for 100% robust cross-dataset join
            df['_canonical_key'] = df[dim_col].apply(_clean_str)

            # Record clean display name
            for _, r in df[[dim_col, '_canonical_key']].iterrows():
                ck = r['_canonical_key']
                if ck and ck not in canonical_to_display:
                    canonical_to_display[ck] = clean_display_name(r[dim_col])

            agg_dict = {}
            for c in cols:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                    agg_dict[c] = 'sum'

            df_agg = df.groupby('_canonical_key', as_index=False).agg(agg_dict)
            aggregated_dfs.append(df_agg)

    if not aggregated_dfs:
        return AnalysisResult(direct_answer="No data available for the requested query.", headers=[], rows=[])

    # Outer-join aggregated domain frames on canonical key
    merged_df = aggregated_dfs[0]
    for other_df in aggregated_dfs[1:]:
        merged_df = pd.merge(merged_df, other_df, on='_canonical_key', how='outer')

    # Reconstruct human-readable display column
    merged_df[dim_col] = merged_df['_canonical_key'].map(canonical_to_display).fillna(merged_df['_canonical_key'])

    # Compute derived metrics using strict MetricSpec formulas
    for m_id in all_metric_ids:
        spec = METRIC_REGISTRY.get(m_id)
        if not spec:
            continue
        if spec.metric_type == 'derived':
            num_col = spec.numerator
            den_col = spec.denominator
            formula = spec.formula

            if formula == 'subtraction':
                merged_df[m_id] = merged_df[num_col].fillna(0) - merged_df[den_col].fillna(0)
            else:
                mult = spec.multiplier
                den = merged_df[den_col].fillna(0).replace(0, float('nan'))
                merged_df[m_id] = (merged_df[num_col].fillna(0) / den) * mult
        else:
            raw_col = spec.raw_col
            if raw_col in merged_df.columns:
                merged_df[m_id] = merged_df[raw_col].fillna(0)
            else:
                merged_df[m_id] = 0

    # Sort & Rank
    if plan.operation == 'ranking' and plan.rank_by:
        ascending = (plan.direction == 'asc')
        merged_df = merged_df.sort_values(by=plan.rank_by, ascending=ascending)
        if plan.limit:
            merged_df = merged_df.head(plan.limit)
    else:
        if all_metric_ids:
            merged_df = merged_df.sort_values(by=all_metric_ids[0], ascending=False)

    # Format table headers
    headers = [plan.group_by.upper()]
    for m_id in all_metric_ids:
        spec = METRIC_REGISTRY.get(m_id)
        name = spec.display_name if spec else m_id
        if plan.operation == 'ranking' and m_id == plan.rank_by:
            name += " (Rank)"
        headers.append(name)

    # Format table rows
    rows: List[List[str]] = []
    for _, row in merged_df.iterrows():
        r_vals = [str(row[dim_col])]
        for m_id in all_metric_ids:
            spec = METRIC_REGISTRY.get(m_id)
            val = row.get(m_id)
            fmt_type = spec.display_type if spec else 'numeric'
            fmt_str = format_value_str(val, fmt_type)
            r_vals.append(fmt_str)
        rows.append(r_vals)

    # Generate executive narrative summary
    top_entity = rows[0][0] if rows else "N/A"
    summary = f"Results for {plan.group_by.upper()} analysis across {len(all_metric_ids)} metrics. Top: {top_entity}."
    if plan.notes:
        summary += "\n" + "\n".join(plan.notes)

    return AnalysisResult(
        direct_answer=summary,
        headers=headers,
        rows=rows,
        group_dimension=plan.group_by,
        operation=plan.operation,
    )
