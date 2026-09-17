from django.test import TestCase
from query_engine.router import route_question, _merge_text_entities
from query_engine import params as p


class DeepAuditRegressionTests(TestCase):
    def test_phase1_wise_entity_capture(self):
        ctx = _merge_text_entities('AGM wise fee due', {})
        self.assertNotIn('wise', str(ctx.get('agm', '')).lower())

        ctx_ri = _merge_text_entities('RI wise fee due', {})
        self.assertNotIn('wise', str(ctx_ri.get('ri', '')).lower())

        ctx_zone = _merge_text_entities('Zone wise dropout percentage', {})
        self.assertNotIn('wise', str(ctx_zone.get('zone', '')).lower())

        h_agm = route_question('AGM wise fee due')
        res_agm = h_agm({})
        self.assertTrue(len(res_agm.get('data', [])) > 0)

        h_ri = route_question('RI wise fee due')
        res_ri = h_ri({})
        self.assertTrue(len(res_ri.get('data', [])) > 0)

    def test_phase2_pp_ps_hs_group_aggregation(self):
        h = route_question('What is the PP dropout percentage for AGM Ramana Rao?')
        self.assertIsNotNone(h)
        res = h({})
        self.assertTrue(len(res.get('data', [])) > 0)
        entry = res['data'][0]
        val = entry.get('current_year') or entry.get('value')
        self.assertAlmostEqual(val, 17.60, places=1)
        self.assertIn('17.6', res.get('answer', ''))

    def test_phase3_single_type_existing_new(self):
        h = route_question('AGM wise existing student dropout percentage')
        self.assertIsNotNone(h)
        res = h({})
        self.assertTrue(len(res.get('data', [])) > 0)
        self.assertEqual(res['function'], 'group_metric_aggregate')

        h_both = route_question('Compare existing and new student dropout percentage.')
        self.assertIsNotNone(h_both)
        res_both = h_both({})
        self.assertEqual(res_both['function'], 'compare_dimensions')

    def test_phase4_biggest_improvement_direction(self):
        h = route_question('Which branch has the biggest improvement in dropout percentage?')
        self.assertIsNotNone(h)
        res = h({})
        self.assertTrue(len(res.get('data', [])) > 0)
        top = res['data'][0]
        self.assertIn('MIYAPUR FUTURE PATHWAYS', top['branch'])
        self.assertLess(top['change'], 0)
        self.assertAlmostEqual(top['change'], -10.53, places=1)
        self.assertIn('Biggest Improvement', res.get('answer', ''))

    def test_phase5_cross_hierarchy_precedence(self):
        dim = p.extract_group_dimension('Compare AGM Ramana Rao dropout by RI')
        self.assertEqual(dim, 'ri')

        h = route_question('Compare AGM Ramana Rao dropout by RI')
        self.assertIsNotNone(h)
        res = h({})
        self.assertEqual(res['function'], 'group_metric_aggregate')
        self.assertTrue(len(res.get('data', [])) > 0)

    def test_phase7_historical_revenue_salary_guard(self):
        h = route_question('What was the previous year revenue for AGM Ramana Rao?')
        self.assertIsNotNone(h)
        res = h({})
        self.assertEqual(res['function'], 'revenue_salary_historical_unavailable')
        self.assertIn('Historical last-year comparison is not available', res['answer'])
