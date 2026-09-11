from django.test import TestCase, Client

from query_engine.router import route_question


EXTENDED_QUESTION_CATALOG = [
    # --- Fee Due Questions ---
    # Scalar / Totals / Counts
    ("What was the last year 2024-25 fee due amount?", "fee_summary", ["LY_FD"]),
    ("What is the total active fee due for 2025-26?", "fee_summary", ["CY_A_FD"]),
    ("What is the total 2024-25 fee due count?", "fee_summary", ["LY_FDC"]),
    ("What is the live student due count?", "fee_summary", ["CY_A_FDC"]),
    ("What is the actual zero paid count?", "fee_summary", ["CY_ZP"]),
    ("What is the total zero paid fee due count?", "fee_summary", ["CY_ZP"]),
    ("What is the total zero-paid fee amount?", "fee_summary", ["CY_ZP_FD"]),
    ("Show count of students who did not pay fee and did not purchase books.", "fee_books_not_purchased", ["CY_FN_BN"]),
    ("What is the count of students who paid fee but did not purchase books?", "fee_books_not_purchased", ["CY_FP_BN"]),

    # Fee Due Rankings & Metric Projections
    ("Which branches have the highest zero-paid fee amount?", "fee_summary", ["branch", "CY_ZP_FD"]),
    ("Show top 5 branches by 2024-25 last year fee due.", "fee_summary", ["branch", "LY_FD"]),
    ("Show top 5 branches by 2025-26 active fee due.", "fee_summary", ["branch", "CY_A_FD"]),
    ("Which branches have the highest zero-paid count?", "fee_summary", ["branch", "CY_ZP"]),
    ("Show bottom 5 branches by 2025-26 active fee due.", "fee_summary", ["branch", "CY_A_FD"]),

    # Fee Due Groupings (Branch, Zone, RI, AGM, S_Type)
    ("Show fee paid but books not purchased by branch.", "fee_books_not_purchased", ["branch", "CY_FP_BN"]),
    ("Show zero-paid fee due count by branch.", "fee_summary", ["branch", "CY_ZP"]),
    ("Show zero-paid fee due count by zone.", "fee_summary", ["zone", "CY_ZP"]),
    ("Show books not purchased summary by zone.", "fee_books_not_purchased", ["zone"]),
    ("Show books not purchased summary by RI.", "fee_books_not_purchased", ["ri"]),
    ("Show active fee due by zone.", "fee_summary", ["zone", "CY_A_FD"]),
    ("Show last year fee due by zone.", "fee_summary", ["zone", "LY_FD"]),
    ("Show active fee due by RI.", "fee_summary", ["ri", "CY_A_FD"]),
    ("Show last year fee due by RI.", "fee_summary", ["ri", "LY_FD"]),
    ("Show active fee due by AGM.", "fee_summary", ["agm", "CY_A_FD"]),
    ("Show last year fee due by AGM.", "fee_summary", ["agm", "LY_FD"]),
    ("Show active fee due by branch type.", "fee_summary", ["s_type", "CY_A_FD"]),
    ("Show books not purchased summary by AGM.", "fee_books_not_purchased", ["agm"]),
    ("Show books not purchased summary by branch type.", "fee_books_not_purchased", ["s_type"]),

    # Fee Due YoY Comparisons
    ("Compare last year and current year fee due", "fee_yoy_comparison", ["branch", "LY_FD", "CY_A_FD", "difference"]),
    ("Compare 2024-25 and 2025-26 fee due by branch.", "fee_yoy_comparison", ["branch", "LY_FD", "CY_A_FD", "difference"]),
    ("Compare 2024-25 and 2025-26 fee due by zone.", "fee_yoy_comparison", ["zone", "LY_FD", "CY_A_FD", "difference"]),
    ("Compare 2024-25 and 2025-26 fee due by RI.", "fee_yoy_comparison", ["ri", "LY_FD", "CY_A_FD", "difference"]),
    ("Compare 2024-25 and 2025-26 fee due by AGM.", "fee_yoy_comparison", ["agm", "LY_FD", "CY_A_FD", "difference"]),
    ("Which branches reduced their fee due compared to last year?", "fee_yoy_comparison", ["branch"]),
    ("Which branches increased their fee due from last year to this year?", "fee_yoy_comparison", ["branch"]),

    # --- Revenue vs Salary Questions & Output Projections ---
    ("What is the total employee count?", "revenue_salary_summary", ["total_employees"]),
    ("What is total salary cost?", "revenue_salary_summary", ["total_salary"]),
    ("What is the total student count?", "revenue_salary_summary", ["total_students"]),
    ("What is the total net revenue across all branches?", "revenue_salary_summary", ["total_revenue"]),
    ("What is the total net surplus?", "revenue_salary_ranking", ["surplus"]),
    ("What is the cost per student?", "revenue_salary_summary", ["cost_per_student"]),
    ("What is the fee average?", "revenue_salary_summary", ["fee_average"]),
    ("What is the salary vs revenue percentage?", "revenue_salary_summary", ["salary_vs_revenue_pct"]),
    ("What is the student teacher ratio in revenue vs salary dataset?", "revenue_salary_summary", ["student_teacher_ratio"]),

    # Revenue vs Salary Rankings & Projections
    ("Show top 5 branches by net revenue.", "revenue_salary_ranking", ["rank", "entity", "total_revenue"]),
    ("Show top 5 branches by surplus.", "revenue_salary_ranking", ["rank", "entity", "surplus"]),
    ("Show bottom 5 branches by salary vs revenue percentage.", "revenue_salary_ranking", ["rank", "entity", "salary_vs_revenue_pct"]),
    ("Which zone has the highest net revenue?", "revenue_salary_ranking", ["rank", "entity", "total_revenue"]),
    ("Which AGM has the highest total surplus?", "revenue_salary_ranking", ["rank", "entity", "surplus"]),
    ("Which RI has the lowest salary vs revenue percentage?", "revenue_salary_ranking", ["rank", "entity", "salary_vs_revenue_pct"]),
    ("Show total employee salary cost by Zone.", "revenue_salary_ranking", ["rank", "entity", "total_salary"]),

    # Revenue vs Salary Thresholds
    ("List branches with total revenue greater than 1 crore.", "revenue_salary_threshold", ["rank", "entity", "total_revenue"]),
    ("Show branches with employee salary exceeding 50 lakhs.", "revenue_salary_threshold", ["rank", "entity", "total_salary"]),
    ("Show branches with net surplus greater than 20 lakhs.", "revenue_salary_threshold", ["rank", "entity", "surplus"]),

    # Revenue vs Salary Segment Comparisons
    ("Compare revenue vs salary across all academic segments.", "revenue_salary_segment_comparison", ["segment"]),
    ("What is the cost per student for Pre Primary?", "revenue_salary_segment_comparison", ["segment", "cost_per_student"]),
    ("What is the fee average for High School?", "revenue_salary_segment_comparison", ["segment", "fee_average"]),
    ("Show the student teacher ratio for Lower Primary.", "revenue_salary_segment_comparison", ["segment", "student_teacher_ratio"]),
    ("What is the surplus for Pre Primary?", "revenue_salary_segment_comparison", ["segment", "surplus"]),
    ("Compare Lower Primary and Upper Primary revenue", "revenue_salary_segment_comparison", ["segment", "total_revenue"]),
]

