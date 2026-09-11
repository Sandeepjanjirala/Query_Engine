from django.test import TestCase
from rest_framework.test import APIRequestFactory

from query_engine.router import route_question
from query_engine.views import QueryView


class RIScopedBranchRankingTests(TestCase):
    def test_query_1_ri_m_ramana_top_branches_highest_dropout_percentage(self):
        handler = route_question("RI M Ramana top branches with highest dropout percentage")
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'top_5_dropout_branches')
        branches = [item['branch'] for item in res['data']]
        # All 5 returned branches must belong strictly to Mr.M.Ramana
        expected_branches = ['NARSIPATNAM', 'YALAMANCHILI', 'GAJUWAKA', 'KURMANNAPALEM', 'ANAKAPALLI']
        self.assertEqual(branches, expected_branches)

        answer = res['answer']
        self.assertIn('| Rank | Branch | Current Year | Last Year | Change |', answer)
        self.assertIn('pp', answer)

    def test_query_2_ri_m_ramana_top_branches_dropouts_count(self):
        handler = route_question("RI M ramana top branches with dropouts count")
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'rank_branches_by_metric')
        branches = [item['branch'] for item in res['data']]
        # Must return branches under Mr.M.Ramana ordered by count descending
        expected_branches = ['NARSIPATNAM', 'KURMANNAPALEM', 'ANAKAPALLI', 'YALAMANCHILI', 'GAJUWAKA']
        self.assertEqual(branches, expected_branches)

        answer = res['answer']
        self.assertIn('| Rank | Branch | Current Year | Last Year | Change |', answer)
        self.assertIn('+12', answer)

    def test_natural_language_variants_for_m_ramana(self):
        variants = [
            "RI Mr.M.Ramana top branches with highest dropout percentage",
            "Top 5 branches under M Ramana by dropout percentage",
            "Top 5 branches within Mr.M.Ramana by dropout percentage",
            "Top 5 branches for Mr.M.Ramana by dropout percentage",
        ]
        for query in variants:
            handler = route_question(query)
            self.assertIsNotNone(handler, f"Failed to route variant: {query}")
            res = handler({})
            branches = [item['branch'] for item in res['data']]
            self.assertEqual(branches[0], 'NARSIPATNAM', f"Failed top branch for variant: {query}")
            self.assertNotIn('Kakinada 6', branches)

    def test_scoped_ranking_under_ahmedali(self):
        handler = route_question("Top 5 branches under Mr.Ahmedali by dropout percentage")
        res = handler({})
        branches = [item['branch'] for item in res['data']]
        self.assertEqual(branches[0], 'MVP COLONY')
        self.assertNotIn('NARSIPATNAM', branches)

    def test_scoped_ranking_under_mv_suresh_agm(self):
        handler = route_question("Top 5 branches under Mr.M.V.Suresh by dropout count")
        res = handler({})
        branches = [item['branch'] for item in res['data']]
        self.assertEqual(branches[0], 'RAJAHMUNDRY 1')
        self.assertNotIn('MVP COLONY', branches)

    def test_scoped_ranking_in_kakinada_zone(self):
        handler = route_question("Top 5 branches in Kakinada zone by dropout percentage")
        res = handler({})
        branches = [item['branch'] for item in res['data']]
        self.assertEqual(branches[0], 'Kakinada 6')

    def test_api_endpoint_runtime_query_path(self):
        factory = APIRequestFactory()

        # Bug 1 API call
        req1 = factory.post('/api/query/', {'question': 'RI M Ramana top branches with highest dropout percentage'}, format='json')
        resp1 = QueryView.as_view()(req1)
        self.assertEqual(resp1.status_code, 200)
        self.assertTrue(resp1.data['success'])
        branches1 = [item['branch'] for item in resp1.data['data']]
        self.assertEqual(branches1, ['NARSIPATNAM', 'YALAMANCHILI', 'GAJUWAKA', 'KURMANNAPALEM', 'ANAKAPALLI'])

        # Bug 2 API call
        req2 = factory.post('/api/query/', {'question': 'RI M ramana top branches with dropouts count'}, format='json')
        resp2 = QueryView.as_view()(req2)
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.data['success'])
        branches2 = [item['branch'] for item in resp2.data['data']]
        self.assertEqual(branches2, ['NARSIPATNAM', 'KURMANNAPALEM', 'ANAKAPALLI', 'YALAMANCHILI', 'GAJUWAKA'])

    def test_explicit_prompt_entity_overrides_dashboard_context_filters(self):
        # Scenario: Dashboard filter context has RI=Mr.M.Ramana and Branch=GAJUWAKA selected
        active_dashboard_context = {
            'agm': 'All',
            'ri': 'Mr.M.Ramana',
            'zone': 'Visakhapatnam',
            'branches': ['GAJUWAKA'],
        }

        # User asks about RI gopi nath in AI assistant chat
        handler = route_question("show RI gopi nath top branches with dropout count")
        res = handler(active_dashboard_context)

        branches = [item['branch'] for item in res['data']]
        # Must override Mr.M.Ramana and GAJUWAKA, returning top branches under Mr.P Gopi Nath
        self.assertEqual(branches[0], 'Payakaraopeta')
        self.assertNotIn('GAJUWAKA', branches)

