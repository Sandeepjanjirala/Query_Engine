"""
Tests for parameter-driven capabilities, enhanced YoY intent detection and
parameter extraction, and confirmation that the original V1 dropout intent
is completely unaffected.
"""
from django.test import SimpleTestCase

import pandas as pd

from query_engine import params as p
from query_engine.analytics import (
    aggregate_by_group,
    lookup_branch_metrics,
    rank_branches_by_metric,
    year_over_year_ranking,
)
from query_engine.pandas_tools import build_metric_index, resolve_column
from query_engine.router import route_question


def make_df():
    return pd.DataFrame({
        'AGM Name': ['Suresh', 'Suresh', 'Kumar', 'Kumar'],
        'RI Name': ['Ramesh', 'Naresh', 'Ramesh', 'Naresh'],
        'Zone': ['Zone A', 'Zone A', 'Zone B', 'Zone B'],
        'Branch': ['KAKINADA 1', 'NAD', 'VIZAG 1', 'ELURU 1'],
        'CY-DPP': [30, 10, 25, 15],
        'LY-DPP': [20, 15, 30, 10],
        'CY-NS': [100, 200, 150, 50],
        'LY-NS': [80, 220, 100, 60],
        'CY-GS': [120, 210, 160, 70],
        'LY-GS': [110, 200, 150, 80],
        'AC-CY-SC': [3, 2, 4, 1],
        'AD-CY-SC': [5, 4, 6, 2],
        'CY-SC': [20, 18, 22, 10],
        'LY-SC': [18, 20, 20, 12],
        'PP-NOS': [4, 3, 5, 2],
        'Avg-SPS': [30, 28, 32, 25],
        'SD': [20, -20, 50, -10],
        'NSD': [20, -20, 50, -10],
        'NOCR': [10, 8, 12, 5],
        'NOOR': [8, 8, 10, 5],
        'NOVR': [2, 0, 2, 0],
        'ARCS': [500, 450, 600, 400],
    })


class ParamExtractionTests(SimpleTestCase):
    def test_extract_metric_prefers_specific_phrases(self):
        self.assertEqual(p.extract_metric('net strength difference for branches'), 'NSD')
        self.assertEqual(p.extract_metric('strength difference by branch'), 'SD')
        self.assertEqual(p.extract_metric('dropout percentage highest'), 'DPP')
        self.assertEqual(p.extract_metric('number of dropouts'), 'DP')
        self.assertEqual(p.extract_metric('grant strength top branches'), 'GS')
        self.assertEqual(p.extract_metric('net strength by zone'), 'NS')
        self.assertEqual(p.extract_metric('compare performance by branch'), 'NS')
        self.assertEqual(p.extract_metric('staff count for branch'), 'SC')
        self.assertEqual(p.extract_metric('student teacher ratio'), 'STR')
        self.assertEqual(p.extract_metric('number of sections'), 'NOS')
        self.assertEqual(p.extract_metric('students per section'), 'Avg-SPS')
        self.assertEqual(p.extract_metric('vacant rooms'), 'NOVR')
        self.assertIsNone(p.extract_metric('hello there'))

    def test_extract_level(self):
        self.assertEqual(p.extract_level('high school sections'), 'HS')
        self.assertEqual(p.extract_level('pre primary dropout'), 'PP')
        self.assertEqual(p.extract_level('primary school staff'), 'PS')
        self.assertIsNone(p.extract_level('overall dropout'))

    def test_extract_type_only_matches_full_words(self):
        self.assertEqual(p.extract_type('new admissions dropout'), 'N')
        self.assertEqual(p.extract_type('existing students'), 'E')
        self.assertIsNone(p.extract_type('branch net strength'))

    def test_extract_n_defaults_and_parses_digits_and_words(self):
        self.assertEqual(p.extract_n('top 5 branches'), 5)
        self.assertEqual(p.extract_n('top 12 branches'), 12)
        self.assertEqual(p.extract_n('top five branches'), 5)
        self.assertEqual(p.extract_n('branches with highest strength'), 5)

    def test_extract_direction(self):
        self.assertEqual(p.extract_direction('bottom 5 branches'), 'asc')
        self.assertEqual(p.extract_direction('top 5 branches'), 'desc')

    def test_is_yoy_question(self):
        self.assertTrue(p.is_yoy_question('Which branches improved their dropout percentage compared with last year?'))
        self.assertTrue(p.is_yoy_question('Which branches had the biggest increase in dropout percentage?'))
        self.assertTrue(p.is_yoy_question('Which branches declined compared with last year?'))
        self.assertTrue(p.is_yoy_question('Compare current-year and previous-year performance by branch.'))
        self.assertTrue(p.is_yoy_question('CY vs LY net strength'))
        self.assertTrue(p.is_yoy_question('Show YoY growth in grant strength'))
        self.assertFalse(p.is_yoy_question('Total net strength by zone'))
        self.assertFalse(p.is_yoy_question('Vacant rooms in Kakinada branch'))

    def test_extract_yoy_direction(self):
        self.assertEqual(
            p.extract_yoy_direction('Which branches improved their dropout percentage compared with last year?'),
            'positive',
        )
        self.assertEqual(
            p.extract_yoy_direction('Which branches had the biggest increase in dropout percentage?'),
            'positive',
        )
        self.assertEqual(
            p.extract_yoy_direction('Which branches declined compared with last year?'),
            'negative',
        )
        self.assertEqual(
            p.extract_yoy_direction('Which branches had the biggest change in dropout percentage?'),
            'absolute',
        )
        self.assertEqual(
            p.extract_yoy_direction('Compare current-year and previous-year performance by branch.'),
            'compare',
        )

    def test_extract_known_values_uses_word_boundaries(self):
        values = ['NAD', 'KAKINADA 1']
        found = p.extract_known_values('vacant rooms in kakinada branch', values)
        self.assertNotIn('NAD', found)

        found = p.extract_known_values('staff count for NAD', values)
        self.assertIn('NAD', found)


