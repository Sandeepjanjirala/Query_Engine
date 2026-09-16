from django.test import TestCase
from query_engine.router import route_question
from query_engine.orchestrator import (
    run_agm_teacher_student_ratio_statistics,
    run_ri_teacher_student_ratio_statistics,
    run_branch_teacher_student_ratio_statistics,
)


class TeacherStudentRatioStatisticsTest(TestCase):
    def test_01_agm_teacher_student_ratio_statistics_execution(self):
        res = run_agm_teacher_student_ratio_statistics({'question': 'AGM Ramana teacher student ratio statistics'}, context={'agm': 'Mr.G.V.Ramana Rao'})
        self.assertEqual(res['function'], 'agm_teacher_student_ratio_statistics')
        answer = res['answer']
        self.assertIn("AGM Teacher Student Ratio Statistics", answer)
        self.assertIn("G. V. Ramana Rao", answer)
        self.assertIn("1. About This AGM", answer)
        self.assertIn("2. Overall Staffing & Ratio Summary", answer)
        self.assertIn("3. Level-Wise Staffing Ratios", answer)
        self.assertIn("4. Zone Performance", answer)
        self.assertIn("5. RI Performance", answer)
        self.assertIn("6. Branches Needing Attention", answer)
        self.assertIn("7. Conclusion", answer)
        self.assertIn("Detailed Branch Teacher Student Ratio Data", answer)
        self.assertTrue(len(res['data']) > 0)

    def test_02_ri_teacher_student_ratio_statistics_execution(self):
        res = run_ri_teacher_student_ratio_statistics({'question': 'RI Srinivas teacher student ratio statistics'}, context={'ri': 'K.Srinivasa Rao'})
        self.assertEqual(res['function'], 'ri_teacher_student_ratio_statistics')
        answer = res['answer']
        self.assertIn("RI Teacher Student Ratio Statistics", answer)
        self.assertIn("K. Srinivasa Rao", answer)
        self.assertIn("1. About This RI", answer)
        self.assertIn("2. Overall Staffing & Ratio Summary", answer)
        self.assertIn("3. Level-Wise Staffing Ratios", answer)
        self.assertIn("4. Branches Needing Attention", answer)
        self.assertIn("5. Conclusion", answer)
        self.assertNotIn("Branch Performance", answer)
        self.assertIn("Detailed Branch Teacher Student Ratio Data", answer)
        self.assertTrue(len(res['data']) > 0)

    def test_03_branch_teacher_student_ratio_statistics_execution(self):
        res = run_branch_teacher_student_ratio_statistics({'question': 'SUCHITRA teacher student ratio statistics'}, context={'branch': 'SUCHITRA'})
        self.assertEqual(res['function'], 'branch_teacher_student_ratio_statistics')
        answer = res['answer']
        self.assertIn("# Branch Teacher Student Ratio Statistics — SUCHITRA", answer)
        self.assertIn("1. About This Branch", answer)
        self.assertIn("2. Staffing & Operational Overview", answer)
        self.assertIn("3. Level-Wise Staffing Breakdown", answer)
        self.assertIn("4. Conclusion", answer)
        self.assertIn("Detailed Branch Teacher Student Ratio Data", answer)
        self.assertTrue(len(res['data']) > 0)

    def test_04_routing_teacher_student_ratio_triggers(self):
        queries = [
            "Teacher student ratio statistics",
            "Student teacher ratio statistics",
            "Staff ratio statistics",
            "AGM G.V.Ramana Rao teacher student ratio statistics",
            "RI K.Srinivasa Rao staff ratio statistics",
            "SUCHITRA teacher student ratio statistics",
        ]
        for q in queries:
            handler = route_question(q)
            self.assertIsNotNone(handler, f"Routing failed for '{q}'")
            res = handler({})
            self.assertIn(res['function'], [
                'agm_teacher_student_ratio_statistics',
                'ri_teacher_student_ratio_statistics',
                'branch_teacher_student_ratio_statistics',
            ], f"Unexpected handler for '{q}'")
