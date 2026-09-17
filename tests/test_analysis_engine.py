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

    def test_null_historical_data_handling(self):
        sample_data = [
            {'rank': 1, 'branch': 'NEW_BRANCH', 'current_year': 14.5, 'previous_year': None, 'difference': None}
        ]
        analysis = build_ranking_analysis(sample_data, metric='CY-DPP', ascending=False, group_dimension='Branch')
        formatted = render_operation_response(analysis)
        self.assertEqual(analysis.rows[0][3], 'N/A')
        self.assertEqual(analysis.rows[0][4], 'N/A')
        self.assertEqual(analysis.rows[0][5], '⚪ Not Comparable')
        self.assertIn("| 1 | NEW_BRANCH | 14.50% | N/A | N/A | ⚪ Not Comparable |", formatted)

    def test_yoy_direction_negative_filtering(self):
        import pandas as pd
        from query_engine.analytics import year_over_year_ranking
        test_df = pd.DataFrame([
            {'Branch': 'Branch A', 'CY-DPP': 15.0, 'LY-DPP': 10.0},  # change = +5.0 (worse)
            {'Branch': 'Branch B', 'CY-DPP': 8.0, 'LY-DPP': 12.0},   # change = -4.0 (reduced)
            {'Branch': 'Branch C', 'CY-DPP': 5.0, 'LY-DPP': 7.0},    # change = -2.0 (reduced)
        ])
        # Asking for negative change (reduction in dropouts)
        res = year_over_year_ranking(test_df, 'CY-DPP', 'LY-DPP', n=5, ascending=True, direction='negative')
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]['branch'], 'Branch B')
        self.assertEqual(res[0]['change'], -4.0)
        self.assertEqual(res[1]['branch'], 'Branch C')
        self.assertEqual(res[1]['change'], -2.0)
        # Ensure positive change was excluded
        self.assertNotIn('Branch A', [r['branch'] for r in res])

    def test_numbered_branch_and_negative_entity_resolution(self):
        from query_engine.params import resolve_single_entity
        candidates = ['Kompally', 'Kompally 2', 'Kompally 4', 'TOLICHOWKI 1', 'MEDCHAL']
        self.assertEqual(resolve_single_entity('Kompally branch', candidates, 'branch'), 'Kompally')
        self.assertEqual(resolve_single_entity('Kompally 2 branch', candidates, 'branch'), 'Kompally 2')
        self.assertEqual(resolve_single_entity('Kompally two branch', candidates, 'branch'), 'Kompally 2')
        self.assertEqual(resolve_single_entity('Tolichowki branch', candidates, 'branch'), 'TOLICHOWKI 1')
        self.assertEqual(resolve_single_entity('Tolichowki 1 branch', candidates, 'branch'), 'TOLICHOWKI 1')
        self.assertIsNone(resolve_single_entity('Bobby Lee branch', candidates, 'branch'))

    def test_unknown_branch_query_routing(self):
        from query_engine.router import route_question
        handler = route_question("Bobby Lee branch dropout percentage")
        res = handler({})
        self.assertEqual(res['function'], 'entity_not_found')
        self.assertIn("couldn't find a matching branch for 'Bobby Lee'", res['answer'])

    def test_fee_scalar_and_count_disambiguation_under_agm(self):
        from query_engine.router import route_question
        # 1. Scalar fee due under AGM Ramana Rao -> returns 1,536,186.0 without top-5 ranking
        h_scalar = route_question("What is the current year fee due under AGM Ramana Rao?")
        res_scalar = h_scalar({})
        self.assertEqual(res_scalar.get('function'), 'fee_summary')
        self.assertEqual(res_scalar.get('capability'), 'fee_total')
        self.assertEqual(res_scalar['data'][0].get('CY_A_FD'), 1536186.0)
        self.assertNotIn("top 5", res_scalar['answer'].lower())
        self.assertIn("1,536,186", res_scalar['answer'])

        # 2. Student count with fee due -> returns 78 (CY_A_FDC)
        h_count = route_question("How many students have current year fee due under AGM Ramana Rao?")
        res_count = h_count({})
        self.assertEqual(res_count.get('function'), 'fee_summary')
        self.assertEqual(res_count.get('capability'), 'fee_due_count')
        self.assertEqual(res_count['data'][0].get('CY_A_FDC'), 78)
        self.assertIn("78", res_count['answer'])

        # 3. Zero-paid count -> returns 1357 (CY_ZP)
        h_zp_cnt = route_question("How many students have zero-paid fees under AGM Ramana Rao?")
        res_zp_cnt = h_zp_cnt({})
        self.assertEqual(res_zp_cnt.get('function'), 'fee_summary')
        self.assertEqual(res_zp_cnt.get('capability'), 'zero_paid_count')
        self.assertEqual(res_zp_cnt['data'][0].get('CY_ZP'), 1357)

        # 4. Zero-paid balance -> returns 82,638,454.0 (CY_ZP_FD)
        h_zp_bal = route_question("What is the zero-paid fee due balance under AGM Ramana Rao?")
        res_zp_bal = h_zp_bal({})
        self.assertEqual(res_zp_bal.get('function'), 'fee_summary')
        self.assertEqual(res_zp_bal.get('capability'), 'zero_paid_fee_due')
        self.assertEqual(res_zp_bal['data'][0].get('CY_ZP_FD'), 82638454.0)
        self.assertIn("82,638,454", res_zp_bal['answer'])

    def test_school_level_comparison_under_agm(self):
        from query_engine.router import route_question
        h_level = route_question("Which school level has the highest dropout percentage under AGM Ramana Rao?")
        res_level = h_level({})
        self.assertEqual(res_level.get('function'), 'compare_dimensions')
        categories = [r.get('category') for r in res_level['data']]
        self.assertIn('PS', categories)
        self.assertIn('PP', categories)
        self.assertIn('HS', categories)

    def test_ri_comparison_weighted_ratio_not_additive_sum(self):
        from query_engine.router import route_question
        # 1. Single year group aggregate
        h_ri = route_question("Compare dropout percentage by RI under AGM Ramana Rao")
        res_ri = h_ri({})
        self.assertEqual(res_ri.get('function'), 'group_metric_aggregate')
        for row in res_ri['data']:
            val = row.get('value')
            if val is not None:
                self.assertLess(val, 100.0, f"RI group metric aggregate has impossible DPP: {val}%")

        # 2. YoY comparison across RIs
        h_yoy = route_question("Compare 2024-25 and 2025-26 dropout percentage by RI under AGM Ramana Rao")
        res_yoy = h_yoy({})
        self.assertEqual(res_yoy.get('function'), 'compare_dimensions')
        for row in res_yoy['data']:
            cy_val = row.get('Current Year')
            if cy_val is not None:
                self.assertLess(cy_val, 100.0, f"RI YoY comparison has impossible DPP: {cy_val}%")
                self.assertGreater(cy_val, 0.0)



