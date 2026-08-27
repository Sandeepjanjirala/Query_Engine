from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd

from .dataset_loader import load_dataset
from .filters import apply_filter_context
from .join_engine import join_datasets
from .metric_registry import get_default_metric_registry


@dataclass
class QueryPlan:
    dataset_ids: List[str]
    primary_dataset_id: str
    metric_ids: List[str]
    group_dimension: Optional[str] = None
    filters: Dict[str, str] = field(default_factory=dict)
    operation: Optional[str] = None


def resolve_required_datasets(metric_ids: List[str]) -> Tuple[str, List[str]]:
    """
    Given a list of metric IDs or column names, return (primary_dataset_id, secondary_dataset_ids).
    Default primary dataset is 'branch_analytics'.
    """
    metric_registry = get_default_metric_registry()
    dataset_ids = []
    
    for m in metric_ids:
        spec = metric_registry.get(m)
        if spec:
            ds = spec.dataset_id
            if ds not in dataset_ids:
                dataset_ids.append(ds)
        else:
            # Fallback check if it's in fee_analysis or branch_analytics
            if m in ('CY_A_FD', 'LY_FD', 'CY_A_FDC', 'LY_FDC', 'CY_A_ZP', 'CY_ZP', 'CY_ZP_FD', 'CY_FP_BN', 'CY_FN_BN'):
                if 'fee_analysis' not in dataset_ids:
                    dataset_ids.append('fee_analysis')
            else:
                if 'branch_analytics' not in dataset_ids:
                    dataset_ids.append('branch_analytics')

    if not dataset_ids:
        dataset_ids = ['branch_analytics']

    primary_id = dataset_ids[0]
    secondary_ids = dataset_ids[1:]
    return primary_id, secondary_ids


def get_prepared_dataframe(
    metric_ids: List[str],
    context: Optional[dict] = None,
    primary_dataset_id: Optional[str] = None,
) -> pd.DataFrame:
    """
    Prepare and return a DataFrame containing only the required dataset(s).
    Applies common dashboard filters to each dataset prior to joining.
    """
    if primary_dataset_id is None:
        p_id, sec_ids = resolve_required_datasets(metric_ids)
    else:
        p_id = primary_dataset_id
        _, all_sec = resolve_required_datasets(metric_ids)
        sec_ids = [s for s in all_sec if s != p_id]

    # 1. Load primary dataset
    primary_df = load_dataset(p_id)
    # Apply filter context before join
    primary_df = apply_filter_context(primary_df, context)

    # 2. Single dataset case: Load ONLY required dataset!
    if not sec_ids:
        return primary_df

    # 3. Multi-dataset case: Load secondary datasets & apply filter context to each
    secondary_dfs = []
    for sec_id in sec_ids:
        sec_df = load_dataset(sec_id)
        sec_df = apply_filter_context(sec_df, context)
        secondary_dfs.append(sec_df)

    # 4. Join datasets using common dimensions
    combined_df = join_datasets(primary_df, secondary_dfs)
    return combined_df
