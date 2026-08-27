from pathlib import Path

import pandas as pd
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from query_engine.analytics import top_5_dropout_branches
from query_engine.glossary import ABBREVIATIONS
from query_engine.orchestrator import get_dataframe, get_metric_index
from query_engine.router import route_question
from query_engine.views import QueryView


class AnalyticsTests(SimpleTestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            'Branch': ['A', 'B', 'C', 'D', 'E', 'F'],
            'CY-DPP': [5, 25, 10, 30, 20, 15],
        })

    def test_top_five_sorted_by_cy_dpp_descending(self):
        result = top_5_dropout_branches(self.df)
        self.assertEqual([x['branch'] for x in result], ['D', 'B', 'E', 'F', 'C'])
        self.assertEqual([x['dropout_percentage'] for x in result], [30.0, 25.0, 20.0, 15.0, 10.0])

    def test_business_abbreviations_are_exact(self):
        expected = {
            'PP': 'Pre Primary', 'PS': 'Primary School', 'HS': 'High School',
            'E': 'Existing', 'N': 'New', 'LY': 'Last Year', 'CY': 'Current Year',
            'GS': 'Grant Strength', 'DP': 'Dropouts', 'DPP': 'Dropouts Percentage',
            'NS': 'Net Strength', 'STR': 'Student Teacher Ratio',
            'NSD': 'Net Strength Difference', 'NOS': 'Number of Sections',
            'SPS': 'Students Per Section', 'SC': 'Staff Count',
            'SD': 'Strength Difference', 'AC': 'Activity Staff',
            'AD': 'Administration Staff', 'NOCR': 'Number of Class Rooms',
            'NOOR': 'Number of Occupied Rooms', 'NOVR': 'Number of Vacancy Rooms',
            'ARCS': 'Average Room Capacity Square Feet',
        }
        self.assertEqual(ABBREVIATIONS, expected)

    def test_router_recognizes_supported_questions(self):
        self.assertIsNotNone(route_question('Show top 5 branches with highest dropout percentage'))
        self.assertIsNotNone(route_question('Which five branches have the worst DPP?'))

    def test_router_rejects_unsupported_question(self):
        self.assertIsNone(route_question('What is the weather today?'))


from query_engine.orchestrator import clear_caches, get_dataframe, get_metric_index


class APITests(SimpleTestCase):
    def tearDown(self):
        clear_caches()

    @override_settings(BRANCH_ANALYTICS_FILE=Path(__file__).resolve().parent.parent / 'test_branch_analytics.xlsx')
    def test_query_endpoint_v1(self):
        clear_caches()

        path = Path(__file__).resolve().parent.parent / 'test_branch_analytics.xlsx'
        pd.DataFrame({
            'Branch': ['A', 'B', 'C', 'D', 'E', 'F'],
            'CY-DPP': [5, 25, 10, 30, 20, 15],
            'LY-DPP': [10, 20, 15, 25, 10, 20],
            'CY-NS': [100, 200, 150, 50, 300, 250],
            'LY-NS': [90, 210, 140, 60, 280, 260],
        }).to_excel(path, index=False)
        try:
            request = APIRequestFactory().post('/api/query/', {
                'question': 'Show top 5 branches with highest dropout percentage'
            }, format='json')
            response = QueryView.as_view()(request)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data['success'])
            self.assertEqual(response.data['function'], 'top_5_dropout_branches')
            self.assertEqual(response.data['data'][0]['branch'], 'D')
        finally:
            path.unlink(missing_ok=True)
            clear_caches()

    @override_settings(BRANCH_ANALYTICS_FILE=Path(__file__).resolve().parent.parent / 'test_branch_analytics.xlsx')
    def test_query_endpoint_yoy(self):
        clear_caches()
        path = Path(__file__).resolve().parent.parent / 'test_branch_analytics.xlsx'
        pd.DataFrame({
            'Branch': ['A', 'B', 'C', 'D', 'E', 'F'],
            'CY-DPP': [5, 25, 10, 30, 20, 15],
            'LY-DPP': [10, 20, 15, 25, 10, 20],
            'CY-NS': [100, 200, 150, 50, 300, 250],
            'LY-NS': [90, 210, 140, 60, 280, 260],
        }).to_excel(path, index=False)
        try:
            request = APIRequestFactory().post('/api/query/', {
                'question': 'Which branches improved their dropout percentage compared with last year?'
            }, format='json')
            response = QueryView.as_view()(request)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data['success'])
            self.assertEqual(response.data['function'], 'year_over_year_change_ranking')
            self.assertIsInstance(response.data['data'], list)
        finally:
            path.unlink(missing_ok=True)
            clear_caches()

