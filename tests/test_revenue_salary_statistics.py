from django.test import TestCase
from query_engine.router import route_question
from query_engine.orchestrator import (
    run_agm_revenue_salary_statistics,
    run_ri_revenue_salary_statistics,
    run_branch_revenue_salary_statistics,
)
from query_engine.dataset_loader import load_dataset


class RevenueSalaryStatisticsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.df = load_dataset('revenue_vs_salary')

    def test_01_agm_revenue_salary_statistics_execution(self):
        res = run_agm_revenue_salary_statistics({'question': 'AGM Ramana revenue vs salary statistics'}, context={'agm': 'Mr.G.V.Ramana Rao'})
        self.assertEqual(res['function'], 'agm_revenue_salary_statistics')
        answer = res['answer']
        self.assertIn("# AGM Revenue vs Salary Statistics — Mr. G. V. Ramana Rao", answer)
        self.assertIn("1. About This AGM", answer)
        self.assertIn("2. Overall Financial Summary", answer)
        self.assertIn("salary costs were", answer)
        self.assertNotIn("as surplus", answer)
        self.assertNotIn("remaining", answer)
        self.assertIn("3. Segment Breakdown", answer)
        self.assertIn("Primary School (PS)", answer)
        self.assertNotIn("Lower Primary (LPS)", answer)
        self.assertNotIn("Upper Primary (UPS)", answer)
        self.assertIn("4. Zone Performance", answer)
        self.assertIn("5. RI Performance", answer)
        self.assertIn("6. Branches Needing Attention", answer)
        self.assertIn("7. Conclusion", answer)
        self.assertIn("Detailed Branch Revenue vs Salary Data", answer)
        self.assertTrue(len(res['data']) > 0)

    def test_02_ri_revenue_salary_statistics_execution(self):
        res = run_ri_revenue_salary_statistics({'question': 'RI Srinivas revenue vs salary statistics'}, context={'ri': 'K.Srinivasa Rao'})
        self.assertEqual(res['function'], 'ri_revenue_salary_statistics')
        answer = res['answer']
        self.assertIn("RI Revenue vs Salary Statistics", answer)
        self.assertIn("K. Srinivasa Rao", answer)
        self.assertIn("1. About This RI", answer)
        self.assertIn("2. Overall Financial Summary", answer)
        self.assertIn("salary costs were", answer)
        self.assertIn("3. Segment Breakdown", answer)
        self.assertIn("Primary School (PS)", answer)
        self.assertIn("4. Branches Needing Attention", answer)
        self.assertIn("5. Conclusion", answer)
        self.assertNotIn("Branch Performance", answer)
        self.assertIn("Detailed Branch Revenue vs Salary Data", answer)
        self.assertTrue(len(res['data']) > 0)

    def test_03_branch_revenue_salary_statistics_execution(self):
        res = run_branch_revenue_salary_statistics({'question': 'SUCHITRA revenue vs salary statistics'}, context={'branch': 'SUCHITRA'})
        self.assertEqual(res['function'], 'branch_revenue_salary_statistics')
        answer = res['answer']
        self.assertIn("# Branch Revenue vs Salary Statistics — SUCHITRA", answer)
        self.assertIn("1. About This Branch", answer)
        self.assertIn("2. Financial & Operational Overview", answer)
        self.assertIn("salary costs accounted for", answer)
        self.assertIn("3. Segment Breakdown", answer)
        self.assertIn("Primary School (PS)", answer)
        self.assertIn("4. Conclusion", answer)
        self.assertIn("Detailed Branch Revenue vs Salary Data", answer)
        self.assertTrue(len(res['data']) > 0)

    def test_04_routing_revenue_statistics_triggers(self):
        queries = [
            "Revenue statistics",
            "salary statistics",
            "revenue vs salary statistics",
            "AGM G.V.Ramana Rao revenue statistics",
            "RI K.Srinivasa Rao revenue vs salary statistics",
            "SUCHITRA revenue statistics",
        ]
        for q in queries:
            handler = route_question(q)
            self.assertIsNotNone(handler, f"Routing failed for '{q}'")
            res = handler({})
            self.assertIn(res['function'], [
                'agm_revenue_salary_statistics',
                'ri_revenue_salary_statistics',
                'branch_revenue_salary_statistics',
            ], f"Unexpected handler for '{q}'")
