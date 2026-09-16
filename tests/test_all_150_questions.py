"""
Exhaustive test suite verifying that all 150 questions from the question bank
route to the correct reusable pre-function capability and execute successfully.
"""
from django.test import SimpleTestCase

from query_engine.router import route_question


ALL_150_QUESTIONS = [
    # 1. Ranking / Top-Bottom N
    (1, "Which are the top 5 branches by dropout percentage?", "top_5_dropout_branches"),
    (2, "Show the top 10 branches with the highest dropout percentage.", "rank_branches_by_metric"),
    (3, "Which branches have the lowest dropout percentage?", "rank_branches_by_metric"),
    (4, "Show the bottom 5 branches by dropout percentage.", "rank_branches_by_metric"),
    (5, "Which are the top 10 branches by dropout count?", "rank_branches_by_metric"),
    (6, "Show the branches with the highest number of dropouts.", "rank_branches_by_metric"),
    (7, "Which 5 branches have the lowest dropout count?", "rank_branches_by_metric"),
    (8, "Show the top 5 branches by net strength.", "rank_branches_by_metric"),
    (9, "Which branches have the highest current-year strength?", "rank_branches_by_metric"),
    (10, "Show the bottom 10 branches by net strength.", "rank_branches_by_metric"),
    (11, "Which branches have the highest number of sections?", "rank_branches_by_metric"),
    (12, "Show the top 5 branches by section count.", "rank_branches_by_metric"),
    (13, "Which branches have the fewest sections?", "rank_branches_by_metric"),
    (14, "Show the top 10 branches by average strength per section.", "rank_branches_by_metric"),
    (15, "Which branches have the lowest average strength per section?", "rank_branches_by_metric"),
    (16, "Show the top 5 branches by empty rooms.", "rank_branches_by_metric"),
    (17, "Which branches have the most vacant rooms?", "rank_branches_by_metric"),
    (18, "Show the bottom 5 branches by empty rooms.", "rank_branches_by_metric"),
    (19, "Which branches have the highest staff count?", "rank_branches_by_metric"),
    (20, "Show the top 10 branches by staff count.", "rank_branches_by_metric"),
    (21, "Which branches have the highest student-teacher ratio?", "rank_branches_by_metric"),
    (22, "Show the top 5 branches by STR.", "rank_branches_by_metric"),
    (23, "Which branches have the lowest student-teacher ratio?", "rank_branches_by_metric"),
    (24, "Show the bottom 10 branches by STR.", "rank_branches_by_metric"),
    (25, "Which RIs have the highest dropout percentage?", "group_metric_aggregate"),
    (26, "Show the top 5 RIs by dropout count.", "group_metric_aggregate"),
    (27, "Which zones have the highest dropout percentage?", "group_metric_aggregate"),
    (28, "Show the top 5 zones by net strength.", "group_metric_aggregate"),
    (29, "Which AGMs have the highest total dropouts?", "group_metric_aggregate"),
    (30, "Show the top 10 branches by current-year strength.", "rank_branches_by_metric"),

    # 2. Branch / Entity Lookup
    (31, "Show the complete summary of HMT Colony branch.", "branch_scorecard"),
    (32, "Give me all metrics for this branch.", "branch_scorecard"),
    (33, "What is the dropout percentage of HMT Colony?", "branch_metric_lookup"),
    (34, "How many students dropped out from HMT Colony?", "branch_metric_lookup"),
    (35, "What is the current strength of HMT Colony?", "branch_metric_lookup"),
    (36, "What was the previous-year strength of HMT Colony?", "branch_metric_lookup"),
    (37, "How many sections does HMT Colony have?", "branch_metric_lookup"),
    (38, "What is the average strength per section at HMT Colony?", "branch_metric_lookup"),
    (39, "How many rooms are occupied at HMT Colony?", "branch_metric_lookup"),
    (40, "How many empty rooms does HMT Colony have?", "branch_metric_lookup"),
    (41, "What is the staff count at HMT Colony?", "branch_metric_lookup"),
    (42, "What is the student-teacher ratio at HMT Colony?", "branch_metric_lookup"),
    (43, "Show the dropout and strength details for HMT Colony.", "branch_metric_lookup"),
    (44, "Show the room and section details for HMT Colony.", "branch_metric_lookup"),
    (45, "Give me the current and previous-year metrics for HMT Colony.", "branch_metric_lookup"),

    # 3. Grouped Aggregates
    (46, "What is the total dropout count by RI?", "group_metric_aggregate"),
    (47, "Show dropout percentage by RI.", "group_metric_aggregate"),
    (48, "What is the total dropout count by zone?", "group_metric_aggregate"),
    (49, "Show dropout percentage by zone.", "group_metric_aggregate"),
    (50, "What is the total dropout count by AGM?", "group_metric_aggregate"),
    (51, "Show the total current-year strength by RI.", "group_metric_aggregate"),
    (52, "Show the total previous-year strength by RI.", "group_metric_aggregate"),
    (53, "What is the total strength by zone?", "group_metric_aggregate"),
    (54, "Show the total number of sections by RI.", "group_metric_aggregate"),
    (55, "Show the total number of sections by zone.", "group_metric_aggregate"),
    (56, "What is the total number of empty rooms by RI?", "group_metric_aggregate"),
    (57, "Show empty rooms by zone.", "group_metric_aggregate"),
    (58, "What is the total staff count by RI?", "group_metric_aggregate"),
    (59, "Show staff count by zone.", "group_metric_aggregate"),
    (60, "Show student-teacher ratio by RI.", "group_metric_aggregate"),
    (61, "Show student-teacher ratio by zone.", "group_metric_aggregate"),
    (62, "What is the average strength per section by RI?", "group_metric_aggregate"),
    (63, "Show average strength per section by zone.", "group_metric_aggregate"),
    (64, "Show branch-wise dropout totals.", "branch_metric_lookup"),
    (65, "Show branch-wise strength totals.", "branch_metric_lookup"),

    # 4. Year-over-Year CY vs LY
    (66, "Which branches improved their dropout percentage compared with last year?", "year_over_year_change_ranking"),
    (67, "Which branches had a higher dropout percentage than last year?", "year_over_year_change_ranking"),
    (68, "Which branches reduced their dropout percentage from LY to CY?", "year_over_year_change_ranking"),
    (69, "Which branches increased their dropout percentage from LY to CY?", "year_over_year_change_ranking"),
    (70, "Which branches declined compared with last year?", "year_over_year_change_ranking"),
    (71, "Which branches improved compared with last year?", "year_over_year_change_ranking"),
    (72, "Compare current-year and previous-year dropout percentage by branch.", "year_over_year_change_ranking"),
    (73, "Compare CY and LY dropout counts by branch.", "year_over_year_change_ranking"),
    (74, "Show the change in dropout percentage from LY to CY.", "year_over_year_change_ranking"),
    (75, "Show the top 5 branches with the biggest improvement in dropout percentage.", "year_over_year_change_ranking"),
    (76, "Show the top 5 branches with the biggest increase in dropout percentage.", "year_over_year_change_ranking"),
    (77, "Which branches had the biggest reduction in dropouts?", "year_over_year_change_ranking"),
    (78, "Which branches had the biggest increase in dropouts?", "year_over_year_change_ranking"),
    (79, "Compare current-year and previous-year strength by branch.", "year_over_year_change_ranking"),
    (80, "Which branches increased their strength compared with last year?", "year_over_year_change_ranking"),
    (81, "Which branches lost strength compared with last year?", "year_over_year_change_ranking"),
    (82, "Show branches with increased sections compared with LY.", "year_over_year_change_ranking"),
    (83, "Show branches with reduced sections compared with LY.", "year_over_year_change_ranking"),
    (84, "Compare CY and LY staff count by branch.", "year_over_year_change_ranking"),
    (85, "Compare CY and LY STR by branch.", "year_over_year_change_ranking"),

    # 5. Threshold Questions
    (86, "Which branches have dropout percentage above 15%?", "filter_by_threshold"),
    (87, "Show branches with dropout percentage greater than 10%.", "filter_by_threshold"),
    (88, "Which branches have dropout percentage below 5%?", "filter_by_threshold"),
    (89, "Show branches with dropout percentage less than 3%.", "filter_by_threshold"),
    (90, "How many branches have dropout percentage above 15%?", "filter_by_threshold"),
    (91, "How many RIs have dropout percentage above 10%?", "filter_by_threshold"),
    (92, "Which branches have more than 5 empty rooms?", "filter_by_threshold"),
    (93, "How many branches have more than 10 empty rooms?", "filter_by_threshold"),
    (94, "Which branches have fewer than 3 empty rooms?", "filter_by_threshold"),
    (95, "Which branches have STR greater than 30?", "filter_by_threshold"),
    (96, "Show branches where STR is above 25.", "filter_by_threshold"),
    (97, "How many branches have STR below 20?", "filter_by_threshold"),
    (98, "Which branches have more than 10 sections?", "filter_by_threshold"),
    (99, "Show branches with fewer than 5 sections.", "filter_by_threshold"),
    (100, "Which branches have current strength greater than 500?", "filter_by_threshold"),

    # 6. PP / PS / HS Comparison
    (101, "Compare dropout percentage between PP, PS and HS.", "compare_dimensions"),
    (102, "Which category has the highest dropout percentage?", "compare_dimensions"),
    (103, "Which category has the lowest dropout percentage?", "compare_dimensions"),
    (104, "Compare PP, PS and HS dropout counts.", "compare_dimensions"),
    (105, "Which category has the highest strength?", "compare_dimensions"),
    (106, "Compare PP, PS and HS sections.", "compare_dimensions"),
    (107, "Which category has the highest average strength per section?", "compare_dimensions"),
    (108, "Compare PP, PS and HS STR.", "compare_dimensions"),
    (109, "Which category has the highest student-teacher ratio?", "compare_dimensions"),
    (110, "Which category has the lowest student-teacher ratio?", "compare_dimensions"),
    (111, "Compare PP, PS and HS current-year strength.", "compare_dimensions"),
    (112, "Compare PP, PS and HS previous-year strength.", "compare_dimensions"),
    (113, "Show CY vs LY dropout percentage for PP, PS and HS.", "compare_dimensions"),
    (114, "Which category improved the most compared with last year?", "compare_dimensions"),
    (115, "Which category declined the most compared with last year?", "compare_dimensions"),

    # 7. Existing vs New / E-N
    (116, "Compare existing and new student dropout percentage.", "compare_dimensions"),
    (117, "What is the dropout percentage for existing students?", "compare_dimensions"),
    (118, "What is the dropout percentage for new students?", "compare_dimensions"),
    (119, "Which has higher dropout, existing or new?", "compare_dimensions"),
    (120, "Compare existing and new dropout counts.", "compare_dimensions"),
    (121, "Show existing vs new dropout by RI.", "compare_dimensions"),
    (122, "Show existing vs new dropout by zone.", "compare_dimensions"),
    (123, "Compare existing and new strength.", "compare_dimensions"),
    (124, "Which category has more current-year strength, existing or new?", "compare_dimensions"),
    (125, "Show existing vs new dropout percentage for PP.", "compare_dimensions"),
    (126, "Show existing vs new dropout percentage for PS.", "compare_dimensions"),
    (127, "Show existing vs new dropout percentage for HS.", "compare_dimensions"),
    (128, "Compare existing and new students in HS.", "compare_dimensions"),
    (129, "Compare existing and new students in PS.", "compare_dimensions"),
    (130, "Compare existing and new students in PP.", "compare_dimensions"),

    # 8. Rooms / Occupancy / Vacancy
    (131, "Which branches have the most occupied rooms?", "rank_branches_by_metric"),
    (132, "Which branches have the most empty rooms?", "rank_branches_by_metric"),
    (133, "Show total occupied rooms by RI.", "group_metric_aggregate"),
    (134, "Show total empty rooms by RI.", "group_metric_aggregate"),
    (135, "Show occupied rooms by zone.", "group_metric_aggregate"),
    (136, "Show empty rooms by zone.", "group_metric_aggregate"),
    (137, "What is the room occupancy percentage by branch?", "calculate_room_ratio"),
    (138, "Which branches have the highest room occupancy?", "calculate_room_ratio"),
    (139, "Which branches have the lowest room occupancy?", "calculate_room_ratio"),
    (140, "Which branches have the highest vacancy percentage?", "calculate_room_ratio"),
    (141, "Show branches with more than 20% vacant rooms.", "filter_by_threshold"),
    (142, "Compare occupied and empty rooms by RI.", "compare_dimensions"),
    (143, "Compare occupied and empty rooms by zone.", "compare_dimensions"),
    (144, "How many rooms are occupied in the current scope?", "scope_total"),
    (145, "How many rooms are vacant in the current scope?", "scope_total"),

    # 9. Staff / STR
    (146, "Which RIs have the highest staff count?", "group_metric_aggregate"),
    (147, "Which branches have the highest student-teacher ratio?", "rank_branches_by_metric"),
    (148, "Compare CY and LY staff count by RI.", "compare_dimensions"),
    (149, "Which branches improved their student-teacher ratio compared with last year?", "year_over_year_change_ranking"),
    (150, "Which branches have the highest staff-to-student performance gap?", "rank_branches_by_metric"),
]


