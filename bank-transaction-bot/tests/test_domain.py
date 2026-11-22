import copy
import unittest
from app.service import InvestigationService
from app.domain import evaluate_limit


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.service = InvestigationService()

    def test_recorded_card_limit_is_confirmed(self):
        r = self.service.diagnose('online-card')
        f = r['findings'][0]
        self.assertEqual((f['certainty'], f['control_level']), ('CONFIRMED', 'CARD'))
        self.assertEqual(f['reason_category'], 'VELOCITY_LIMITS')
        self.assertEqual(f['remaining'], '300.00')
        self.assertIn('模拟', r['customer_response'])

    def test_four_levels_and_seven_categories_are_demonstrated(self):
        results = [self.service.diagnose(s['id']) for s in self.service.list_scenarios()]
        findings = [f for r in results for f in r['findings']]
        self.assertEqual({f['control_level'] for f in findings if f.get('control_level')}, {'ENTITY', 'CARD', 'ACCOUNT', 'PRODUCT'})
        self.assertEqual({f['reason_category'] for f in findings if f.get('reason_category')}, set(self.service.ontology['reason_categories']))

    def test_six_limit_types(self):
        self.assertEqual(len(self.service.ontology['limit_types']), 6)
        types = {f.get('limit_type') for s in self.service.list_scenarios() for f in self.service.diagnose(s['id'])['findings']}
        self.assertTrue(set(self.service.ontology['limit_types']) <= types)

    def test_current_state_does_not_confirm_past_decline(self):
        r = self.service.diagnose('history-missing')
        self.assertEqual(r['findings'][0]['certainty'], 'INFERRED')
        self.assertIn('无法确认', r['customer_response'])

    def test_historical_and_current_are_separate(self):
        past = self.service.diagnose('unlocked-now')
        now = self.service.diagnose('unlocked-now', 'CONTROL')
        self.assertEqual(past['findings'][0]['certainty'], 'CONFIRMED')
        self.assertIn('已解除', now['customer_response'])

    def test_conflict_is_preserved(self):
        self.assertEqual(self.service.diagnose('conflict')['findings'][0]['certainty'], 'CONFLICTED')

    def test_skipped_is_not_pass(self):
        r = self.service.diagnose('skipped')
        self.assertEqual(r['findings'][0]['certainty'], 'UNKNOWN')
        self.assertIn('未执行', r['customer_response'])

    def test_risk_data_never_enters_public_contract(self):
        import json
        r = self.service.diagnose('entity-risk')
        text = json.dumps(r)
        for secret in ('risk_score', 'internal_threshold', 'secret-rule-88'):
            self.assertNotIn(secret, text)
        self.assertEqual(r['findings'][0]['control_level'], 'ENTITY')
        self.assertFalse(r['next_actions'][0]['requires_confirmation'])

    def test_multiple_causes_preserve_recorded_primary(self):
        r = self.service.diagnose('multiple')
        self.assertEqual(len(r['findings']), 2)
        self.assertEqual(r['findings'][0]['causal_role'], 'RECORDED_PRIMARY_CAUSE')
        self.assertEqual(r['findings'][1]['causal_role'], 'POTENTIAL_BLOCKER')

    def test_network_failure_not_issuer_decline(self):
        r = self.service.diagnose('network')
        self.assertEqual(r['findings'][0]['reason_category'], None)
        self.assertIn('不能认定', r['customer_response'])

    def test_unknown_id(self):
        with self.assertRaises(KeyError):
            self.service.diagnose('not-found')

    def test_ontology_drives_action_inheritance(self):
        r = self.service.diagnose('online-card')
        self.assertIn('VIEW_LIMIT', [a['id'] for a in r['next_actions']])
        self.assertTrue(self.service.graph.is_a('DailyOnlinePurchaseLimit', 'LimitControl'))


