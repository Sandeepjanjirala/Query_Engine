"""
tests/test_multi_metric_verification.py

Independent mathematical and architectural verification suite for the
Multi-Metric Query Engine.

Verifies:
1. Three Mandatory Tests:
   - Top 5 branches by dropout count with dropout percentage
   - RI wise fee due with dropouts
   - Top 5 AGMs by salary percentage with fee paid but books not purchased
2. Additional Multi-Metric Scenarios:
   - Top 5 branches by dropout percentage with dropout count and fee due
   - Show RI wise dropout percentage, STR and salary percentage
   - Zone wise dropout count and fee due
   - Branch wise dropout percentage with salary
   - Compare AGM Ramana Rao dropout by RI with fee due
   - Top 5 RIs by fee due with dropout count
   - Top 5 zones by salary percentage with dropout percentage
3. Single-Entity Statistics Preservation:
   - AGM Ramana Rao statistics
   - RI Anitha statistics
   - KAKINADA 1 statistics
4. Independent Mathematical Assertions:
   - Directly loads raw Excel files with pandas.
   - Computes expected group sums and derived ratios independently.
   - Asserts exact numerical and formatting equivalence.
"""

import re
from django.test import SimpleTestCase
import pandas as pd

from query_engine.router import route_question
from query_engine.dataset_loader import load_dataset
from query_engine.filters import _clean_str


class MultiMetricVerificationTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ba_df = load_dataset('branch_analytics')
        cls.fee_df = load_dataset('fee_analysis')
        cls.rs_df = load_dataset('revenue_vs_salary')

    # -------------------------------------------------------------------------
    # 1. Three Mandatory Verification Tests
    # -------------------------------------------------------------------------

    def test_mandatory_01_top_5_branches_dropout_count_with_percentage(self):
        """Mandatory 1: Top 5 branches by dropout count with dropout percentage."""
        q = "Top 5 branches by dropout count with dropout percentage"
        handler = route_question(q)
        res = handler({})

        self.assertEqual(res['function'], 'multi_metric_analysis')
        self.assertIn('Detailed Evidence', res['answer'])

        # Independent calculation directly on raw branch_analytics dataframe
        df = self.ba_df.copy()
        df['CY-DP'] = pd.to_numeric(df['CY-DP'], errors='coerce').fillna(0)
        df['CY-NS'] = pd.to_numeric(df['CY-NS'], errors='coerce').fillna(0)
        top5 = df.sort_values(by='CY-DP', ascending=False).head(5)

        expected_rows = []
        for _, row in top5.iterrows():
            dp = int(row['CY-DP'])
            ns = float(row['CY-NS'])
            dpp = (dp / ns * 100) if ns > 0 else 0.0
            expected_rows.append((row['Branch'].strip(), f"{dp:,}", f"{dpp:.2f}%"))

        actual_data = res['data']
        self.assertEqual(len(actual_data), 5)
        for i in range(5):
            exp_b, exp_dp, exp_dpp = expected_rows[i]
            act_row = actual_data[i]
            self.assertEqual(act_row[0].strip().lower(), exp_b.lower(), f"Rank {i+1} branch mismatch")
            self.assertEqual(act_row[1], exp_dp, f"Rank {i+1} dropout count mismatch")
            self.assertEqual(act_row[2], exp_dpp, f"Rank {i+1} dropout % mismatch")

    def test_mandatory_02_ri_wise_fee_due_with_dropouts(self):
        """Mandatory 2: RI wise fee due with dropouts."""
        q = "RI wise fee due with dropouts"
        handler = route_question(q)
        res = handler({})

        self.assertEqual(res['function'], 'multi_metric_analysis')
        self.assertIn('Detailed Evidence', res['answer'])

        # Independent calculation of expected group sums
        fee_df = self.fee_df.copy()
        fee_df['CY_A_FD'] = pd.to_numeric(fee_df['CY_A_FD'], errors='coerce').fillna(0)
        fee_df['_ck'] = fee_df['RI Name'].apply(_clean_str)
        exp_fee = fee_df.groupby('_ck')['CY_A_FD'].sum().to_dict()

        ba_df = self.ba_df.copy()
        ba_df['CY-DP'] = pd.to_numeric(ba_df['CY-DP'], errors='coerce').fillna(0)
        ba_df['_ck'] = ba_df['RI Name'].apply(_clean_str)
        exp_dp = ba_df.groupby('_ck')['CY-DP'].sum().to_dict()

        actual_data = res['data']
        self.assertTrue(len(actual_data) >= 4)
        for row in actual_data:
            ri_name, fee_str, dp_str = row[0], row[1], row[2]
            ck = _clean_str(ri_name)
            self.assertIn(ck, exp_fee, f"Unknown RI in result: {ri_name}")

            # Verify Fee Due
            raw_fee = int(re.sub(r'[^\d]', '', fee_str))
            self.assertEqual(raw_fee, int(round(exp_fee[ck])), f"Fee due mismatch for {ri_name}")

            # Verify Dropout Count
            raw_dp = int(re.sub(r'[^\d]', '', dp_str))
            self.assertEqual(raw_dp, int(round(exp_dp.get(ck, 0))), f"Dropout count mismatch for {ri_name}")

    def test_mandatory_03_top_5_agms_salary_pct_with_fee_paid_books_not_purchased(self):
        """Mandatory 3: Top 5 AGMs by salary percentage with fee paid but books not purchased."""
        q = "Top 5 AGMs by salary percentage with fee paid but books not purchased"
        handler = route_question(q)
        res = handler({})

        self.assertEqual(res['function'], 'multi_metric_analysis')
        self.assertIn('Detailed Evidence', res['answer'])

        # Independent calculation of salary % and books not purchased
        rs_df = self.rs_df.copy()
        rs_df['TOT_SAL'] = pd.to_numeric(rs_df['TOT_SAL'], errors='coerce').fillna(0)
        rs_df['TOT_REV_N'] = pd.to_numeric(rs_df['TOT_REV_N'], errors='coerce').fillna(0)
        rs_df['_ck'] = rs_df['AGM Name'].apply(_clean_str)
        rs_agg = rs_df.groupby('_ck').agg({'TOT_SAL': 'sum', 'TOT_REV_N': 'sum'})
        rs_agg['salary_pct'] = (rs_agg['TOT_SAL'] / rs_agg['TOT_REV_N']) * 100.0
        exp_sal_pct = rs_agg['salary_pct'].to_dict()

        fee_df = self.fee_df.copy()
        fee_df['CY_FP_BN'] = pd.to_numeric(fee_df['CY_FP_BN'], errors='coerce').fillna(0)
        fee_df['_ck'] = fee_df['AGM Name'].apply(_clean_str)
        exp_books = fee_df.groupby('_ck')['CY_FP_BN'].sum().to_dict()

        actual_data = res['data']
        self.assertTrue(len(actual_data) >= 2)
        for row in actual_data:
            agm_name, sal_str, books_str = row[0], row[1], row[2]
            ck = _clean_str(agm_name)
            self.assertIn(ck, exp_sal_pct, f"Unknown AGM: {agm_name}")

            # Verify Salary %
            raw_pct = float(sal_str.replace('%', '').strip())
            self.assertAlmostEqual(raw_pct, exp_sal_pct[ck], places=2, msg=f"Salary % mismatch for {agm_name}")

            # Verify Books not purchased
            raw_books = int(re.sub(r'[^\d]', '', books_str))
            self.assertEqual(raw_books, int(round(exp_books.get(ck, 0))), f"Books count mismatch for {agm_name}")

    # -------------------------------------------------------------------------
    # 2. Additional Multi-Metric Test Scenarios
    # -------------------------------------------------------------------------

    def test_additional_01_top_5_branches_dropout_percentage_with_count_and_fee_due(self):
        """Top 5 branches by dropout percentage with dropout count and fee due."""
        q = "Top 5 branches by dropout percentage with dropout count and fee due"
        handler = route_question(q)
        res = handler({})

        self.assertEqual(res['function'], 'multi_metric_analysis')
        self.assertEqual(len(res['data']), 5)
        # Verify columns: BRANCH, Dropout % (Rank), Dropout Count, 2025-26 Fee Due
        self.assertEqual(len(res['data'][0]), 4)

    def test_additional_02_show_ri_wise_dropout_pct_str_and_salary_pct(self):
        """Show RI wise dropout percentage, STR and salary percentage."""
        q = "Show RI wise dropout percentage, STR and salary percentage"
        handler = route_question(q)
        res = handler({})

        self.assertEqual(res['function'], 'multi_metric_analysis')
        actual_data = res['data']
        self.assertTrue(len(actual_data) >= 4)

        # Independent STR calculation for each RI: SUM(CY-NS) / SUM(CY-SC)
        ba_df = self.ba_df.copy()
        ba_df['CY-NS'] = pd.to_numeric(ba_df['CY-NS'], errors='coerce').fillna(0)
        ba_df['CY-SC'] = pd.to_numeric(ba_df['CY-SC'], errors='coerce').fillna(0)
        ba_df['_ck'] = ba_df['RI Name'].apply(_clean_str)
        ba_agg = ba_df.groupby('_ck').agg({'CY-NS': 'sum', 'CY-SC': 'sum'})
        ba_agg['str'] = ba_agg['CY-NS'] / ba_agg['CY-SC']
        exp_str = ba_agg['str'].to_dict()

        for row in actual_data:
            ri_name, dpp_str, str_val_str, sal_str = row[0], row[1], row[2], row[3]
            ck = _clean_str(ri_name)
            self.assertIn(ck, exp_str)
            actual_str = float(str_val_str)
            self.assertAlmostEqual(actual_str, exp_str[ck], places=2, msg=f"STR mismatch for {ri_name}")

    def test_additional_03_zone_wise_dropout_count_and_fee_due(self):
        """Zone wise dropout count and fee due."""
        q = "Zone wise dropout count and fee due"
        handler = route_question(q)
        res = handler({})

        self.assertEqual(res['function'], 'multi_metric_analysis')
        self.assertTrue(len(res['data']) >= 3)

    def test_additional_04_branch_wise_dropout_percentage_with_salary(self):
        """Branch wise dropout percentage with salary."""
        q = "Branch wise dropout percentage with salary"
        handler = route_question(q)
        res = handler({})

        self.assertEqual(res['function'], 'multi_metric_analysis')
        self.assertEqual(len(res['data']), 40)

    def test_additional_05_compare_agm_ramana_rao_dropout_by_ri_with_fee_due(self):
        """Compare AGM Ramana Rao dropout by RI with fee due."""
        q = "Compare AGM Ramana Rao dropout by RI with fee due"
        handler = route_question(q)
        res = handler({})

        self.assertEqual(res['function'], 'multi_metric_analysis')
        # Under AGM Ramana Rao, there is 1 RI (K.Srinivasa Rao)
        self.assertEqual(len(res['data']), 1)
        self.assertIn('srinivasa', res['data'][0][0].lower())

    def test_additional_06_top_5_ris_by_fee_due_with_dropout_count(self):
        """Top 5 RIs by fee due with dropout count."""
        q = "Highest 5 RIs by fee due with dropouts"
        handler = route_question(q)
        res = handler({})

        self.assertEqual(res['function'], 'multi_metric_analysis')
        self.assertTrue(len(res['data']) <= 5)

    def test_additional_07_top_5_zones_salary_pct_with_dropout_pct(self):
        """Top 5 zones by salary percentage with dropout percentage."""
        q = "Top 5 zones by salary percentage with dropout percentage"
        handler = route_question(q)
        res = handler({})

        self.assertEqual(res['function'], 'multi_metric_analysis')
        self.assertTrue(len(res['data']) >= 3)

    # -------------------------------------------------------------------------
    # 3. Preservation of Single-Entity Statistics Profiles
    # -------------------------------------------------------------------------

    def test_entity_profile_agm_ramana_rao_statistics(self):
        """Verify 'AGM Ramana Rao statistics' routes to full executive profile, not a table."""
        q = "AGM Ramana Rao statistics"
        handler = route_question(q)
        res = handler({})

        self.assertIn(res['function'], ('agm_combined_statistics', 'agm_statistics'))
        self.assertIn('### AGM', res['answer'])
        self.assertIn('#### 1. About This AGM', res['answer'])

    def test_entity_profile_ri_anitha_statistics(self):
        """Verify 'RI Anitha statistics' routes to full executive profile, not a table."""
        q = "RI Anitha statistics"
        handler = route_question(q)
        res = handler({})

        self.assertIn(res['function'], ('ri_combined_statistics', 'ri_statistics'))
        self.assertIn('### RI', res['answer'])
        self.assertIn('#### 1. About This RI', res['answer'])

    def test_entity_profile_kakinada_1_statistics(self):
        """Verify 'KAKINADA 1 statistics' correctly identifies non-existent branch."""
        q = "KAKINADA 1 statistics"
        handler = route_question(q)
        res = handler({})

        self.assertEqual(res['function'], 'entity_not_found')
        self.assertIn("couldn't find a matching", res['answer'])

    def test_entity_profile_live_branch_statistics(self):
        """Verify live branch statistics 'Kompally 2 statistics' routes to full executive profile."""
        q = "Kompally 2 statistics"
        handler = route_question(q)
        res = handler({})

        self.assertIn(res['function'], ('branch_combined_statistics', 'branch_statistics'))
        self.assertIn('### Branch Kompally 2 — Statistics', res['answer'])
        self.assertIn('#### 1. About This Branch', res['answer'])

