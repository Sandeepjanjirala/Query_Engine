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
        aliases=['fee due', '2025-26 live student fee due', 'live student fee due', 'current year fee due', 'live student due', 'cy_a_fd'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='LY_FD',
        dataset_id='fee_analysis',
        source_column='LY_FD',
        display_name='2024-25 Fee Due',
        data_type='currency',
        default_agg='sum',
        aliases=['last year fee due', '2024-25 fee due', 'ly fee due', 'ly_fd'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='CY_A_FDC',
        dataset_id='fee_analysis',
        source_column='CY_A_FDC',
        display_name='2025-26 Live Student Due Count',
        data_type='count',
        default_agg='sum',
        aliases=['2025-26 due count', 'current year due count', 'live student due count', 'due count', '2025-26 live student due count', 'cy_a_fdc'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='LY_FDC',
        dataset_id='fee_analysis',
        source_column='LY_FDC',
        display_name='2024-25 Fee Due Count',
        data_type='count',
        default_agg='sum',
        aliases=['last year due count', '2024-25 fee due count', 'ly fee due count', 'ly due count', 'ly_fdc'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='CY_A_ZP',
        dataset_id='fee_analysis',
        source_column='CY_A_ZP',
        display_name='2025-26 Actual Zero Paid',
        data_type='count',
        default_agg='sum',
        aliases=['2025-26 actual zero paid', 'actual zero paid', 'zero paid', 'cy_a_zp'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='CY_ZP',
        dataset_id='fee_analysis',
        source_column='CY_ZP',
        display_name='2025-26 Actual Zero Paid Count',
        data_type='count',
        default_agg='sum',
        aliases=['cy zero paid count', 'zero paid count', 'actual zero paid count', 'cy_zp'],
    ))

    metric_registry.register(MetricSpec(
        metric_id='CY_ZP_FD',
        dataset_id='fee_analysis',
        source_column='CY_ZP_FD',
        display_name='Current Year Zero Paid Fee Due',
        data_type='currency',
        default_agg='sum',
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
    branch_metrics = [
        ('DPP', 'Dropouts Percentage', 'percentage', 'mean', ['dropout percentage', 'dpp', 'dropout %']),
        ('DP', 'Dropouts', 'count', 'sum', ['dropouts', 'dropout count', 'dp']),
        ('GS', 'Grant Strength', 'numeric', 'sum', ['grant strength', 'gs']),
        ('NS', 'Net Strength', 'numeric', 'sum', ['net strength', 'ns']),
        ('STR', 'Student Teacher Ratio', 'numeric', 'mean', ['student teacher ratio', 'str']),
        ('NOS', 'Number of Sections', 'count', 'sum', ['number of sections', 'sections', 'nos']),
        ('SPS', 'Students Per Section', 'numeric', 'mean', ['students per section', 'sps', 'avg-sps']),
        ('SC', 'Staff Count', 'count', 'sum', ['staff count', 'sc']),
        ('NOCR', 'Number of Class Rooms', 'count', 'sum', ['number of class rooms', 'nocr']),
        ('NOOR', 'Number of Occupied Rooms', 'count', 'sum', ['number of occupied rooms', 'noor']),
        ('NOVR', 'Number of Vacancy Rooms', 'count', 'sum', ['number of vacancy rooms', 'novr']),
        ('ARCS', 'Average Room Capacity SqFt', 'numeric', 'mean', ['arcs', 'average room capacity']),
        ('SD', 'Strength Difference', 'numeric', 'sum', ['strength difference', 'sd']),
        ('NSD', 'Net Strength Difference', 'numeric', 'sum', ['net strength difference', 'nsd']),
        ('vacancy_rate', 'Room Vacancy Percentage', 'percentage', 'mean', ['vacancy_rate', 'vacancy rate', 'vacant rate']),
        ('occupancy_rate', 'Room Occupancy Percentage', 'percentage', 'mean', ['occupancy_rate', 'occupancy rate', 'occupied rate']),
    ]


    for m_id, name, dtype, agg, aliases in branch_metrics:
        metric_registry.register(MetricSpec(
            metric_id=m_id,
            dataset_id='branch_analytics',
            source_column=m_id,
            display_name=name,
            data_type=dtype,
            default_agg=agg,
            aliases=aliases,
        ))


register_default_metrics()