class LimitTests(unittest.TestCase):
    def test_decimal_precision_and_equal_boundary(self):
        r = evaluate_limit('0.30', '0.10', '0.20', 'DAILY')
        self.assertFalse(r['exceeded'])
        self.assertEqual(r['remaining'], '0.20')

    def test_single_limit_is_not_remaining_daily_allowance(self):
        r = evaluate_limit('100.00', None, '101.00', 'SINGLE')
        self.assertTrue(r['exceeded'])
        self.assertIsNone(r['remaining'])

    def test_missing_usage_is_unknown(self):
        self.assertIsNone(evaluate_limit('100', None, '50', 'DAILY')['exceeded'])

    def test_invalid_amounts_rejected(self):
        for amount in ('NaN', 'Infinity', '-1', 'abc'):
            with self.assertRaises(ValueError):
                evaluate_limit('100', '0', amount, 'DAILY')

    def test_negative_remaining_not_clamped(self):
        self.assertEqual(evaluate_limit('100', '110', '1', 'DAILY')['remaining'], '-10')

class CurrentLimitTests(unittest.TestCase):
    def test_current_allowance_uses_current_snapshot(self):
        r = InvestigationService().diagnose('online-card', 'LIMIT')
        self.assertEqual(r['findings'][0]['remaining'], '150.00')
        self.assertIn('当前', r['customer_response'])
        self.assertNotIn('剩余 300.00', r['customer_response'])

    def test_no_current_snapshot_is_unknown(self):
        r = InvestigationService().diagnose('missing-usage', 'LIMIT')
        self.assertEqual(r['findings'][0]['certainty'], 'UNKNOWN')
        self.assertNotIn('remaining', r['findings'][0])

class EvidenceBoundaryTests(unittest.TestCase):
    def record(self, sid='online-card'):
        service = InvestigationService()
        record = next(r for r in service.adapter.records if r['id']==sid)
        return service, record

    def test_pass_is_not_a_candidate_cause(self):
        service, record = self.record('card-locked')
        record['controls'][0]['evaluation'] = 'PASS'
        r = service.diagnose('card-locked')
        self.assertEqual(r['findings'][0]['causal_role'], 'RULED_OUT')
        self.assertIn('通过', r['customer_response'])

    def test_error_is_unknown(self):
        service, record = self.record('card-locked')
        record['controls'][0]['evaluation'] = 'ERROR'
        self.assertEqual(service.diagnose('card-locked')['findings'][0]['certainty'], 'UNKNOWN')

    def test_current_configuration_not_described_as_historical_allowance(self):
        service, record = self.record()
        record['historical_snapshot'] = False
        record['controls'][0]['evaluation'] = 'UNKNOWN'
        r = service.diagnose('online-card')
        self.assertNotIn('交易当时：有效日限额', r['customer_response'])
        self.assertNotIn('remaining', r['findings'][0])

    def test_currency_conflict_prevents_calculation(self):
        service, record = self.record()
        record['controls'][0]['limit']['currency'] = 'USD'
        r = service.diagnose('online-card')
        self.assertIsNone(r['findings'][0]['remaining'])
        self.assertEqual(r['findings'][0]['certainty'], 'UNKNOWN')

class CurrentEvaluationTests(unittest.TestCase):
    def test_current_view_does_not_reuse_historical_fail(self):
        result = InvestigationService().diagnose('online-card', 'LIMIT')
        self.assertEqual(result['findings'][0]['evaluation_result'], 'NOT_EVALUATED')

class RiskCurrentViewTests(unittest.TestCase):
    def test_risk_current_state_uses_generic_current_wording(self):
        service = InvestigationService()
        record = next(r for r in service.adapter.records if r['id']=='entity-risk')
        for active, expected in ((True,'当前仍存在'),(False,'当前未显示')):
            record['controls'][0]['current_active'] = active
            result = service.diagnose('entity-risk', 'CONTROL')
            self.assertIn(expected, result['customer_response'])
            self.assertNotIn('risk_score', str(result))
