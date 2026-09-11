from unittest import TestCase
from django.test import Client, TestCase as DjangoTestCase

from query_engine.analytics import (
    revenue_salary_ranking,
    revenue_salary_segment_comparison,
    revenue_salary_summary,
    revenue_salary_threshold_filter,
)
from query_engine.dataset_loader import load_dataset
from query_engine.orchestrator import (
    run_revenue_salary_ranking,
    run_revenue_salary_segment_comparison,
    run_revenue_salary_summary,
    run_revenue_salary_surplus,
    run_revenue_salary_threshold,
)
from query_engine.router import route_question


class RevenueVsSalaryAnalyticsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.df = load_dataset('revenue_vs_salary')

    def test_01_dataset_loaded_successfully(self):
        self.assertFalse(self.df.empty)
        self.assertIn('AGM Name', self.df.columns)
        self.assertIn('Branch', self.df.columns)
        self.assertIn('TOT_REV_N', self.df.columns)
        self.assertIn('TOT_SAL', self.df.columns)

    def test_02_overall_summary_totals(self):
        res = revenue_salary_summary(self.df, segment='TOT')
        self.assertGreater(res['branch_count'], 0)
        self.assertGreater(res['total_revenue'], 0)
        self.assertGreater(res['total_salary'], 0)
        self.assertEqual(res['surplus'], round(res['total_revenue'] - res['total_salary'], 2))

    def test_03_branch_filtering(self):
        first_branch = str(self.df['Branch'].dropna().iloc[0])
        filtered_df = self.df[self.df['Branch'] == first_branch]
        res = revenue_salary_summary(filtered_df, segment='TOT')
        self.assertEqual(res['branch_count'], 1)

    def test_04_ri_filtering(self):
        first_ri = str(self.df['RI Name'].dropna().iloc[0])
        filtered_df = self.df[self.df['RI Name'] == first_ri]
        res = revenue_salary_summary(filtered_df, segment='TOT')
        self.assertEqual(res['branch_count'], len(filtered_df))

    def test_05_zone_filtering(self):
        first_zone = str(self.df['Zone'].dropna().iloc[0])
        filtered_df = self.df[self.df['Zone'] == first_zone]
        res = revenue_salary_summary(filtered_df, segment='TOT')
        self.assertEqual(res['branch_count'], len(filtered_df))

    def test_06_agm_filtering(self):
        first_agm = str(self.df['AGM Name'].dropna().iloc[0])
        filtered_df = self.df[self.df['AGM Name'] == first_agm]
        res = revenue_salary_summary(filtered_df, segment='TOT')
        self.assertEqual(res['branch_count'], len(filtered_df))

    def test_07_segment_breakdown_and_comparison(self):
        results = revenue_salary_segment_comparison(self.df)
        self.assertEqual(len(results), 6)  # PP, LPS, UPS, HS, ACD, AD_AC
        segments = [r['segment'] for r in results]
        self.assertEqual(segments, ['PP', 'LPS', 'UPS', 'HS', 'ACD', 'AD_AC'])

    def test_08_branch_ranking_by_revenue(self):
        ranked = revenue_salary_ranking(self.df, metric='TOT_REV_N', group_col='Branch', n=5, ascending=False)
        self.assertEqual(len(ranked), 5)
        self.assertEqual(ranked[0]['rank'], 1)
        self.assertGreaterEqual(ranked[0]['total_revenue'], ranked[1]['total_revenue'])

    def test_09_branch_ranking_by_salary(self):
        ranked = revenue_salary_ranking(self.df, metric='TOT_SAL', group_col='Branch', n=5, ascending=False)
        self.assertEqual(len(ranked), 5)
        self.assertGreaterEqual(ranked[0]['total_salary'], ranked[1]['total_salary'])

    def test_10_branch_ranking_by_surplus(self):
        ranked = revenue_salary_ranking(self.df, metric='SURPLUS', group_col='Branch', n=5, ascending=False)
        self.assertEqual(len(ranked), 5)
        self.assertGreaterEqual(ranked[0]['surplus'], ranked[1]['surplus'])

    def test_11_zone_wise_aggregation(self):
        ranked = revenue_salary_ranking(self.df, metric='TOT_REV_N', group_col='Zone', n=None, ascending=False)
        self.assertGreater(len(ranked), 0)

    def test_12_ri_wise_aggregation(self):
        ranked = revenue_salary_ranking(self.df, metric='TOT_REV_N', group_col='RI Name', n=None, ascending=False)
        self.assertGreater(len(ranked), 0)

    def test_13_agm_wise_aggregation(self):
        ranked = revenue_salary_ranking(self.df, metric='TOT_REV_N', group_col='AGM Name', n=None, ascending=False)
        self.assertGreater(len(ranked), 0)

    def test_14_threshold_filter(self):
        results = revenue_salary_threshold_filter(self.df, metric='TOT_REV_N', operator='>', value=1000000.0, group_col='Branch')
        for item in results:
            self.assertGreater(item['total_revenue'], 1000000.0)

    def test_15_ratio_metric_computation(self):
        res = revenue_salary_summary(self.df, segment='TOT')
        if res['total_revenue'] > 0:
            expected_sal_v_rev = round((res['total_salary'] / res['total_revenue']) * 100, 2)
            self.assertEqual(res['salary_vs_revenue_pct'], expected_sal_v_rev)

    def test_16_surplus_formula(self):
        res = revenue_salary_summary(self.df, segment='TOT')
        self.assertEqual(res['surplus'], round(res['total_revenue'] - res['total_salary'], 2))

    def test_17_zero_denominator_safety(self):
        empty_df = self.df.head(0)
        res = revenue_salary_summary(empty_df, segment='TOT')
        self.assertEqual(res['branch_count'], 0)
        self.assertEqual(res['total_revenue'], 0.0)
        self.assertEqual(res['fee_average'], 0.0)
        self.assertEqual(res['salary_vs_revenue_pct'], 0.0)
        self.assertEqual(res['student_teacher_ratio'], 0.0)


