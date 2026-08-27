from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from django.conf import settings


@dataclass
class DatasetSpec:
    dataset_id: str
    file_path: Path
    sheet_name: str
    common_dimensions: List[str] = field(default_factory=lambda: ['AGM', 'RI', 'Zone', 'Branch'])
    column_mapping: Dict[str, str] = field(default_factory=dict)
    metrics: List[str] = field(default_factory=list)
    description: str = ""


class DatasetRegistry:
    def __init__(self):
        self._registry: Dict[str, DatasetSpec] = {}

    def register(self, spec: DatasetSpec) -> None:
        self._registry[spec.dataset_id] = spec

    def get(self, dataset_id: str) -> Optional[DatasetSpec]:
        return self._registry.get(dataset_id)

    def list_datasets(self) -> List[str]:
        return list(self._registry.keys())

    def find_datasets_for_metrics(self, metric_ids: List[str]) -> List[str]:
        """Find unique dataset IDs containing the given metric IDs."""
        dataset_ids = []
        for m in metric_ids:
            for spec in self._registry.values():
                if m in spec.metrics or m in spec.column_mapping:
                    if spec.dataset_id not in dataset_ids:
                        dataset_ids.append(spec.dataset_id)
        return dataset_ids


# Global dataset registry instance
registry = DatasetRegistry()
_INITIALIZED = False


def get_default_registry() -> DatasetRegistry:
    global _INITIALIZED
    if not _INITIALIZED:
        register_default_datasets()
        _INITIALIZED = True
    return registry


def register_default_datasets():
    """Register the built-in datasets: branch_analytics and fee_analysis."""
    base_dir = getattr(settings, 'BASE_DIR', Path('.'))
    
    branch_file = getattr(settings, 'BRANCH_ANALYTICS_FILE', base_dir / 'data' / 'branch_analytics.xlsx')
    branch_sheet = getattr(settings, 'BRANCH_ANALYTICS_SHEET', 'Sheet1')
    
    fee_file = getattr(settings, 'FEE_DUE_FILE', base_dir / 'data' / 'fee due.xlsx')
    fee_sheet = getattr(settings, 'FEE_DUE_SHEET', 'Anys_fee_due_data')

    registry.register(
        DatasetSpec(
            dataset_id='branch_analytics',
            file_path=Path(branch_file),
            sheet_name=branch_sheet,
            common_dimensions=['AGM', 'RI', 'Zone', 'Branch'],
            column_mapping={
                'AGM Name': 'AGM',
                'RI Name': 'RI',
                'Zone': 'Zone',
                'Branch': 'Branch',
            },
            description='Branch dropout, strength, staff, and room utilization dataset',
        )
    )

    registry.register(
        DatasetSpec(
            dataset_id='fee_analysis',
            file_path=Path(fee_file),
            sheet_name=fee_sheet,
            common_dimensions=['AGM', 'RI', 'Zone', 'Branch'],
            column_mapping={
                'AGM_Name': 'AGM',
                'AGM Name': 'AGM',
                'RI_Name': 'RI',
                'RI Name': 'RI',
                'Zone': 'Zone',
                'Branch': 'Branch',
                'Branch Name': 'Branch',
                'S_Type': 'Branch Type',
                'LY_FD': '2024-25 Fee Due',
                'LY_FDC': '2024-25 Fee Due Count',
                'CY_A_FD': '2025-26 Live Student Fee Due',
                'CY_A_FDC': '2025-26 Live Student Due Count',
                'CY_A_ZP': '2025-26 Actual Zero Paid',
                'CY_ZP': '2025-26 Actual Zero Paid Count',
                'CY_ZP_FD': 'Current Year Zero Paid Fee Due',
                'CY_FP_BN': 'Fee Paid But Books Not Purchased',
                'CY_FN_BN': 'Fee Not Paid & Books Not Purchased',
            },
            metrics=[
                'LY_FD', 'LY_FDC', 'CY_A_FD', 'CY_A_FDC',
                'CY_A_ZP', 'CY_ZP', 'CY_ZP_FD', 'CY_FP_BN', 'CY_FN_BN'
            ],
            description='Fee Due, Zero Paid, and Books Not Purchased dataset',
        )
    )

