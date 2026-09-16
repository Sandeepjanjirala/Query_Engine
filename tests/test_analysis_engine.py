from django.test import TestCase

from query_engine.analysis_engine import (
    AnalysisResult,
    build_group_analysis,
    build_lookup_analysis,
    build_ranking_analysis,
    determine_data_type,
    determine_kpi_direction,
    evaluate_status,
    format_diff_str,
    format_value_str,
)
from query_engine.formatting import render_operation_response
from query_engine.orchestrator import run_agm_statistics, run_branch_statistics, run_ri_statistics


class AnalysisEngineTests(TestCase):
    def test_kpi_direction_detection(self):
        self.assertEqual(determine_kpi_direction('CY-DPP'), 'negative')
        self.assertEqual(determine_kpi_direction('CY_A_FD'), 'negative')
        self.assertEqual(determine_kpi_direction('CY-NS'), 'positive')
        self.assertEqual(determine_kpi_direction('TOT_REV_N'), 'positive')

    def test_data_type_detection(self):
        self.assertEqual(determine_data_type('CY-DPP'), 'percentage')
        self.assertEqual(determine_data_type('CY-DP'), 'count')
        self.assertEqual(determine_data_type('CY_A_FD'), 'currency')

    def test_status_evaluation(self):
        # Negative KPI (e.g. dropouts): Increase is Worsened, Decrease is Improved
        self.assertEqual(evaluate_status(5.0, 'negative'), '🔴 Worsened')
        self.assertEqual(evaluate_status(-3.0, 'negative'), '🟢 Improved')
        self.assertEqual(evaluate_status(0.0, 'negative'), '⚪ Unchanged')
        self.assertEqual(evaluate_status(None, 'negative'), '⚪ Not Comparable')

        # Positive KPI (e.g. Net Strength / Revenue): Increase is Improved, Decrease is Worsened
        self.assertEqual(evaluate_status(100.0, 'positive'), '🟢 Improved')
        self.assertEqual(evaluate_status(-50.0, 'positive'), '🔴 Worsened')
        self.assertEqual(evaluate_status(0.0, 'positive'), '⚪ Unchanged')

    def test_number_formatting(self):
        self.assertEqual(format_value_str(12.345, 'percentage'), '12.35%')
        self.assertEqual(format_diff_str(-2.5, 'percentage'), '-2.50 percentage points')
        self.assertEqual(format_value_str(12345, 'count'), '12,345')
        self.assertEqual(format_diff_str(12, 'count'), '+12')
        self.assertEqual(format_diff_str(None, 'percentage'), 'N/A')

    def test_operation_aware_ranking_response(self):
        sample_data = [
            {'rank': 1, 'branch': 'NARSIPATNAM', 'current_year': 32.5, 'previous_year': 30.0, 'difference': 2.5},
            {'rank': 2, 'branch': 'YALAMANCHILI', 'current_year': 28.1, 'previous_year': 31.0, 'difference': -2.9},
        ]
        analysis = build_ranking_analysis(sample_data, metric='CY-DPP', ascending=False, group_dimension='Branch')
        self.assertIsInstance(analysis, AnalysisResult)
        self.assertIn("Highest CY-DPP Branches", analysis.direct_answer)
        self.assertEqual(analysis.rows[0][5], '🔴 Worsened')
        self.assertEqual(analysis.rows[1][5], '🟢 Improved')

        formatted = render_operation_response(analysis)
        self.assertIn("### Detailed Evidence", formatted)
        self.assertIn("| Rank | Branch | Current Year | Last Year | Change | Status |", formatted)
        self.assertIn("NARSIPATNAM", formatted)
        self.assertIn("YALAMANCHILI", formatted)

    def test_concise_lookup_response(self):
        sample_data = [
            {'branch': 'KAKINADA 1', 'current_year': 15.17, 'previous_year': 11.78, 'difference': 3.39}
        ]
        analysis = build_lookup_analysis(sample_data, columns=['CY-DPP'])
        formatted = render_operation_response(analysis)
        self.assertIn("KAKINADA 1", formatted)
        self.assertIn("15.17%", formatted)
        self.assertIn("Status: 🔴 Worsened", formatted)

    def test_overall_ri_review(self):
        res = run_ri_statistics({}, context={'ri': 'K.Srinivasa Rao'})
        self.assertEqual(res['function'], 'ri_combined_statistics')
        answer = res['answer']
        self.assertIn("RI K. Srinivasa Rao — Statistics", answer)
        self.assertIn("1. About This RI", answer)
        self.assertIn("2. Overall Dropout Situation", answer)
        self.assertIn("3. Fee Due Situation", answer)
        self.assertIn("4. Revenue vs Salary", answer)
        self.assertIn("5. Teacher-Student Ratio", answer)
        self.assertIn("6. Branch Performance", answer)
        self.assertIn("7. Overall Conclusion", answer)
        self.assertIn("percentage points", answer)

    def test_overall_agm_review(self):
        res = run_agm_statistics({}, context={'agm': 'G.V.Ramana Rao'})
        self.assertEqual(res['function'], 'agm_combined_statistics')
        answer = res['answer']
        self.assertIn("AGM G. V. Ramana Rao — Statistics", answer)
        self.assertIn("1. About This AGM", answer)
        self.assertIn("2. Overall Dropout Situation", answer)
        self.assertIn("3. Fee Due Situation", answer)
        self.assertIn("4. Revenue vs Salary", answer)
        self.assertIn("5. Teacher-Student Ratio", answer)
        self.assertIn("6. Branch Performance", answer)
        self.assertIn("7. Overall Conclusion", answer)
        self.assertIn("percentage points", answer)

    def test_overall_branch_review(self):
        res = run_branch_statistics({}, context={'branch': 'SUCHITRA'})
        self.assertEqual(res['function'], 'branch_combined_statistics')
        answer = res['answer']
        self.assertIn("Branch SUCHITRA — Statistics", answer)
        self.assertIn("1. About This Branch", answer)
        self.assertIn("2. Overall Dropout Situation", answer)
        self.assertIn("3. Fee Due Situation", answer)
        self.assertIn("4. Revenue vs Salary", answer)
        self.assertIn("5. Teacher-Student Ratio", answer)
        self.assertIn("6. Branch Performance", answer)
        self.assertIn("7. Overall Conclusion", answer)
        self.assertIn("percentage points", answer)

    def test_domain_dropout_statistics_routing(self):
        from query_engine.router import route_question
        res1 = route_question("RI Srinivasa Dropouts statistics")({})
        self.assertEqual(res1['function'], 'ri_dropout_statistics')

        res2 = route_question("AGM Ramana Dropouts statistics")({})
        self.assertEqual(res2['function'], 'agm_dropout_statistics')

        res3 = route_question("Zone Kompally Dropouts statistics")({})
        self.assertEqual(res3['function'], 'zone_dropout_statistics')

        res4 = route_question("SUCHITRA Dropouts statistics")({})
        self.assertEqual(res4['function'], 'branch_dropout_statistics')
