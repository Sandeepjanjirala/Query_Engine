from django.test import TestCase
from query_engine.router import route_question
from query_engine.orchestrator import (
    run_agm_combined_statistics,
    run_ri_combined_statistics,
    run_branch_combined_statistics,
    run_combined_statistics,
)
from query_engine.multi_stats import extract_requested_statistics, normalize_speech_and_wording


class MultiStatisticsTest(TestCase):
    def test_01_extract_requested_statistics_normalization(self):
        self.assertEqual(extract_requested_statistics("RI Anitha dropouts, fee due statistics"), ["dropout", "fee_due"])
        self.assertEqual(extract_requested_statistics("RI Anitha revenue vs salary, fee due statistics"), ["revenue_salary", "fee_due"])
        self.assertEqual(extract_requested_statistics("RI Anitha dropouts, teacher student ratio, fee due"), ["dropout", "teacher_student_ratio", "fee_due"])
        self.assertEqual(extract_requested_statistics("AGM Suresh dropouts, fee due, revenue vs salary, teacher student ratio"), ["dropout", "fee_due", "revenue_salary", "teacher_student_ratio"])
        self.assertEqual(extract_requested_statistics("KAKINADA 1 dropouts, fee due, revenue vs salary"), ["dropout", "fee_due", "revenue_salary"])
        # Speech variations
        self.assertEqual(extract_requested_statistics("RI anitha dropouts feedue statistics"), ["dropout", "fee_due"])
        self.assertEqual(extract_requested_statistics("RI anitha drop outs fee-do statistics"), ["dropout", "fee_due"])
        self.assertEqual(extract_requested_statistics("RI anitha revenue verse salary and fee dues"), ["revenue_salary", "fee_due"])
        self.assertEqual(extract_requested_statistics("RI anitha drop outs and str statistics"), ["dropout", "teacher_student_ratio"])

    def test_02_ri_anitha_fee_due_and_dropouts_routing_and_format(self):
        handler = route_question("RI Anitha fee due and dropouts statistics")
        self.assertIsNotNone(handler)
        res = handler(context={})
        self.assertEqual(res['function'], 'ri_combined_statistics')
        self.assertEqual(res['data']['entity_type'], 'RI')
        self.assertIn("Anitha", res['data']['entity_name'])
        ans = res['answer']

        # Selective sequential numbering: 1. About, 2. Dropout, 3. Fee Due, 4. Conclusion
        self.assertIn("### RI Y. Anitha — Statistics", ans)
        self.assertIn("#### 1. About This RI", ans)
        self.assertIn("#### 2. Overall Dropout Situation", ans)
        self.assertIn("#### 3. Fee Due Situation", ans)
        self.assertIn("#### 4. Overall Conclusion", ans)

        # Unrequested domains MUST NOT appear
        self.assertNotIn("Revenue vs Salary", ans)
        self.assertNotIn("Teacher-Student Ratio", ans)
        self.assertNotIn("Branch Performance", ans)
        self.assertNotIn("Detailed Evidence", ans)

    def test_03_ri_anitha_dropouts_and_fee_due(self):
        handler = route_question("RI Anitha dropouts and fee due statistics")
        res = handler(context={})
        self.assertEqual(res['function'], 'ri_combined_statistics')
        self.assertEqual(res['data']['entity_type'], 'RI')
        ans = res['answer']
        self.assertIn("#### 1. About This RI", ans)
        self.assertIn("#### 2. Overall Dropout Situation", ans)
        self.assertIn("#### 3. Fee Due Situation", ans)
        self.assertIn("#### 4. Overall Conclusion", ans)
        self.assertNotIn("Revenue vs Salary", ans)

    def test_04_ri_anitha_revenue_salary_and_fee_due(self):
        handler = route_question("RI Anitha revenue vs salary and fee due statistics")
        res = handler(context={})
        self.assertEqual(res['function'], 'ri_combined_statistics')
        self.assertEqual(res['data']['entity_type'], 'RI')
        ans = res['answer']
        self.assertIn("#### 1. About This RI", ans)
        self.assertIn("#### 2. Fee Due Situation", ans)
        self.assertIn("#### 3. Revenue vs Salary", ans)
        self.assertIn("#### 4. Overall Conclusion", ans)
        self.assertNotIn("Overall Dropout Situation", ans)
        self.assertNotIn("Teacher-Student Ratio", ans)
        self.assertIn("%", ans)

    def test_05_ri_anitha_3_statistics(self):
        handler = route_question("RI Anitha dropouts, teacher student ratio, fee due statistics")
        res = handler(context={})
        self.assertEqual(res['function'], 'ri_combined_statistics')
        self.assertEqual(res['data']['entity_type'], 'RI')
        ans = res['answer']
        self.assertIn("#### 1. About This RI", ans)
        self.assertIn("#### 2. Overall Dropout Situation", ans)
        self.assertIn("#### 3. Fee Due Situation", ans)
        self.assertIn("#### 4. Teacher-Student Ratio", ans)
        self.assertIn("#### 5. Overall Conclusion", ans)
        self.assertNotIn("Revenue vs Salary", ans)
        self.assertNotIn("Branch Performance", ans)

    def test_06_agm_suresh_dropouts_and_fee_due(self):
        handler = route_question("AGM Suresh dropouts and fee due statistics")
        res = handler(context={})
        self.assertEqual(res['function'], 'agm_combined_statistics')
        self.assertEqual(res['data']['entity_type'], 'AGM')
        ans = res['answer']
        self.assertIn("### AGM", ans)
        self.assertIn("#### 1. About This AGM", ans)
        self.assertIn("#### 2. Overall Dropout Situation", ans)
        self.assertIn("#### 3. Fee Due Situation", ans)
        self.assertIn("#### 4. Overall Conclusion", ans)
        self.assertNotIn("Revenue vs Salary", ans)
        self.assertNotIn("Teacher-Student Ratio", ans)

    def test_07_agm_suresh_4_statistics(self):
        handler = route_question("AGM Suresh dropouts, fee due, revenue vs salary, teacher student ratio")
        res = handler(context={})
        self.assertEqual(res['function'], 'agm_combined_statistics')
        self.assertEqual(res['data']['entity_type'], 'AGM')
        ans = res['answer']
        self.assertIn("#### 1. About This AGM", ans)
        self.assertIn("#### 2. Overall Dropout Situation", ans)
        self.assertIn("#### 3. Fee Due Situation", ans)
        self.assertIn("#### 4. Revenue vs Salary", ans)
        self.assertIn("#### 5. Teacher-Student Ratio", ans)
        self.assertIn("#### 6. Branch Performance", ans)
        self.assertIn("#### 7. Overall Conclusion", ans)

    def test_08_branch_kakinada_1_dropouts_and_fee_due(self):
        handler = route_question("KAKINADA 1 dropouts and fee due statistics")
        res = handler(context={})
        self.assertEqual(res['function'], 'branch_combined_statistics')
        self.assertEqual(res['data']['entity_type'], 'Branch')
        ans = res['answer']
        self.assertIn("### Branch", ans)
        self.assertIn("#### 1. About This Branch", ans)
        self.assertIn("#### 2. Overall Dropout Situation", ans)
        self.assertIn("#### 3. Fee Due Situation", ans)
        self.assertIn("#### 4. Overall Conclusion", ans)
        self.assertNotIn("Revenue vs Salary", ans)

    def test_09_branch_kakinada_1_3_statistics(self):
        handler = route_question("KAKINADA 1 dropouts, fee due, revenue vs salary statistics")
        res = handler(context={})
        self.assertEqual(res['function'], 'branch_combined_statistics')
        self.assertEqual(res['data']['entity_type'], 'Branch')
        ans = res['answer']
        self.assertIn("#### 1. About This Branch", ans)
        self.assertIn("#### 2. Overall Dropout Situation", ans)
        self.assertIn("#### 3. Fee Due Situation", ans)
        self.assertIn("#### 4. Revenue vs Salary", ans)
        self.assertIn("#### 5. Overall Conclusion", ans)
        self.assertNotIn("Teacher-Student Ratio", ans)

    def test_10_branch_sun_city_dropouts_and_str(self):
        handler = route_question("sun city dropouts and teacher student ratio statistics")
        res = handler(context={})
        self.assertEqual(res['function'], 'branch_combined_statistics')
        self.assertEqual(res['data']['entity_type'], 'Branch')
        self.assertIn("Sun City", res['data']['entity_name'])
        ans = res['answer']
        self.assertIn("#### 1. About This Branch", ans)
        self.assertIn("#### 2. Overall Dropout Situation", ans)
        self.assertIn("#### 3. Teacher-Student Ratio", ans)
        self.assertIn("#### 4. Overall Conclusion", ans)
        str_section = ans.split("#### 3. Teacher-Student Ratio")[1].split("####")[0]
        self.assertIn("23.00", str_section)

    def test_11_four_business_rules_verification(self):
        handler = route_question("RI Anitha statistics")
        res = handler(context={})
        ans = res['answer']

        # All 7 sections present when overall statistics requested
        self.assertIn("#### 1. About This RI", ans)
        self.assertIn("#### 2. Overall Dropout Situation", ans)
        self.assertIn("#### 3. Fee Due Situation", ans)
        self.assertIn("#### 4. Revenue vs Salary", ans)
        self.assertIn("#### 5. Teacher-Student Ratio", ans)
        self.assertIn("#### 6. Branch Performance", ans)
        self.assertIn("#### 7. Overall Conclusion", ans)

        # Rule A: Revenue vs Salary removes "remaining" and "surplus" text
        self.assertIn("Salary costs were", ans)
        self.assertNotIn("leaving 66.82% as remaining", ans)
        self.assertNotIn("remaining", ans.lower())

        # Rule B: Dropout Statistics leads with percentage first, count second
        self.assertIn("Overall dropout percentage is", ans)
        self.assertIn("898 dropouts this year", ans)

        # Rule C: Dropout change uses percentage points unit
        self.assertIn("percentage points", ans)
        self.assertNotIn("+-", ans)

        # Rule D: High risk branches separated from worsening & improving
        self.assertIn("High-risk branches above 10% DPP", ans)
        self.assertIn("Biggest increase in DPP", ans)

    def test_12_speech_to_text_queries(self):
        # 1. feedue
        h1 = route_question("RI anitha dropouts feedue statistics")
        r1 = h1(context={})
        self.assertEqual(r1['function'], 'ri_combined_statistics')
        self.assertEqual(r1['requested_statistics'], ['dropout', 'fee_due'])
        self.assertIn("#### 1. About This RI", r1['answer'])
        self.assertIn("#### 2. Overall Dropout Situation", r1['answer'])
        self.assertIn("#### 3. Fee Due Situation", r1['answer'])
        self.assertIn("#### 4. Overall Conclusion", r1['answer'])
        self.assertNotIn("Revenue vs Salary", r1['answer'])

        # 2. fee-do and drop outs
        h2 = route_question("RI anitha drop outs fee-do statistics")
        r2 = h2(context={})
        self.assertEqual(r2['function'], 'ri_combined_statistics')
        self.assertEqual(r2['requested_statistics'], ['dropout', 'fee_due'])

        # 3. revenue verse salary
        h3 = route_question("RI anitha revenue verse salary feedue statistics")
        r3 = h3(context={})
        self.assertEqual(r3['function'], 'ri_combined_statistics')
        self.assertEqual(r3['requested_statistics'], ['revenue_salary', 'fee_due'])
