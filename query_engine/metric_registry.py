from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MetricSpec:
    metric_id: str
    dataset_id: str
    source_column: str
    display_name: str
    data_type: str = 'numeric'  # 'numeric', 'count', 'currency', 'percentage'
    default_agg: str = 'sum'
    aliases: List[str] = field(default_factory=list)
    metric_type: str = 'additive'  # 'additive', 'derived'
    aggregation_rule: str = 'sum'  # 'sum', 'count', 'mean', 'derived'
    numerator_metric: Optional[str] = None
    denominator_metric: Optional[str] = None
    kpi_direction: str = 'positive'  # 'positive' (higher=better), 'negative' (lower=better)
    supports_comparison: bool = False
    current_year_col: Optional[str] = None
    previous_year_col: Optional[str] = None


class MetricRegistry:
    def __init__(self):
        self._metrics: Dict[str, MetricSpec] = {}
        self._alias_map: Dict[str, str] = {}

    def register(self, spec: MetricSpec) -> None:
        self._metrics[spec.metric_id] = spec
        # Register main metric ID and source column as aliases
        self._alias_map[spec.metric_id.lower()] = spec.metric_id
        self._alias_map[spec.source_column.lower()] = spec.metric_id
        for alias in spec.aliases:
            self._alias_map[alias.lower()] = spec.metric_id

    def get(self, metric_id: str) -> Optional[MetricSpec]:
        if not metric_id:
            return None
        key = metric_id.lower().strip()
        resolved_id = self._alias_map.get(key) or self._alias_map.get(key.replace('_', ' ')) or self._alias_map.get(key.replace('-', ' '))
        if not resolved_id:
            resolved_id = metric_id
        return self._metrics.get(resolved_id)

    def resolve_metric_id(self, text: str) -> Optional[str]:
        if not text:
            return None
        key = text.lower().strip()
        return self._alias_map.get(key) or self._alias_map.get(key.replace('_', ' ')) or self._alias_map.get(key.replace('-', ' '))



# Global metric registry instance
metric_registry = MetricRegistry()


def get_default_metric_registry() -> MetricRegistry:
    return metric_registry