class MetricIndexTests(SimpleTestCase):
    def setUp(self):
        self.df = make_df()
        self.index = build_metric_index(self.df)

    def test_resolves_overall_and_level_columns(self):
        self.assertEqual(resolve_column(self.index, 'DPP', year='CY'), 'CY-DPP')
        self.assertEqual(resolve_column(self.index, 'DPP', year='LY'), 'LY-DPP')
        self.assertEqual(resolve_column(self.index, 'NOS', 'PP'), 'PP-NOS')
        self.assertEqual(resolve_column(self.index, 'SC', 'AC', year='CY'), 'AC-CY-SC')
        self.assertEqual(resolve_column(self.index, 'ARCS'), 'ARCS')

    def test_falls_back_when_type_not_supported_by_metric(self):
        self.assertEqual(resolve_column(self.index, 'NOS', 'PP', 'E'), 'PP-NOS')

    def test_returns_none_for_unknown_metric(self):
        self.assertIsNone(resolve_column(self.index, 'NOPE'))


class AnalyticsPrimitiveTests(SimpleTestCase):
    def setUp(self):
        self.df = make_df()

    def test_rank_branches_by_metric_descending(self):
        result = rank_branches_by_metric(self.df, 'CY-NS', n=2, ascending=False)
        self.assertEqual([r['branch'] for r in result], ['NAD', 'VIZAG 1'])

    def test_rank_branches_by_metric_ascending(self):
        result = rank_branches_by_metric(self.df, 'CY-DPP', n=2, ascending=True)
        self.assertEqual([r['branch'] for r in result], ['NAD', 'ELURU 1'])

    def test_lookup_branch_metrics_single_branch(self):
        result = lookup_branch_metrics(self.df, ['CY-NS', 'CY-GS'], branches=['VIZAG 1'])
        self.assertEqual(result, [{'branch': 'VIZAG 1', 'CY-NS': 150.0, 'CY-GS': 160.0}])

    def test_lookup_branch_metrics_all_when_no_branches_given(self):
        result = lookup_branch_metrics(self.df, ['CY-NS'])
        self.assertEqual(len(result), 4)

    def test_aggregate_by_group_sum(self):
        result = aggregate_by_group(self.df, 'Zone', 'CY-NS', agg='sum')
        by_zone = {r['group']: r['value'] for r in result}
        self.assertEqual(by_zone['Zone A'], 300.0)
        self.assertEqual(by_zone['Zone B'], 200.0)

    def test_aggregate_by_group_mean(self):
        result = aggregate_by_group(self.df, 'Zone', 'CY-NS', agg='mean')
        by_zone = {r['group']: r['value'] for r in result}
        self.assertEqual(by_zone['Zone A'], 150.0)

    def test_year_over_year_ranking_positive_change(self):
        # CY-NS - LY-NS: KAKINADA 1 = 20, NAD = -20, VIZAG 1 = 50, ELURU 1 = -10
        result = year_over_year_ranking(self.df, 'CY-NS', 'LY-NS', n=4, ascending=False, sort_by='change')
        self.assertEqual(result[0]['branch'], 'VIZAG 1')
        self.assertEqual(result[0]['change'], 50.0)
        self.assertEqual(result[1]['branch'], 'KAKINADA 1')
        self.assertEqual(result[1]['change'], 20.0)

    def test_year_over_year_ranking_negative_change(self):
        result = year_over_year_ranking(self.df, 'CY-NS', 'LY-NS', n=2, ascending=True, sort_by='change')
        self.assertEqual(result[0]['branch'], 'NAD')
        self.assertEqual(result[0]['change'], -20.0)
        self.assertEqual(result[1]['branch'], 'ELURU 1')
        self.assertEqual(result[1]['change'], -10.0)

    def test_year_over_year_ranking_absolute_change(self):
        result = year_over_year_ranking(self.df, 'CY-NS', 'LY-NS', n=4, sort_by='absolute')
        self.assertEqual(result[0]['branch'], 'VIZAG 1')   # |50|
        self.assertEqual(result[0]['change'], 50.0)
        self.assertEqual(result[1]['branch'], 'KAKINADA 1') # |20|
        self.assertEqual(result[2]['branch'], 'NAD')        # |-20|


