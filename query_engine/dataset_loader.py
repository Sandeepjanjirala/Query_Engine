from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
import pandas as pd

from .dataset_registry import DatasetSpec, get_default_registry


_DATASET_CACHE: Dict[str, pd.DataFrame] = {}


def clear_dataset_cache():
    _DATASET_CACHE.clear()


from django.conf import settings


def load_dataset_from_spec(spec: DatasetSpec) -> pd.DataFrame:
    """Load a dataset DataFrame based on its DatasetSpec."""
    file_path = Path(spec.file_path)
    if spec.dataset_id == 'branch_analytics' and hasattr(settings, 'BRANCH_ANALYTICS_FILE'):
        file_path = Path(settings.BRANCH_ANALYTICS_FILE)
    elif spec.dataset_id == 'fee_analysis' and hasattr(settings, 'FEE_DUE_FILE'):
        file_path = Path(settings.FEE_DUE_FILE)

    if not file_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {file_path}")


    # Inspect available sheets and read dataframe cleanly
    with open(file_path, 'rb') as f:
        xl = pd.ExcelFile(f)
        available_sheets = xl.sheet_names

        # Determine which sheet to load
        target_sheet = spec.sheet_name
        if target_sheet not in available_sheets:
            # Fallback logic for fee due or branch analytics if target sheet isn't named exactly as spec
            valid_sheets = [s for s in available_sheets if s.strip().upper() != 'TS']
            if not valid_sheets:
                raise ValueError(f"No valid analytical sheet found in {file_path}")
            target_sheet = valid_sheets[0]

        # Explicit check: Never load 'TS'
        if target_sheet.strip().upper() == 'TS':
            raise ValueError("TS sheet is forbidden for analytical query engine use.")

        df = pd.read_excel(f, sheet_name=target_sheet)

    df = df.copy()

    # Canonical dimension column mapping & normalization
    # Standardize column headers for common dimensions
    col_map = {
        'AGM Name': 'AGM',
        'AGM_Name': 'AGM',
        'RI Name': 'RI',
        'RI_Name': 'RI',
        'Branch Name': 'Branch',
        'Branch_Name': 'Branch',
    }
    
    # Apply column aliases
    for old_col, new_col in col_map.items():
        if old_col in df.columns and new_col not in df.columns:
            df[new_col] = df[old_col]

    # Ensure whitespace trimming on canonical text columns
    for dim_col in ['AGM', 'RI', 'Zone', 'Branch', 'AGM Name', 'RI Name', 'Branch']:
        if dim_col in df.columns:
            df[dim_col] = df[dim_col].astype('string').str.strip()

    return df


def load_dataset(dataset_id: str, force_reload: bool = False) -> pd.DataFrame:
    """Lazy load a registered dataset by ID with process-level caching."""
    if not force_reload and dataset_id in _DATASET_CACHE:
        return _DATASET_CACHE[dataset_id].copy()

    registry = get_default_registry()
    spec = registry.get(dataset_id)
    if not spec:
        raise ValueError(f"Unknown dataset_id: {dataset_id}")

    df = load_dataset_from_spec(spec)
    _DATASET_CACHE[dataset_id] = df
    return df.copy()