def register_default_metrics():
    # Fee Dataset metrics
    metric_registry.register(MetricSpec(
        metric_id='CY_A_FD',
        dataset_id='fee_analysis',
        source_column='CY_A_FD',
        display_name='2025-26 Live Student Fee Due',
        data_type='currency',
        default_agg='sum',
        kpi_direction='negative',
        aliases=['fee due', '2025-26 live student fee due', 'live student fee due', 'current year fee due', 'live student due', 'cy_a_fd'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='LY_FD',
        dataset_id='fee_analysis',
        source_column='LY_FD',
        display_name='2024-25 Fee Due',
        data_type='currency',
        default_agg='sum',
        kpi_direction='negative',
        aliases=['last year fee due', '2024-25 fee due', 'ly fee due', 'ly_fd'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='CY_A_FDC',
        dataset_id='fee_analysis',
        source_column='CY_A_FDC',
        display_name='2025-26 Live Student Due Count',
        data_type='count',
        default_agg='sum',
        kpi_direction='negative',
        aliases=['2025-26 due count', 'current year due count', 'live student due count', 'due count', '2025-26 live student due count', 'cy_a_fdc'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='LY_FDC',
        dataset_id='fee_analysis',
        source_column='LY_FDC',
        display_name='2024-25 Fee Due Count',
        data_type='count',
        default_agg='sum',
        kpi_direction='negative',
        aliases=['last year due count', '2024-25 fee due count', 'ly fee due count', 'ly due count', 'ly_fdc'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='CY_A_ZP',
        dataset_id='fee_analysis',
        source_column='CY_A_ZP',
        display_name='2025-26 Actual Zero Paid',
        data_type='count',
        default_agg='sum',
        kpi_direction='negative',
        aliases=['2025-26 actual zero paid', 'actual zero paid', 'zero paid', 'cy_a_zp'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='CY_ZP',
        dataset_id='fee_analysis',
        source_column='CY_ZP',
        display_name='2025-26 Actual Zero Paid Count',
        data_type='count',
        default_agg='sum',
        kpi_direction='negative',
        aliases=['cy zero paid count', 'zero paid count', 'actual zero paid count', 'cy_zp'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='CY_ZP_FD',
        dataset_id='fee_analysis',
        source_column='CY_ZP_FD',
        display_name='Current Year Zero Paid Fee Due',
        data_type='currency',
        default_agg='sum',
        kpi_direction='negative',
        aliases=['current year zero paid fee due', 'zero paid fee due', 'cy zero paid fee due', 'cy_zp_fd'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='CY_FP_BN',
        dataset_id='fee_analysis',
        source_column='CY_FP_BN',
        display_name='Fee Paid But Books Not Purchased',
        data_type='count',
        default_agg='sum',
        aliases=['fee paid but books not purchased', 'fee paid books not purchased', 'fp bn', 'cy_fp_bn'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='CY_FN_BN',
        dataset_id='fee_analysis',
        source_column='CY_FN_BN',
        display_name='Fee Not Paid & Books Not Purchased',
        data_type='count',
        default_agg='sum',
        aliases=['fee not paid and books not purchased', 'fee not paid books not purchased', 'fn bn', 'cy_fn_bn'],
    ))

    # Branch Analytics metrics
    branch_specs = [
        MetricSpec(
            metric_id='DPP',
            dataset_id='branch_analytics',
            source_column='DPP',
            display_name='Dropouts Percentage',
            data_type='percentage',
            default_agg='derived',
            metric_type='derived',
            aggregation_rule='derived',
            numerator_metric='DP',
            denominator_metric='NS',
            kpi_direction='negative',
            aliases=['dropout percentage', 'dpp', 'dropout %', 'drop outs percentage'],
        ),
        MetricSpec(
            metric_id='DP',
            dataset_id='branch_analytics',
            source_column='DP',
            display_name='Dropouts',
            data_type='count',
            default_agg='sum',
            kpi_direction='negative',
            aliases=['dropouts', 'dropout count', 'dp', 'drop outs'],
        ),
        MetricSpec(
            metric_id='GS',
            dataset_id='branch_analytics',
            source_column='GS',
            display_name='Grant Strength',
            data_type='numeric',
            default_agg='sum',
            aliases=['grant strength', 'gs'],
        ),
        MetricSpec(
            metric_id='NS',
            dataset_id='branch_analytics',
            source_column='NS',
            display_name='Net Strength',
            data_type='numeric',
            default_agg='sum',
            aliases=['net strength', 'ns'],
        ),
        MetricSpec(
            metric_id='STR',
            dataset_id='branch_analytics',
            source_column='STR',
            display_name='Student Teacher Ratio',
            data_type='numeric',
            default_agg='derived',
            metric_type='derived',
            aggregation_rule='derived',
            numerator_metric='NS',
            denominator_metric='SC',
            aliases=['student teacher ratio', 'str'],
        ),
        MetricSpec(
            metric_id='NOS',
            dataset_id='branch_analytics',
            source_column='NOS',
            display_name='Number of Sections',
            data_type='count',
            default_agg='sum',
            aliases=['number of sections', 'sections', 'nos'],
        ),
        MetricSpec(
            metric_id='SPS',
            dataset_id='branch_analytics',
            source_column='SPS',
            display_name='Students Per Section',
            data_type='numeric',
            default_agg='derived',
            metric_type='derived',
            aggregation_rule='derived',
            numerator_metric='NS',
            denominator_metric='NOS',
            aliases=['students per section', 'sps', 'avg-sps'],
        ),
        MetricSpec(
            metric_id='SC',
            dataset_id='branch_analytics',
            source_column='SC',
            display_name='Staff Count',
            data_type='count',
            default_agg='sum',
            aliases=['staff count', 'sc'],
        ),
        MetricSpec(
            metric_id='NOCR',
            dataset_id='branch_analytics',
            source_column='NOCR',
            display_name='Number of Class Rooms',
            data_type='count',
            default_agg='sum',
            aliases=['number of class rooms', 'nocr'],
        ),
        MetricSpec(
            metric_id='NOOR',
            dataset_id='branch_analytics',
            source_column='NOOR',
            display_name='Number of Occupied Rooms',
            data_type='count',
            default_agg='sum',
            aliases=['number of occupied rooms', 'noor'],
        ),
        MetricSpec(
            metric_id='NOVR',
            dataset_id='branch_analytics',
            source_column='NOVR',
            display_name='Number of Vacancy Rooms',
            data_type='count',
            default_agg='sum',
            aliases=['number of vacancy rooms', 'novr'],
        ),
        MetricSpec(
            metric_id='ARCS',
            dataset_id='branch_analytics',
            source_column='ARCS',
            display_name='Average Room Capacity SqFt',
            data_type='numeric',
            default_agg='mean',
            aliases=['arcs', 'average room capacity'],
        ),
        MetricSpec(
            metric_id='SD',
            dataset_id='branch_analytics',
            source_column='SD',
            display_name='Strength Difference',
            data_type='numeric',
            default_agg='sum',
            aliases=['strength difference', 'sd'],
        ),
        MetricSpec(
            metric_id='NSD',
            dataset_id='branch_analytics',
            source_column='NSD',
            display_name='Net Strength Difference',
            data_type='numeric',
            default_agg='sum',
            aliases=['net strength difference', 'nsd'],
        ),
        MetricSpec(
            metric_id='vacancy_rate',
            dataset_id='branch_analytics',
            source_column='vacancy_rate',
            display_name='Room Vacancy Percentage',
            data_type='percentage',
            default_agg='derived',
            metric_type='derived',
            aggregation_rule='derived',
            numerator_metric='NOVR',
            denominator_metric='NOCR',
            kpi_direction='negative',
            aliases=['vacancy_rate', 'vacancy rate', 'vacant rate'],
        ),
        MetricSpec(
            metric_id='occupancy_rate',
            dataset_id='branch_analytics',
            source_column='occupancy_rate',
            display_name='Room Occupancy Percentage',
            data_type='percentage',
            default_agg='derived',
            metric_type='derived',
            aggregation_rule='derived',
            numerator_metric='NOOR',
            denominator_metric='NOCR',
            aliases=['occupancy_rate', 'occupancy rate', 'occupied rate'],
        ),
    ]

    for spec in branch_specs:
        metric_registry.register(spec)

    # Revenue vs Salary Dataset metrics
    rev_sal_specs = [
        MetricSpec(
            metric_id='TOT_REV_N',
            dataset_id='revenue_vs_salary',
            source_column='TOT_REV_N',
            display_name='Total Net Revenue',
            data_type='currency',
            default_agg='sum',
            aliases=['revenue', 'net revenue', 'total revenue', 'total net revenue', 'tot_rev_n', 'income', 'earnings'],
        ),
        MetricSpec(
            metric_id='TOT_SAL',
            dataset_id='revenue_vs_salary',
            source_column='TOT_SAL',
            display_name='Total Employee Salary Cost',
            data_type='currency',
            default_agg='sum',
            aliases=['salary', 'salary cost', 'total salary', 'employee cost', 'tot_sal', 'staff cost'],
        ),
        MetricSpec(
            metric_id='TOT_NS',
            dataset_id='revenue_vs_salary',
            source_column='TOT_NS',
            display_name='Total Student Count',
            data_type='count',
            default_agg='sum',
            aliases=['total students', 'student count', 'total student count', 'tot_ns'],
        ),
        MetricSpec(
            metric_id='TOT_SC',
            dataset_id='revenue_vs_salary',
            source_column='TOT_SC',
            display_name='Total Employee Count',
            data_type='count',
            default_agg='sum',
            aliases=['total employees', 'employee count', 'total employee count', 'tot_sc', 'total staff count'],
        ),
        MetricSpec(
            metric_id='TOT_FA',
            dataset_id='revenue_vs_salary',
            source_column='TOT_FA',
            display_name='Total Fee Average',
            data_type='currency',
            default_agg='derived',
            metric_type='derived',
            aggregation_rule='derived',
            numerator_metric='TOT_REV_N',
            denominator_metric='TOT_NS',
            aliases=['fee average', 'average fee', 'total fee average', 'tot_fa'],
        ),
        MetricSpec(
            metric_id='TOT_CS',
            dataset_id='revenue_vs_salary',
            source_column='TOT_CS',
            display_name='Total Cost per Student',
            data_type='currency',
            default_agg='derived',
            metric_type='derived',
            aggregation_rule='derived',
            numerator_metric='TOT_SAL',
            denominator_metric='TOT_NS',
            aliases=['cost per student', 'total cost per student', 'tot_cs', 'student cost'],
        ),
        MetricSpec(
            metric_id='TOT_SAL_V_REV',
            dataset_id='revenue_vs_salary',
            source_column='TOT_SAL_V_REV',
            display_name='Total Salary vs Revenue %',
            data_type='percentage',
            default_agg='derived',
            metric_type='derived',
            aggregation_rule='derived',
            numerator_metric='TOT_SAL',
            denominator_metric='TOT_REV_N',
            kpi_direction='negative',
            aliases=['salary vs revenue', 'salary-to-revenue ratio', 'salary percentage', 'tot_sal_v_rev', 'salary burden'],
        ),
        MetricSpec(
            metric_id='TOT_STR',
            dataset_id='revenue_vs_salary',
            source_column='TOT_STR',
            display_name='Total Student Teacher Ratio',
            data_type='numeric',
            default_agg='derived',
            metric_type='derived',
            aggregation_rule='derived',
            numerator_metric='TOT_NS',
            denominator_metric='TOT_SC',
            aliases=['student teacher ratio', 'total student teacher ratio', 'tot_str', 'student-staff ratio'],
        ),
        MetricSpec(
            metric_id='SURPLUS',
            dataset_id='revenue_vs_salary',
            source_column='SURPLUS',
            display_name='Surplus after Salary',
            data_type='currency',
            default_agg='sum',
            aliases=['surplus', 'surplus after salary', 'revenue minus salary', 'revenue after salary', 'net surplus'],
        ),
    ]

    for spec in rev_sal_specs:
        metric_registry.register(spec)

    segments = ['PP', 'LPS', 'UPS', 'HS', 'ACD', 'AD_AC']
    suffixes = [
        ('SC', 'Employee Count', 'count'),
        ('SAL', 'Employee Cost', 'currency'),
        ('NS', 'Student Count', 'count'),
        ('REV_N', 'Net Revenue', 'currency'),
        ('FA', 'Fee Average', 'currency'),
        ('CS', 'Cost per Student', 'currency'),
        ('SAL_V_REV', 'Salary vs Revenue %', 'percentage'),
        ('STR', 'Student Teacher Ratio', 'numeric'),
    ]

    for seg in segments:
        for sfx, lbl, dtype in suffixes:
            metric_id = f"{seg}_{sfx}"
            is_derived = sfx in ('FA', 'CS', 'SAL_V_REV', 'STR')
            num_m = None
            den_m = None
            if sfx == 'FA':
                num_m, den_m = f"{seg}_REV_N", f"{seg}_NS"
            elif sfx == 'CS':
                num_m, den_m = f"{seg}_SAL", f"{seg}_NS"
            elif sfx == 'SAL_V_REV':
                num_m, den_m = f"{seg}_SAL", f"{seg}_REV_N"
            elif sfx == 'STR':
                num_m, den_m = f"{seg}_NS", f"{seg}_SC"

            metric_registry.register(MetricSpec(
                metric_id=metric_id,
                dataset_id='revenue_vs_salary',
                source_column=metric_id,
                display_name=f"{seg} {lbl}",
                data_type=dtype,
                default_agg='derived' if is_derived else ('sum' if dtype in ('currency', 'count') else 'mean'),
                metric_type='derived' if is_derived else 'additive',
                aggregation_rule='derived' if is_derived else 'sum',
                numerator_metric=num_m,
                denominator_metric=den_m,
                kpi_direction='negative' if sfx in ('SAL_V_REV',) else 'positive',
                aliases=[metric_id.lower(), f"{seg.lower()} {lbl.lower()}"],
            ))



register_default_metrics()