class RouterCapabilityTests(SimpleTestCase):
    def setUp(self):
        self.ctx = {'agm': 'All', 'ri': 'All', 'zone': 'All', 'branches': ['All']}

    def test_original_dropout_intent_untouched(self):
        handler = route_question('Show top 5 branches with highest dropout percentage')
        self.assertIsNotNone(handler)

    def test_yoy_four_target_queries_route_successfully(self):
        # 1. Improved dropout percentage compared with last year
        h1 = route_question('Which branches improved their dropout percentage compared with last year?')
        self.assertIsNotNone(h1)

        # 2. Biggest increase in dropout percentage
        h2 = route_question('Which branches had the biggest increase in dropout percentage?')
        self.assertIsNotNone(h2)

        # 3. Declined compared with last year
        h3 = route_question('Which branches declined compared with last year?')
        self.assertIsNotNone(h3)

        # 4. Compare current-year and previous-year performance by branch
        h4 = route_question('Compare current-year and previous-year performance by branch.')
        self.assertIsNotNone(h4)

    def test_generic_ranking_covers_other_metrics(self):
        handler = route_question('Top 3 branches by net strength')
        self.assertIsNotNone(handler)

    def test_bottom_ranking_dropout_variation_not_covered_by_v1(self):
        handler = route_question('Bottom 5 branches by dropout percentage')
        self.assertIsNotNone(handler)

    def test_unsupported_question_still_rejected(self):
        self.assertIsNone(route_question('What is the weather today?'))

    def test_group_aggregate_routes(self):
        self.assertIsNotNone(route_question('Total net strength by zone'))

    def test_staff_summary_routes(self):
        self.assertIsNotNone(route_question('Show activity staff count for all branches'))

    def test_room_snapshot_routes(self):
        self.assertIsNotNone(route_question('Vacant rooms by branch'))

    def test_sections_snapshot_routes(self):
        self.assertIsNotNone(route_question('Number of sections for High School branch wise'))

    def test_strength_difference_routes(self):
        self.assertIsNotNone(route_question('Strength difference ranking'))