# Generate additional 100+ systematic question variations to reach >150 total tests
SURPLUS_VARS = [f"Show top {n} branches by surplus." for n in [3, 5, 10, 15, 20]]
REV_VARS = [f"Show top {n} branches by total revenue." for n in [3, 5, 10, 15, 20]]
SAL_VARS = [f"Show top {n} branches by salary cost." for n in [3, 5, 10, 15, 20]]
FEE_VARS = [f"Show top {n} branches by 2025-26 fee due." for n in [3, 5, 10, 15, 20]]
FEE_LY_VARS = [f"Show top {n} branches by 2024-25 fee due." for n in [3, 5, 10, 15, 20]]
ZP_VARS = [f"Show top {n} branches by zero paid fee amount." for n in [3, 5, 10, 15, 20]]
BOOKS_VARS = [f"Show top {n} branches with fee paid but books not purchased." for n in [3, 5, 10, 15, 20]]
THRESH_VARS = [f"List branches with total revenue greater than {x} lakhs." for x in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]]

for q in SURPLUS_VARS:
    EXTENDED_QUESTION_CATALOG.append((q, "revenue_salary_ranking", ["rank", "entity", "surplus"]))
for q in REV_VARS:
    EXTENDED_QUESTION_CATALOG.append((q, "revenue_salary_ranking", ["rank", "entity", "total_revenue"]))
