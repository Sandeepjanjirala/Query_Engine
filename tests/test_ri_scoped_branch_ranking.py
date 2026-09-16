from django.test import TestCase
from rest_framework.test import APIRequestFactory

from query_engine.router import route_question
from query_engine.views import QueryView


class RIScopedBranchRankingTests(TestCase):
    def test_query_1_ri_srinivasa_rao_top_branches_highest_dropout_percentage(self):
        handler = route_question("RI K.Srinivasa Rao top branches with highest dropout percentage")
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'top_5_dropout_branches')
        branches = [item['branch'] for item in res['data']]
        # All 5 returned branches must belong strictly to K.Srinivasa Rao
        expected_branches = ['SUCHITRA', 'HMT Colony', 'Kompally 5', 'MEDCHAL IPL IC', 'Kompally 4']
        self.assertEqual(branches, expected_branches)

        answer = res['answer']
        self.assertIn('| Rank | Branch | Current Year | Last Year | Change |', answer)
        self.assertTrue('percentage points' in answer or 'pp' in answer)

    def test_query_2_ri_srinivasa_rao_top_branches_dropouts_count(self):
        handler = route_question("RI K.Srinivasa Rao top branches with dropouts count")
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'rank_branches_by_metric')
        branches = [item['branch'] for item in res['data']]
        # Must return branches under K.Srinivasa Rao ordered by count descending
        expected_branches = ['Kompally 4', 'SUCHITRA', 'HMT Colony', 'Kompally 2', 'Kompally 5']
        self.assertEqual(branches, expected_branches)

        answer = res['answer']
        self.assertIn('| Rank | Branch | Current Year | Last Year | Change |', answer)

    def test_natural_language_variants_for_srinivasa_rao(self):
        variants = [
            "RI Mr.K.Srinivasa Rao top branches with highest dropout percentage",
            "Top 5 branches under K Srinivasa Rao by dropout percentage",
            "Top 5 branches within Mr.K.Srinivasa Rao by dropout percentage",
            "Top 5 branches for Mr.K.Srinivasa Rao by dropout percentage",
        ]
        for query in variants:
            handler = route_question(query)
            self.assertIsNotNone(handler, f"Failed to route variant: {query}")
            res = handler({})
            branches = [item['branch'] for item in res['data']]
            self.assertEqual(branches[0], 'SUCHITRA', f"Failed top branch for variant: {query}")

    def test_scoped_ranking_under_padmaja(self):
        handler = route_question("Top 5 branches under Mrs.Padmaja by dropout percentage")
        res = handler({})
        branches = [item['branch'] for item in res['data']]
        self.assertEqual(branches[0], 'SP NAGAR DS')
        self.assertNotIn('SUCHITRA', branches)

    def test_scoped_ranking_under_ramana_rao_agm(self):
        handler = route_question("Top 5 branches under Mr.G.V.Ramana Rao by dropout count")
        res = handler({})
        branches = [item['branch'] for item in res['data']]
        self.assertEqual(branches[0], 'Kompally 4')

    def test_scoped_ranking_in_kompally_zone(self):
        handler = route_question("Top 5 branches in Kompally zone by dropout percentage")
        res = handler({})
        branches = [item['branch'] for item in res['data']]
        self.assertEqual(branches[0], 'SUCHITRA')

    def test_api_endpoint_runtime_query_path(self):
        factory = APIRequestFactory()

        # Bug 1 API call
        req1 = factory.post('/api/query/', {'question': 'RI K.Srinivasa Rao top branches with highest dropout percentage'}, format='json')
        resp1 = QueryView.as_view()(req1)
        self.assertEqual(resp1.status_code, 200)
        self.assertTrue(resp1.data['success'])
        branches1 = [item['branch'] for item in resp1.data['data']]
        self.assertEqual(branches1, ['SUCHITRA', 'HMT Colony', 'Kompally 5', 'MEDCHAL IPL IC', 'Kompally 4'])

        # Bug 2 API call
        req2 = factory.post('/api/query/', {'question': 'RI K.Srinivasa Rao top branches with dropouts count'}, format='json')
        resp2 = QueryView.as_view()(req2)
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.data['success'])
        branches2 = [item['branch'] for item in resp2.data['data']]
        self.assertEqual(branches2, ['Kompally 4', 'SUCHITRA', 'HMT Colony', 'Kompally 2', 'Kompally 5'])

    def test_explicit_prompt_entity_overrides_dashboard_context_filters(self):
        # Scenario: Dashboard filter context has RI=K.Srinivasa Rao and Branch=SUCHITRA selected
        active_dashboard_context = {
            'agm': 'All',
            'ri': 'K.Srinivasa Rao',
            'zone': 'Kompally',
            'branches': ['SUCHITRA'],
        }

        # User asks about RI Hari Krishna in AI assistant chat
        handler = route_question("show RI Hari Krishna top branches with dropout count")
        res = handler(active_dashboard_context)

        branches = [item['branch'] for item in res['data']]
        # Must override K.Srinivasa Rao and SUCHITRA, returning top branches under Hari Krishna
        self.assertEqual(branches[0], 'BEERAMGUDA')
        self.assertNotIn('SUCHITRA', branches)

