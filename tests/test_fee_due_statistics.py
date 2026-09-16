from django.test import TestCase

from query_engine.orchestrator import (
    run_agm_fee_due_statistics,
    run_ri_fee_due_statistics,
    run_branch_fee_due_statistics,
)
from query_engine.router import route_question


class FeeDueStatisticsTests(TestCase):
    def test_agm_fee_due_statistics(self):
        res = run_agm_fee_due_statistics({}, context={'agm': 'G.V.Ramana Rao'})
        self.assertEqual(res['function'], 'agm_fee_due_statistics')
        answer = res['answer']
        self.assertIn("# AGM Fee Due Statistics — G. V. Ramana Rao", answer)
        self.assertIn("1. About This AGM", answer)
        self.assertIn("2. Last Year Fee Due", answer)
        self.assertIn("3. Current Year", answer)
        self.assertIn("4. Books Status", answer)
        self.assertIn("5. Zone Performance", answer)
        self.assertIn("6. RI Performance", answer)
        self.assertIn("7. Branches Needing Attention", answer)
        self.assertIn("8. Conclusion", answer)
        self.assertIn("Detailed Branch Fee Due Data", answer)
        self.assertIn("Last year,", answer)
        self.assertIn("Among the continuing students,", answer)
        self.assertIn("In the current year,", answer)

    def test_ri_fee_due_statistics(self):
        res = run_ri_fee_due_statistics({}, context={'ri': 'K.Srinivasa Rao'})
        self.assertEqual(res['function'], 'ri_fee_due_statistics')
        answer = res['answer']
        self.assertIn("# RI Fee Due Statistics — K. Srinivasa Rao", answer)
        self.assertIn("1. About This RI", answer)
        self.assertIn("2. Last Year Fee Due", answer)
        self.assertIn("3. Current Year", answer)
        self.assertIn("4. Books Status", answer)
        self.assertIn("5. Branches Needing Attention", answer)
        self.assertIn("6. Conclusion", answer)
        self.assertNotIn("Branch Performance", answer)
        self.assertIn("Detailed Branch Fee Due Data", answer)
        self.assertIn("Last year,", answer)
        self.assertIn("Among the continuing students,", answer)
        self.assertIn("In the current year,", answer)

    def test_branch_fee_due_statistics(self):
        res = run_branch_fee_due_statistics({}, context={'branch': 'SUCHITRA'})
        self.assertEqual(res['function'], 'branch_fee_due_statistics')
        answer = res['answer']
        self.assertIn("# Branch Fee Due Statistics — SUCHITRA", answer)
        self.assertIn("1. About This Branch", answer)
        self.assertIn("2. Last Year Fee Due", answer)
        self.assertIn("3. Current Year", answer)
        self.assertIn("4. Books Status", answer)
        self.assertIn("5. Conclusion", answer)
        self.assertIn("Detailed Branch Fee Due Data", answer)
        self.assertIn("Last year,", answer)
        self.assertIn("Among the continuing students,", answer)
        self.assertIn("In the current year,", answer)

    def test_fee_due_statistics_routing(self):
        res1 = route_question("AGM Ramana Fee Due Statistics")({})
        self.assertEqual(res1['function'], 'agm_fee_due_statistics')

        res2 = route_question("RI Srinivasa Fee Due Statistics")({})
        self.assertEqual(res2['function'], 'ri_fee_due_statistics')

        res3 = route_question("SUCHITRA Fee Due Statistics")({})
        self.assertEqual(res3['function'], 'branch_fee_due_statistics')

        # Ensure dropout questions still route to dropout statistics
        res4 = route_question("RI Srinivasa Dropouts statistics")({})
        self.assertEqual(res4['function'], 'ri_dropout_statistics')
