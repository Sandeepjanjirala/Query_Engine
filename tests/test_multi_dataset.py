from pathlib import Path
import tempfile

import pandas as pd
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from query_engine.dataset_loader import clear_dataset_cache, load_dataset
from query_engine.dataset_registry import DatasetSpec, DatasetRegistry
from query_engine.join_engine import join_datasets
from query_engine.metric_registry import get_default_metric_registry
from query_engine.orchestrator import clear_caches
from query_engine.query_planner import get_prepared_dataframe, resolve_required_datasets
from query_engine.router import route_question
from query_engine.views import QueryView


class MultiDatasetEngineTests(SimpleTestCase):
    def setUp(self):
        clear_caches()
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.branch_path = Path(self.tmp_dir.name) / 'branch_analytics.xlsx'
        self.fee_path = Path(self.tmp_dir.name) / 'fee_due.xlsx'

        # Create primary dataset (branch analytics)
        df_branch = pd.DataFrame({
            'AGM Name': ['AGM 1', 'AGM 1', 'AGM 2'],
            'RI Name': ['RI 1', 'RI 1', 'RI 2'],
            'Zone': ['Zone 1', 'Zone 1', 'Zone 2'],
            'Branch': ['KAKINADA 1', 'KAKINADA 2', 'KAKINADA 3'],  # KAKINADA 3 is only in primary
            'CY-DPP': [10.5, 20.0, 5.0],
            'CY-NS': [100, 150, 200],
        })
        with pd.ExcelWriter(self.branch_path, engine='openpyxl') as writer:
            df_branch.to_excel(writer, sheet_name='Sheet1', index=False)

        # Create secondary dataset (fee due) with multi-sheet workbook (Anys_fee_due_data + TS)
        df_fee = pd.DataFrame({
            'AGM_Name': ['AGM 1', '  kakinada 2  '],
            'RI_Name': ['RI 1', 'RI 1'],
            'Zone': ['Zone 1', 'Zone 1'],
            'Branch': ['KAKINADA 1', 'KAKINADA 2'],
            'S_Type': ['Existing', 'New'],
            'LY_FD': [4000, 6000],
            'LY_FDC': [8, 12],
            'CY_A_FD': [5000, 8000],
            'CY_A_FDC': [10, 15],
            'CY_A_ZP': [2, 5],
            'CY_ZP': [2, 5],
            'CY_ZP_FD': [1000, 2000],
            'CY_FP_BN': [3, 4],
            'CY_FN_BN': [1, 2],
        })
        df_ts = pd.DataFrame({'TS_Col': [1, 2, 3]})

        with pd.ExcelWriter(self.fee_path, engine='openpyxl') as writer:
            df_fee.to_excel(writer, sheet_name='Anys_fee_due_data', index=False)
            df_ts.to_excel(writer, sheet_name='TS', index=False)

    def tearDown(self):
        clear_caches()
        self.tmp_dir.cleanup()

    def test_1_dataset_registry_definition(self):
        reg = DatasetRegistry()
        spec = DatasetSpec(
            dataset_id='test_ds',
            file_path=self.fee_path,
            sheet_name='Anys_fee_due_data',
            common_dimensions=['AGM', 'RI', 'Zone', 'Branch'],
            metrics=['CY_A_FD', 'CY_ZP_FD'],
        )
        reg.register(spec)
        self.assertEqual(reg.get('test_ds').dataset_id, 'test_ds')
        self.assertIn('test_ds', reg.list_datasets())

    @override_settings(BRANCH_ANALYTICS_FILE=PropertyMock if False else None)
    def test_2_explicit_sheet_selection_and_ignore_ts(self):
        with override_settings(FEE_DUE_FILE=self.fee_path):
            df = load_dataset('fee_analysis', force_reload=True)
            self.assertIn('CY_A_FD', df.columns)
            self.assertNotIn('TS_Col', df.columns)

    def test_3_canonical_column_mapping(self):
        with override_settings(FEE_DUE_FILE=self.fee_path):
            df = load_dataset('fee_analysis', force_reload=True)
            self.assertIn('AGM', df.columns)
            self.assertIn('RI', df.columns)
            self.assertIn('Branch', df.columns)

    def test_4_metric_resolution_fee_metrics(self):
        reg = get_default_metric_registry()
        self.assertEqual(reg.get('fee due').metric_id, 'CY_A_FD')
        self.assertEqual(reg.get('last year fee due').metric_id, 'LY_FD')
        self.assertEqual(reg.get('last year due count').metric_id, 'LY_FDC')
        self.assertEqual(reg.get('2025-26 due count').metric_id, 'CY_A_FDC')
        self.assertEqual(reg.get('actual zero paid').metric_id, 'CY_A_ZP')
        self.assertEqual(reg.get('zero paid count').metric_id, 'CY_ZP')
        self.assertEqual(reg.get('current year zero paid fee due').metric_id, 'CY_ZP_FD')
        self.assertEqual(reg.get('fee paid but books not purchased').metric_id, 'CY_FP_BN')
        self.assertEqual(reg.get('fee not paid and books not purchased').metric_id, 'CY_FN_BN')

    def test_5_single_dataset_resolution(self):
        p_id, sec_ids = resolve_required_datasets(['CY_A_FD'])
        self.assertEqual(p_id, 'fee_analysis')
        self.assertEqual(sec_ids, [])

    def test_6_multi_dataset_resolution(self):
        p_id, sec_ids = resolve_required_datasets(['CY-DPP', 'CY_A_FD'])
        self.assertIn(p_id, ['branch_analytics', 'fee_analysis'])
        self.assertEqual(len(sec_ids), 1)

    def test_7_left_join_preserves_primary_and_handles_missing_rows(self):
        with override_settings(BRANCH_ANALYTICS_FILE=self.branch_path, FEE_DUE_FILE=self.fee_path):
            df = get_prepared_dataframe(['CY-DPP', 'CY_A_FD'])
            # Branch KAKINADA 3 exists in primary but not secondary
            self.assertEqual(len(df), 3)
            branches = df['Branch'].tolist()
            self.assertIn('KAKINADA 3', branches)
            row3 = df[df['Branch'] == 'KAKINADA 3'].iloc[0]
            self.assertTrue(pd.isna(row3['CY_A_FD']))

    def test_8_dashboard_filter_propagation(self):
        with override_settings(BRANCH_ANALYTICS_FILE=self.branch_path, FEE_DUE_FILE=self.fee_path):
            context = {'agm': 'AGM 1'}
            df = get_prepared_dataframe(['CY-DPP', 'CY_A_FD'], context=context)
            self.assertEqual(len(df), 2)
            self.assertTrue((df['AGM'] == 'AGM 1').all())

    def test_9_unknown_metric_rejection(self):
        handler = route_question('What is the xyz_unsupported_metric of branch?')
        self.assertIsNone(handler)

    def test_10_api_fee_due_query(self):
        with override_settings(BRANCH_ANALYTICS_FILE=self.branch_path, FEE_DUE_FILE=self.fee_path):
            request = APIRequestFactory().post('/api/query/', {
                'question': 'Show top 2 branches by fee due'
            }, format='json')
            response = QueryView.as_view()(request)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data['success'])
            self.assertEqual(response.data['function'], 'rank_branches_by_metric')
            self.assertEqual(len(response.data['data']), 2)
            self.assertEqual(response.data['data'][0]['branch'], 'KAKINADA 2')
            self.assertEqual(response.data['data'][0]['value'], 8000.0)

    def test_11_api_zero_paid_fee_due_query(self):
        with override_settings(BRANCH_ANALYTICS_FILE=self.branch_path, FEE_DUE_FILE=self.fee_path):
            request = APIRequestFactory().post('/api/query/', {
                'question': 'Show branches by current year zero paid fee due'
            }, format='json')
            response = QueryView.as_view()(request)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data['success'])
            self.assertEqual(response.data['data'][0]['branch'], 'KAKINADA 2')
            self.assertEqual(response.data['data'][0]['value'], 2000.0)

    def test_12_books_not_purchased_query(self):
        with override_settings(BRANCH_ANALYTICS_FILE=self.branch_path, FEE_DUE_FILE=self.fee_path):
            request = APIRequestFactory().post('/api/query/', {
                'question': 'Show branches with fee paid but books not purchased'
            }, format='json')
            response = QueryView.as_view()(request)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data['success'])
            self.assertEqual(response.data['data'][0]['branch'], 'KAKINADA 2')
            self.assertEqual(response.data['data'][0]['value'], 4.0)