class All150QuestionsTest(SimpleTestCase):
    def setUp(self):
        self.context = {'agm': 'All', 'ri': 'All', 'zone': 'All', 'branches': ['All']}

    def test_all_150_questions_route_and_execute(self):
        errors = []
        for q_num, question, expected_func in ALL_150_QUESTIONS:
            handler = route_question(question)
            if handler is None:
                errors.append(f"Q{q_num}: '{question}' returned None (expected '{expected_func}')")
                continue

            try:
                result = handler(self.context)
                actual_func = result.get('function')
                if actual_func != expected_func:
                    errors.append(
                        f"Q{q_num}: '{question}' dispatched to '{actual_func}', expected '{expected_func}'"
                    )
                if not result.get('answer'):
                    errors.append(f"Q{q_num}: '{question}' returned empty answer")
            except Exception as exc:
                errors.append(f"Q{q_num}: '{question}' raised exception: {exc}")

        if errors:
            self.fail(f"{len(errors)} question(s) failed routing/execution:\n" + "\n".join(errors[:20]))

    def test_domain_1_mandatory_three_column_format(self):
        table_funcs = {
            "top_5_dropout_branches",
            "rank_branches_by_metric",
            "group_metric_aggregate",
            "year_over_year_change_ranking",
            "compare_dimensions",
        }
        for q_num, question, expected_func in ALL_150_QUESTIONS:
            if expected_func in table_funcs:
                handler = route_question(question)
                result = handler(self.context)
                ans = result.get('answer', '')
                if '| Current Year |' in ans:
                    self.assertTrue('| Change |' in ans or '| Difference |' in ans, f"Q{q_num} ('{question}') markdown table missing '| Change |' column")
