from django.test import TestCase
from query_engine.analytics import select_dropout_entities
from query_engine.formatting import format_ranked_branches
from query_engine.router import route_question


class IndividualHierarchyQueriesTests(TestCase):
    # Test 1: RI -> Branch -> no Top-N -> some CY > 10%
    def test_validation_1_ri_anitha_qualifying_branches_above_10_percent(self):
        handler = route_question('RI Anitha which branches have highest dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'rank_branches_by_metric')
        self.assertEqual(len(res['data']), 7, 'Must return strictly the 7 branches with CY > 10.0%')
        branches = [item['branch'] for item in res['data']]
        expected_branches = [
            'MIYAPUR FUTURE PATHWAYS',
            'TOLICHOWKI 1',
            'Manikonda',
            'Sun City',
            'ATTAPUR',
            'GACHIBOWLI',
            'Shamshabad',
        ]
        self.assertEqual(branches, expected_branches)
        self.assertEqual(res['data'][0]['current_year'], 14.40)
        self.assertEqual(res['data'][-1]['current_year'], 10.05)
        self.assertNotIn('NALLAGANDLA', branches)
        self.assertNotIn('JUBILEE HILLS', branches)
        self.assertIn('| Rank | Branch | Current Year | Last Year | Change | Status |', res['answer'])

    # Test 2: RI -> Branch -> no Top-N -> none CY > 10% (Fallback rule)
    def test_validation_2_fallback_when_no_entities_above_10_percent(self):
        sample = [
            {'branch': 'Branch A', 'current_year': 9.20, 'previous_year': 8.50},
            {'branch': 'Branch B', 'current_year': 7.10, 'previous_year': 7.00},
            {'branch': 'Branch C', 'current_year': 5.40, 'previous_year': 6.00},
        ]
        selected, is_fallback = select_dropout_entities(sample, threshold=10.0)
        self.assertTrue(is_fallback)
        self.assertEqual(len(selected), 3, 'Rule 3 fallback must return all entities when none > 10%')
        ans = format_ranked_branches(selected, 'CY-DPP', ascending=False, context={'ri': 'SampleRI'}, is_fallback=is_fallback)
        self.assertIn('No branches under RI SampleRI are above the 10% dropout threshold', ans)
        self.assertIn('Showing all branches for completeness', ans)

    # Test 3: AGM -> RI -> some CY > 10%
    def test_validation_3_agm_scoped_ris_highest_dropout_percentage(self):
        handler = route_question('AGM Shiva Rama Krishna which RIs have highest dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'group_metric_aggregate')
        self.assertEqual(len(res['data']), 2, 'Only RIs with CY > 10% qualify')
        self.assertEqual(res['data'][0]['group'], 'Y.Anitha')
        self.assertEqual(res['data'][0]['current_year'], 11.79)
        self.assertEqual(res['data'][0]['previous_year'], 11.93)
        self.assertEqual(res['data'][1]['group'], 'M.Hari Krishna')
        self.assertEqual(res['data'][1]['current_year'], 10.78)
        self.assertNotIn('Padmaja', [item['group'] for item in res['data']])

    # Test 4: AGM -> RI -> none CY > 10% (Fallback rule)
    def test_validation_4_agm_fallback_when_none_above_10_percent(self):
        sample = [
            {'group': 'RI Alpha', 'current_year': 8.2, 'previous_year': 7.5},
            {'group': 'RI Beta', 'current_year': 6.1, 'previous_year': 5.8},
        ]
        selected, is_fallback = select_dropout_entities(sample, threshold=10.0)
        self.assertTrue(is_fallback)
        self.assertEqual(len(selected), 2)

    # Test 5: Explicit Top 5
    def test_validation_5_explicit_top_5_with_threshold(self):
        handler = route_question('RI Anitha which 5 branches have highest dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(len(res['data']), 5)
        self.assertEqual(res['data'][0]['branch'], 'MIYAPUR FUTURE PATHWAYS')
        self.assertEqual(res['data'][4]['branch'], 'ATTAPUR')

    # Test 6: Explicit Top 10
    def test_validation_6_explicit_top_10(self):
        handler = route_question('Show the top 10 branches with the highest dropout percentage.')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(len(res['data']), 10)

    # Test 7: Specific Branch (No multi-entity threshold filtering)
    def test_validation_7_specific_branch_lookup(self):
        handler = route_question('Branch Miyapur what is the dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'branch_metric_lookup')
        self.assertIn('14.40%', res['answer'])

    # Test 8: CY > 10, LY <= 10 (Included)
    def test_validation_8_cy_above_10_ly_below_10(self):
        sample = [
            {'branch': 'B1', 'current_year': 14.0, 'previous_year': 8.0},
            {'branch': 'B2', 'current_year': 9.0, 'previous_year': 8.0},
        ]
        selected, is_fallback = select_dropout_entities(sample, threshold=10.0)
        self.assertFalse(is_fallback)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['branch'], 'B1')

    # Test 9: CY > 10, LY > 10 (Included and historical status preserved)
    def test_validation_9_cy_above_10_ly_above_10(self):
        sample = [
            {'branch': 'B1', 'current_year': 14.0, 'previous_year': 24.0, 'difference': -10.0},
        ]
        selected, is_fallback = select_dropout_entities(sample, threshold=10.0)
        self.assertFalse(is_fallback)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['branch'], 'B1')
        self.assertEqual(selected[0]['previous_year'], 24.0)

    # Test 10: CY <= 10, LY > 10 (Do NOT qualify under threshold rules)
    def test_validation_10_cy_below_10_ly_above_10(self):
        sample = [
            {'branch': 'Qualifying Branch', 'current_year': 12.0, 'previous_year': 8.0},
            {'branch': 'Non-Qualifying Branch', 'current_year': 9.0, 'previous_year': 24.0},
        ]
        selected, is_fallback = select_dropout_entities(sample, threshold=10.0)
        self.assertFalse(is_fallback)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['branch'], 'Qualifying Branch')

    # Test 11: CY == 10% (Strictly > 10% rule)
    def test_validation_11_strict_above_10_rule(self):
        sample = [
            {'branch': 'Strictly Above', 'current_year': 10.01, 'previous_year': 9.0},
            {'branch': 'Exactly Ten', 'current_year': 10.00, 'previous_year': 9.0},
            {'branch': 'Below Ten', 'current_year': 9.99, 'previous_year': 9.0},
        ]
        selected, is_fallback = select_dropout_entities(sample, threshold=10.0)
        self.assertFalse(is_fallback)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['branch'], 'Strictly Above')

    # Test 12: No Top-N specified (Never automatically truncate to Top 5)
    def test_validation_12_no_top_n_never_truncates_to_top_5(self):
        handler = route_question('RI Anitha which branches have highest dropout percentage')
        res = handler({})
        self.assertEqual(len(res['data']), 7)
        self.assertNotEqual(len(res['data']), 5)

    # Additional Hierarchy & Domain Tests
    def test_ri_anitha_unbounded_branches_highest_dropouts_count(self):
        handler = route_question('RI Anitha which branches have highest dropouts')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'rank_branches_by_metric')
        self.assertEqual(len(res['data']), 12)
        self.assertEqual(res['data'][0]['branch'], 'Sun City')
        self.assertEqual(res['data'][0]['current_year'], 175.0)

    def test_branch_hierarchy_lookup(self):
        handler = route_question('Branch Miyapur which RI does it belong to')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'branch_hierarchy_lookup')
        self.assertEqual(len(res['data']), 1)
        self.assertEqual(res['data'][0]['branch'], 'MIYAPUR FUTURE PATHWAYS')
        self.assertEqual(res['data'][0]['ri'], 'Y.Anitha')
        self.assertEqual(res['data'][0]['agm'], 'P.Shiva Rama Krishna')
        self.assertEqual(res['data'][0]['zone'], 'Kukatpally')
        self.assertIn('belongs to **RI Y.Anitha**', res['answer'])

    def test_ri_anitha_weighted_dropout_percentage(self):
        handler = route_question('RI anitha dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertIn('11.79%', res['answer'])
        self.assertNotIn('115.46%', res['answer'])

    # -------------------------------------------------------------------
    # Audit Validation Queries: Explicit CY/LY Disambiguation & Formatting
    # -------------------------------------------------------------------
    def test_audit_1_kompally_2_current_year(self):
        handler = route_question('Kompally 2 current year dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'branch_metric_lookup')
        self.assertIn('Current Year Dropout Percentage', res['answer'])
        self.assertIn('9.88%', res['answer'])
        self.assertNotIn('LY-DPP', res['answer'])

    def test_audit_2_kompally_2_last_year(self):
        handler = route_question('Kompally 2 last year dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'branch_metric_lookup')
        self.assertIn('Last Year Dropout Percentage', res['answer'])
        self.assertIn('9.60%', res['answer'])

    def test_audit_3_kompally_2_unspecified_defaults_to_current_year(self):
        handler = route_question('Kompally 2 dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'branch_metric_lookup')
        self.assertIn('Current Year Dropout Percentage', res['answer'])
        self.assertIn('9.88%', res['answer'])

    def test_audit_4_sun_city_current_year(self):
        handler = route_question('Sun City current year dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'branch_metric_lookup')
        self.assertIn('Current Year Dropout Percentage', res['answer'])
        self.assertIn('10.88%', res['answer'])

    def test_audit_5_sun_city_last_year(self):
        handler = route_question('Sun City last year dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'branch_metric_lookup')
        self.assertIn('Last Year Dropout Percentage', res['answer'])
        self.assertIn('5.99%', res['answer'])

    def test_audit_6_ri_padmaja_dropout_percentage_table_format(self):
        handler = route_question('RI Padmaja dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'group_metric_aggregate')
        self.assertIn('| RI | Current Year | Last Year | Difference | Status |', res['answer'])
        self.assertIn('Padmaja', res['answer'])
        self.assertIn('9.59%', res['answer'])
        self.assertIn('8.35%', res['answer'])
        self.assertNotIn('RiCurrent YearLast YearDifferenceStatus', res['answer'])

    def test_audit_7_ri_padmaja_current_year_only(self):
        handler = route_question('RI Padmaja current year dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'group_metric_aggregate')
        self.assertIn('Current Year Dropout Percentage: 9.59%', res['answer'])
        self.assertNotIn('Last Year', res['answer'])
        self.assertNotIn('Difference', res['answer'])

    def test_audit_8_ri_padmaja_last_year_only(self):
        handler = route_question('RI Padmaja last year dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'group_metric_aggregate')
        self.assertIn('Last Year Dropout Percentage: 8.35%', res['answer'])
        self.assertNotIn('Current Year', res['answer'])
        self.assertNotIn('Difference', res['answer'])

    def test_audit_9_ri_anitha_highest_dropout_percentage_branches(self):
        handler = route_question('RI Anitha which branches have highest dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(res['function'], 'rank_branches_by_metric')
        self.assertEqual(len(res['data']), 7)
        self.assertEqual(res['data'][0]['branch'], 'MIYAPUR FUTURE PATHWAYS')
        self.assertEqual(res['data'][0]['current_year'], 14.40)
        self.assertIn('| Rank | Branch | Current Year | Last Year | Change | Status |', res['answer'])

    def test_audit_10_ri_anitha_top_5_branches(self):
        handler = route_question('RI Anitha top 5 branches by dropout percentage')
        self.assertIsNotNone(handler)
        res = handler({})
        self.assertEqual(len(res['data']), 5)
        self.assertEqual(res['data'][0]['branch'], 'MIYAPUR FUTURE PATHWAYS')
        self.assertEqual(res['data'][4]['branch'], 'ATTAPUR')
