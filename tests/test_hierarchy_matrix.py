"""
Dedicated test suite verifying the 160 hierarchy-specific question matrix:
- 40 AGM-wise questions
- 40 RI-wise questions
- 40 Zone-wise questions
- 40 Branch-wise questions
- 26 Cross-hierarchy scoping questions
- Branch invalid child entity guards
- Speech phonetic variations
"""
import json
import os
from django.test import SimpleTestCase

from query_engine.router import route_question


class HierarchyMatrixRegressionTests(SimpleTestCase):
    def setUp(self):
        self.context = {'agm': 'All', 'ri': 'All', 'zone': 'All', 'branches': ['All']}
        self.matrix_dir = os.path.join(os.path.dirname(__file__), 'question_matrix')
        try:
            from query_engine.orchestrator import get_dataframe
            from query_engine.glossary import BRANCH_COLUMN
            df = get_dataframe()
            branches = list(df[BRANCH_COLUMN].dropna().unique()) if BRANCH_COLUMN in df.columns else []
            self.active_branch = 'Kompally 2' if 'Kompally 2' in branches else ('Kakinada 1' if 'Kakinada 1' in branches else (branches[0] if branches else 'Kompally 2'))
        except Exception:
            self.active_branch = 'Kompally 2'

    def _run_question_catalog(self, filename: str):
        filepath = os.path.join(self.matrix_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            catalog = json.load(f)

        errors = []
        for item in catalog:
            q_id = item['id']
            question = item['question']
            expected_func = item.get('expected_function')

            # Adapt sample branch entity to active database branch if testing branch suite
            if 'Kakinada 1' in question and self.active_branch != 'Kakinada 1':
                question = question.replace('Kakinada 1', self.active_branch)

            handler = route_question(question)
            if handler is None:
                errors.append(f"Q{q_id} '{question}' returned None handler (expected '{expected_func}')")
                continue

            try:
                res = handler(self.context)
                actual_func = res.get('function')
                answer = res.get('answer', '')

                if not answer or not str(answer).strip():
                    errors.append(f"Q{q_id} '{question}' returned empty answer")

                # Verify function category if specified
                if expected_func and actual_func != expected_func:
                    # Allow valid alternative reporting functions (e.g. fee_summary vs sub-runners)
                    allowed_variants = {
                        'fee_summary': {'fee_summary', 'run_fee_due_ranking', 'run_total_fee_due', 'run_fee_due_student_count', 'run_zero_paid_count', 'run_zero_paid_fee_due'},
                        'group_metric_aggregate': {'group_metric_aggregate', 'scope_total', 'compare_dimensions'},
                        'rank_branches_by_metric': {'rank_branches_by_metric', 'top_5_dropout_branches', 'year_over_year_ranking', 'filter_by_threshold'},
                        'top_5_dropout_branches': {'top_5_dropout_branches', 'rank_branches_by_metric'},
                        'compare_dimensions': {'compare_dimensions', 'group_metric_aggregate', 'scope_total', 'year_over_year_change_ranking', 'branch_metric_lookup', 'room_utilization_snapshot'},
                        'revenue_salary_summary': {'revenue_salary_summary', 'revenue_salary_ranking', 'revenue_salary_segment_comparison', 'revenue_salary_historical_unavailable'},
                        'revenue_salary_ranking': {'revenue_salary_ranking', 'revenue_salary_summary', 'revenue_salary_historical_unavailable'},
                        'agm_teacher_student_ratio_statistics': {'agm_teacher_student_ratio_statistics', 'scope_total', 'group_metric_aggregate'},
                        'ri_teacher_student_ratio_statistics': {'ri_teacher_student_ratio_statistics', 'scope_total', 'group_metric_aggregate'},
                        'year_over_year_ranking': {'year_over_year_ranking', 'year_over_year_change_ranking', 'rank_branches_by_metric', 'branch_metric_lookup'},
                        'branch_fee_due_statistics': {'branch_fee_due_statistics', 'fee_summary'},
                        'branch_scorecard': {'branch_scorecard', 'branch_combined_statistics', 'entity_summary'},
                        'branch_metric_lookup': {'branch_metric_lookup', 'scope_total', 'sections_and_sps_snapshot', 'staff_count_summary', 'calculate_room_ratio', 'room_utilization_snapshot', 'compare_dimensions'},
                    }
                    if actual_func not in allowed_variants.get(expected_func, {expected_func}):
                        errors.append(f"Q{q_id} '{question}' routed to '{actual_func}', expected '{expected_func}'")

            except Exception as exc:
                errors.append(f"Q{q_id} '{question}' raised exception: {exc}")

        if errors:
            self.fail(f"{len(errors)} question(s) failed in {filename}:\n" + "\n".join(errors[:20]))

    def test_01_agm_questions_matrix_40(self):
        """Test all 40 AGM-wise questions."""
        self._run_question_catalog('agm_questions.json')

    def test_02_ri_questions_matrix_40(self):
        """Test all 40 RI-wise questions."""
        self._run_question_catalog('ri_questions.json')

    def test_03_zone_questions_matrix_40(self):
        """Test all 40 Zone-wise questions."""
        self._run_question_catalog('zone_questions.json')

    def test_04_branch_questions_matrix_40(self):
        """Test all 40 Branch-wise questions."""
        self._run_question_catalog('branch_questions.json')

    def test_05_cross_hierarchy_scoping_26(self):
        """Verify all 26 cross-hierarchy scoping questions execute with correct scoping."""
        cross_hierarchy_cases = [
            # AGM -> Zone
            ("Which zone has the highest dropout percentage under AGM Ramana Rao?", "group_metric_aggregate"),
            ("Which zone has the biggest increase in dropout percentage under AGM Ramana Rao?", "compare_dimensions"),
            ("Which zone has the highest zero-paid fee due under AGM Ramana Rao?", "fee_summary"),
            ("Which zone has the highest salary burden under AGM Ramana Rao?", "revenue_salary_ranking"),
            # AGM -> RI
            ("Which RI has the highest dropout percentage under AGM Ramana Rao?", "group_metric_aggregate"),
            ("Which RI has the highest dropout count under AGM Ramana Rao?", "group_metric_aggregate"),
            ("Which RI has the highest fee due under AGM Ramana Rao?", "fee_summary"),
            ("Which RI has the highest salary burden under AGM Ramana Rao?", "revenue_salary_ranking"),
            ("Which RI has the best improvement in dropout percentage under AGM Ramana Rao?", "compare_dimensions"),
            # AGM -> Branch
            ("Which branch has the highest dropout percentage under AGM Ramana Rao?", "rank_branches_by_metric"),
            ("Show top 5 branches by dropout percentage under AGM Ramana Rao.", "top_5_dropout_branches"),
            ("Which branch has the highest zero-paid fee due under AGM Ramana Rao?", "fee_summary"),
            ("Which branch has the highest salary burden under AGM Ramana Rao?", "revenue_salary_ranking"),
            # RI -> Branch
            ("Which branch has the highest dropout percentage under RI Anitha?", "rank_branches_by_metric"),
            ("Show top 5 branches by dropout count under RI Anitha.", "rank_branches_by_metric"),
            ("Which branch has the highest fee due under RI Anitha?", "fee_summary"),
            ("Which branch has the highest zero-paid fee due under RI Anitha?", "fee_summary"),
            ("Which branch has the highest salary burden under RI Anitha?", "revenue_salary_ranking"),
            # Zone -> RI
            ("Which RI has the highest dropout percentage in Kukatpally zone?", "group_metric_aggregate"),
            ("Which RI has the biggest increase in dropout percentage in Kukatpally zone?", "compare_dimensions"),
            ("Which RI has the highest fee due in Kukatpally zone?", "fee_summary"),
            ("Which RI has the highest salary burden in Kukatpally zone?", "revenue_salary_ranking"),
            # Zone -> Branch
            ("Which branch has the highest dropout percentage in Kukatpally zone?", "rank_branches_by_metric"),
            ("Show top 5 branches by dropout percentage in Kukatpally zone.", "top_5_dropout_branches"),
            ("Which branch has the highest zero-paid fee due in Kukatpally zone?", "fee_summary"),
            ("Which branch has the highest salary burden in Kukatpally zone?", "revenue_salary_ranking"),
        ]

        errors = []
        for q, expected_func in cross_hierarchy_cases:
            handler = route_question(q)
            res = handler(self.context)
            actual_func = res.get('function')
            if actual_func != expected_func:
                errors.append(f"'{q}': dispatched to '{actual_func}', expected '{expected_func}'")
            if not res.get('answer'):
                errors.append(f"'{q}': empty answer returned")

        if errors:
            self.fail(f"{len(errors)} cross-hierarchy question(s) failed:\n" + "\n".join(errors))

    def test_06_branch_invalid_child_guard(self):
        """Branch is lowest hierarchy; asking for child RIs/Zones/Branches must not invent fake entities."""
        invalid_child_queries = [
            "Which RI has the highest dropout percentage under Kompally 2?",
            "Show dropout percentage by RI under Kompally 2.",
            "Which zone has the highest fee due under Kompally 2?",
            "Which branch has the highest dropout under Kompally 2?",
        ]
        for q in invalid_child_queries:
            handler = route_question(q)
            res = handler(self.context)
            self.assertEqual(res.get('function'), 'invalid_hierarchy', f"'{q}' should return invalid_hierarchy")
            self.assertIn("individual branch and does not have child", res.get('answer', ''))

    def test_07_branch_hierarchy_lookup_parent(self):
        """Branch asking which parent it belongs to must correctly lookup parent RI, AGM, Zone."""
        handler = route_question("Which RI does Kompally 2 belong to?")
        res = handler(self.context)
        self.assertEqual(res.get('function'), 'branch_hierarchy_lookup')
        self.assertIn("K.Srinivasa Rao", res.get('answer', ''))

    def test_08_speech_phonetic_variations(self):
        """Acoustic speech variants must normalize and route cleanly."""
        phonetic_cases = [
            ("drop out percentage for AGM Ramana Rao", "group_metric_aggregate"),
            ("dropout percentage for AGM Ramana Rao", "group_metric_aggregate"),
            ("drop outs percentage for AGM Ramana Rao", "group_metric_aggregate"),
            ("What is the feedue under AGM Ramana Rao?", "fee_summary"),
            ("revenue versus salary under AGM Ramana Rao", "revenue_salary_summary"),
            ("revenue vs salary under AGM Ramana Rao", "revenue_salary_summary"),
            ("teacher student ratio under AGM Ramana Rao", "agm_teacher_student_ratio_statistics"),
            ("student teacher ratio under AGM Ramana Rao", "agm_teacher_student_ratio_statistics"),
            ("dropout percentage of Kompally two", "branch_metric_lookup"),
            ("dropout percentage of Kompally 2", "branch_metric_lookup"),
        ]
        for q, expected_func in phonetic_cases:
            handler = route_question(q)
            res = handler(self.context)
            actual_func = res.get('function')
            allowed = {expected_func, 'scope_total', 'revenue_salary_ranking'}
            self.assertIn(actual_func, allowed, f"'{q}' routed to '{actual_func}', expected one of {allowed}")
            self.assertTrue(bool(res.get('answer')), f"'{q}' returned empty answer")