class RevenueVsSalaryRoutingTest(TestCase):
    def test_18_natural_language_routing_samples(self):
        sample_questions = [
            "What is the total net revenue across all branches?",
            "What is the total employee salary cost?",
            "Show the top 5 branches by net revenue.",
            "Show the top 5 branches by surplus.",
            "Show the bottom 5 branches by salary vs revenue percentage.",
            "What is the cost per student for Pre Primary?",
            "Compare revenue vs salary across all academic segments.",
            "Which zone has the highest net revenue?",
            "Which AGM has the highest total surplus?",
            "List branches with total revenue greater than 1 crore.",
            "Show the student teacher ratio for Lower Primary.",
            "What is the fee average for High School?",
            "Which RI has the lowest salary vs revenue percentage?",
            "Show total employee salary cost by Zone.",
            "What is the surplus for Pre Primary?",
            "Show top 10 branches by total revenue.",
            "Show bottom 5 branches by surplus.",
            "What is the total student count in revenue vs salary dataset?",
            "What is the total employee count across branches?",
            "Show revenue vs salary summary.",
        ]
        for q in sample_questions:
            handler = route_question(q)
            self.assertIsNotNone(handler, f"Failed to route question: {q}")
            res = handler(context={})
            self.assertIn('answer', res)
            self.assertIn('data', res)


class RevenueVsSalaryAPITest(DjangoTestCase):
    def setUp(self):
        self.client = Client()

    def test_19_api_query_endpoint(self):
        payload = {"question": "What is the total net revenue?"}
        response = self.client.post("/api/query/", data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("answer", data)
        self.assertIn("data", data)
        self.assertIn("total_revenue", data["data"])
        self.assertNotIn("total_students", data["data"])  # Output Projection test

    def test_20_api_query_endpoint_with_context(self):
        payload = {
            "question": "What is the total net revenue?",
            "context": {"zone": "ZONE 1"}
        }
        response = self.client.post("/api/query/", data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("answer", data)

    def test_21_intent_based_projection_total_students(self):
        handler = route_question("What is the total student count?")
        res = handler(context={})
        self.assertTrue(res['answer'].startswith("Total Student Count"))
        self.assertIn("total_students", res['data'])
        self.assertNotIn("total_revenue", res['data'])  # Only projected metric returned!

    def test_22_intent_based_projection_segment_comparison(self):
        handler = route_question("Compare Lower Primary and Upper Primary revenue")
        res = handler(context={})
        self.assertIn("Lower Primary vs Upper Primary Revenue", res['answer'])
        self.assertEqual(len(res['data']), 2)
        self.assertEqual(res['data'][0]['segment'], 'LPS')
        self.assertEqual(res['data'][1]['segment'], 'UPS')
        self.assertIn("total_revenue", res['data'][0])