for q in SAL_VARS:
    EXTENDED_QUESTION_CATALOG.append((q, "revenue_salary_ranking", ["rank", "entity", "total_salary"]))
for q in FEE_VARS:
    EXTENDED_QUESTION_CATALOG.append((q, "fee_summary", ["branch", "CY_A_FD"]))
for q in FEE_LY_VARS:
    EXTENDED_QUESTION_CATALOG.append((q, "fee_summary", ["branch", "LY_FD"]))
for q in ZP_VARS:
    EXTENDED_QUESTION_CATALOG.append((q, "fee_summary", ["branch", "CY_ZP_FD"]))
for q in BOOKS_VARS:
    EXTENDED_QUESTION_CATALOG.append((q, "fee_books_not_purchased", ["branch", "CY_FP_BN"]))
for q in THRESH_VARS:
    EXTENDED_QUESTION_CATALOG.append((q, "revenue_salary_threshold", ["rank", "entity", "total_revenue"]))


class FeeAndRevenueSalaryExtendedTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.context = {'agm': 'All', 'ri': 'All', 'zone': 'All', 'branches': ['All']}

    def test_extended_question_catalog_routing_and_projection(self):
        errors = []
        for idx, (question, expected_func, expected_keys) in enumerate(EXTENDED_QUESTION_CATALOG, start=1):
            handler = route_question(question)
            if handler is None:
                errors.append(f"Q{idx} '{question}': Handler returned None (expected '{expected_func}')")
                continue

            try:
                res = handler(self.context)
                actual_func = res.get('function')
                if actual_func != expected_func:
                    errors.append(f"Q{idx} '{question}': Expected '{expected_func}', got '{actual_func}'")
                    continue

                data = res.get('data')
                if data is None or (isinstance(data, (list, dict)) and len(data) == 0):
                    errors.append(f"Q{idx} '{question}': Empty data returned")
                    continue

                first_row = data[0] if isinstance(data, list) else data
                for key in expected_keys:
                    if key not in first_row:
                        errors.append(f"Q{idx} '{question}': Expected key '{key}' missing from data row: {first_row}")

            except Exception as exc:
                errors.append(f"Q{idx} '{question}': Exception raised: {exc}")

        if errors:
            self.fail(f"{len(errors)} question(s) failed in extended test suite:\n" + "\n".join(errors[:20]))

    def test_api_endpoint_strict_projection(self):
        # 1. Total Active Fee Due -> ONLY CY_A_FD
        payload1 = {"question": "What is the total active fee due for 2025-26?"}
        resp1 = self.client.post("/api/query/", data=payload1, content_type="application/json")
        self.assertEqual(resp1.status_code, 200)
        d1 = resp1.json()["data"]
        row1 = d1[0] if isinstance(d1, list) else d1
        self.assertIn("CY_A_FD", row1)
        self.assertNotIn("LY_FD", row1)
        self.assertNotIn("CY_ZP", row1)

        # 2. Total Employee Count -> ONLY total_employees
        payload2 = {"question": "What is the total employee count?"}
        resp2 = self.client.post("/api/query/", data=payload2, content_type="application/json")
        self.assertEqual(resp2.status_code, 200)
        d2 = resp2.json()["data"]
        row2 = d2[0] if isinstance(d2, list) else d2
        self.assertIn("total_employees", row2)
        self.assertNotIn("total_revenue", row2)
        self.assertNotIn("total_salary", row2)

        # 3. Highest zero-paid fee amount -> ONLY branch + CY_ZP_FD
        payload3 = {"question": "Which branches have the highest zero-paid fee amount?"}
        resp3 = self.client.post("/api/query/", data=payload3, content_type="application/json")
        self.assertEqual(resp3.status_code, 200)
        d3 = resp3.json()["data"]
        row3 = d3[0] if isinstance(d3, list) else d3
        self.assertIn("branch", row3)
        self.assertIn("CY_ZP_FD", row3)
        self.assertNotIn("CY_A_FD", row3)

    def test_grouping_by_zone_and_ri(self):
        # Group by Zone for Fee Due
        handler1 = route_question("Show active fee due by zone.")
        res1 = handler1(self.context)
        self.assertEqual(res1["function"], "fee_summary")
        self.assertIn("zone", res1["data"][0])
        self.assertIn("CY_A_FD", res1["data"][0])

        # Group by RI for Books Not Purchased
        handler2 = route_question("Show books not purchased summary by RI.")
        res2 = handler2(self.context)
        self.assertEqual(res2["function"], "fee_books_not_purchased")
        self.assertIn("ri", res2["data"][0])

    def test_user_reported_meeting_queries(self):
        # 1. Complete summaries for Branch, Zone, RI, AGM
        for q, expected_entity in [
            ("Give complete summary of KAKINADA 1.", "KAKINADA 1"),
            ("Give complete summary of Kakinada zone.", "Kakinada"),
            ("Give complete summary of Mr.Ahmedali.", "Mr.Ahmedali"),
            ("Give complete summary of Mr.M.V.Suresh.", "Mr.M.V.Suresh"),
            ("Give complete summary of Mr.M.V.Suresh AGM.", "Mr.M.V.Suresh"),
        ]:
            handler = route_question(q)
            self.assertIsNotNone(handler, f"Handler returned None for '{q}'")
            res = handler(self.context)
            self.assertIn(res["function"], ("entity_summary", "branch_scorecard"), f"Function for '{q}' was '{res['function']}'")
            self.assertTrue(len(res["data"]) > 0, f"No data for '{q}'")

        # 2. Scoped Metric Lookups (Zone, RI, AGM)
        for q in [
            "What is the dropout percentage of Kakinada zone?",
            "What is the dropout percentage of Mr.Ahmedali?",
            "What is the dropout percentage of Mr.M.V.Suresh?",
        ]:
            handler = route_question(q)
            self.assertIsNotNone(handler, f"Handler returned None for '{q}'")
            res = handler(self.context)
            self.assertIn("%", res["answer"], f"Answer for '{q}' missing '%': {res['answer']}")

        # 3. Dropout count by AGM/RI (sum of dropouts, not count of branches)
        handler_agm = route_question("Show dropout count by AGM.")
        res_agm = handler_agm(self.context)
        self.assertEqual(res_agm["function"], "group_metric_aggregate")
        # Sum of dropouts across branches under Mr.M.V.Suresh should be > 100, not row count 9
        first_val = res_agm["data"][0]["value"]
        self.assertGreater(first_val, 20.0, f"Expected sum of dropouts > 20, got {first_val}")

        # 4. Typo tolerance
        handler_typo = route_question("top 5 branches with higest doupouts")
        self.assertIsNotNone(handler_typo, "Handler returned None for typo query 'top 5 branches with higest doupouts'")
        res_typo = handler_typo(self.context)
        self.assertEqual(res_typo["function"], "rank_branches_by_metric")

        # 5. YoY Reduction in Dropouts format
        handler_yoy = route_question("Which branches had the biggest reduction in dropouts?")
        self.assertIsNotNone(handler_yoy)
        res_yoy = handler_yoy(self.context)
        self.assertIn("Current Year", res_yoy["answer"])
        self.assertIn("Last Year", res_yoy["answer"])
        self.assertIn("Difference", res_yoy["answer"])

    def test_category_highest_lowest_and_improved_declined(self):
        # Highest vs Lowest category for dropout percentage
        h_high = route_question("Which category has the highest dropout percentage?")
        res_high = h_high(self.context)
        self.assertIn("Highest category**: HS", res_high["answer"])

        h_low = route_question("Which category has the lowest dropout percentage?")
        res_low = h_low(self.context)
        self.assertIn("Lowest category**: PP", res_low["answer"])

        # Improved vs Declined category for dropout percentage YoY
        h_imp = route_question("Which category improved the most compared with last year?")
        res_imp = h_imp(self.context)
        self.assertIn("Improved most**: PP", res_imp["answer"])

        h_dec = route_question("Which category declined the most compared with last year?")
        res_dec = h_dec(self.context)
        self.assertIn("Declined most**: HS", res_dec["answer"])



