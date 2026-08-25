import pandas as pd
from django.test import SimpleTestCase

from query_engine.analytics import top_5_dropout_branches
from query_engine.filters import apply_filter_context


def make_df():
    return pd.DataFrame({
        'AGM Name': ['Suresh', 'Suresh', 'Suresh', 'Kumar', 'Kumar', 'Kumar'],
        'RI Name': ['Ramesh', 'Ramesh', 'Naresh', 'Ramesh', 'Naresh', 'Naresh'],
        'Zone': ['Zone A', 'Zone B', 'Zone A', 'Zone A', 'Zone B', 'Zone B'],
        'Branch': ['KAKINADA 1', 'RAJAHMUNDRY 1', 'KAKINADA 2', 'VIZAG 1', 'VIZAG 2', 'ELURU 1'],
        'CY-DPP': [30, 10, 25, 15, 5, 20],
    })


class ApplyFilterContextTests(SimpleTestCase):
    def setUp(self):
        self.df = make_df()

    def test_no_context_returns_all_rows(self):
        result = apply_filter_context(self.df, None)
        self.assertEqual(len(result), 6)

    def test_all_filters_returns_all_rows(self):
        result = apply_filter_context(self.df, {'agm': 'All', 'ri': 'All', 'branches': ['All']})
        self.assertEqual(len(result), 6)

    def test_agm_filter(self):
        result = apply_filter_context(self.df, {'agm': 'Suresh'})
        self.assertEqual(set(result['Branch']), {'KAKINADA 1', 'RAJAHMUNDRY 1', 'KAKINADA 2'})

    def test_ri_filter(self):
        result = apply_filter_context(self.df, {'ri': 'Naresh'})
        self.assertEqual(set(result['Branch']), {'KAKINADA 2', 'VIZAG 2', 'ELURU 1'})

    def test_agm_and_ri_filter(self):
        result = apply_filter_context(self.df, {'agm': 'Suresh', 'ri': 'Ramesh'})
        self.assertEqual(set(result['Branch']), {'KAKINADA 1', 'RAJAHMUNDRY 1'})

    def test_single_branch_filter(self):
        result = apply_filter_context(self.df, {'branches': ['VIZAG 1']})
        self.assertEqual(set(result['Branch']), {'VIZAG 1'})

    def test_multiple_branches_filter(self):
        result = apply_filter_context(self.df, {'branches': ['KAKINADA 1', 'ELURU 1']})
        self.assertEqual(set(result['Branch']), {'KAKINADA 1', 'ELURU 1'})

    def test_zone_filter(self):
        result = apply_filter_context(self.df, {'zone': 'Zone A'})
        self.assertEqual(set(result['Branch']), {'KAKINADA 1', 'KAKINADA 2', 'VIZAG 1'})

    def test_zone_all_means_no_filter(self):
        result = apply_filter_context(self.df, {'zone': 'All'})
        self.assertEqual(len(result), 6)

    def test_agm_ri_zone_combined(self):
        result = apply_filter_context(self.df, {'agm': 'Suresh', 'ri': 'Ramesh', 'zone': 'Zone A'})
        self.assertEqual(set(result['Branch']), {'KAKINADA 1'})

    def test_case_and_whitespace_insensitive(self):
        result = apply_filter_context(self.df, {'agm': '  suresh  '})
        self.assertEqual(len(result), 3)

    def test_unknown_value_returns_empty_not_crash(self):
        result = apply_filter_context(self.df, {'agm': 'Nobody'})
        self.assertEqual(len(result), 0)

    def test_missing_identifier_column_is_skipped_safely(self):
        # Synthetic df with no AGM/RI columns (e.g. what existing tests use) --
        # filtering on agm/ri must not raise, just have no effect.
        minimal_df = pd.DataFrame({'Branch': ['A', 'B'], 'CY-DPP': [10, 20]})
        result = apply_filter_context(minimal_df, {'agm': 'Suresh', 'ri': 'Ramesh'})
        self.assertEqual(len(result), 2)

    def test_does_not_mutate_input_dataframe(self):
        original = self.df.copy()
        apply_filter_context(self.df, {'agm': 'Suresh'})
        pd.testing.assert_frame_equal(self.df, original)

    def test_top_5_dropout_branches_unfiltered_matches_existing_behavior(self):
        filtered = apply_filter_context(self.df, {'agm': 'All', 'ri': 'All', 'branches': ['All']})
        result = top_5_dropout_branches(filtered)
        self.assertEqual(result[0]['branch'], 'KAKINADA 1')
        self.assertEqual(result[0]['dropout_percentage'], 30.0)

    def test_top_5_dropout_branches_scoped_to_agm_ri(self):
        filtered = apply_filter_context(self.df, {'agm': 'Suresh', 'ri': 'Ramesh'})
        result = top_5_dropout_branches(filtered)
        self.assertEqual([r['branch'] for r in result], ['KAKINADA 1', 'RAJAHMUNDRY 1'])
