import copy
import unittest
from app.configuration import ConfigBundle
from app.mapping import BankMapper, MappingError
from app.rules import RuleEngine
from app.service import InvestigationService
from app.adapters import ROOT, load_json


class MappingTests(unittest.TestCase):
    def test_legacy_fields_codes_and_level_are_mapped(self):
        mapper = BankMapper(ConfigBundle().read('mappings/legacy-demo.json'))
        raw = ConfigBundle().read('config/raw-bank-example.json')
        facts = mapper.normalize(raw)
        self.assertEqual(facts['controls'][0]['type'], 'DailyOnlinePurchaseLimit')
        self.assertEqual(facts['controls'][0]['level'], 'CARD')
        self.assertEqual(facts['controls'][0]['evaluation'], 'FAIL')
        self.assertEqual(facts['amount'], '500.00')
        self.assertNotIn('raw_secret', str(facts))

    def test_mapping_change_changes_result_without_code_change(self):
        bundle = ConfigBundle()
        profile = bundle.read('mappings/legacy-demo.json')
        profile['enums']['levels']['C'] = 'ACCOUNT'
        facts = BankMapper(profile).normalize(bundle.read('config/raw-bank-example.json'))
        self.assertEqual(facts['controls'][0]['level'], 'ACCOUNT')

    def test_unknown_enum_is_not_guessed(self):
        bundle = ConfigBundle()
        raw = bundle.read('config/raw-bank-example.json')
        raw['checks'][0]['layerCode'] = 'UNREGISTERED'
        with self.assertRaises(MappingError):
            BankMapper(bundle.read('mappings/legacy-demo.json')).normalize(raw)

    def test_missing_current_state_is_unknown_not_confirmed(self):
        service = InvestigationService()
        record = next(r for r in service.adapter.records if r['id']=='card-locked')
        del record['controls'][0]['current_active']
        self.assertEqual(service.diagnose('card-locked','CONTROL')['findings'][0]['certainty'],'UNKNOWN')


class LayerTests(unittest.TestCase):
    def test_ontology_has_no_customer_instructions(self):
        o = ConfigBundle().ontology
        for action in o['actions']:
            self.assertNotIn('instruction',action)
            self.assertNotIn('label',action)

    def test_template_change_changes_only_presentation(self):
        bundle = ConfigBundle()
        baseline = InvestigationService(bundle=bundle).diagnose('online-card')
        bundle.templates['messages']['limit_daily_exceeded'] = '测试新话术：{limit_label}'
        changed = InvestigationService(bundle=bundle).diagnose('online-card')
        self.assertIn('测试新话术',changed['customer_response'])
        self.assertEqual(changed['findings'][0]['remaining'],baseline['findings'][0]['remaining'])
        self.assertEqual(changed['findings'][0]['certainty'],baseline['findings'][0]['certainty'])

    def test_rule_configuration_changes_diagnosis(self):
        bundle = ConfigBundle()
        rule = next(r for r in bundle.rules['tables']['base'] if r['id']=='historical-fail')
        rule['set']['certainty'] = 'UNKNOWN'
        r = InvestigationService(bundle=bundle).diagnose('card-locked')
        self.assertEqual(r['findings'][0]['certainty'],'UNKNOWN')
        self.assertEqual(r['findings'][0]['diagnostic_rule_id'],'historical-fail')

    def test_missing_template_reference_is_rejected(self):
        bundle = ConfigBundle()
        del bundle.templates['messages']['limit_daily_exceeded']
        with self.assertRaises(ValueError): bundle.validate()

    def test_unknown_fact_or_operator_is_rejected(self):
        bundle = ConfigBundle()
        for condition in ({'fact':'typo_fact','eq':True},{'fact':'current','execute':'bad'}):
            bad = copy.deepcopy(bundle.rules)
            bad['tables']['base'][0]['when'] = condition
            with self.assertRaises(ValueError): RuleEngine(bad)

    def test_missing_fact_at_runtime_fails_explicitly(self):
        engine = RuleEngine(ConfigBundle().rules)
        with self.assertRaises(ValueError): engine.evaluate('base',{})

    def test_disclosure_config_is_separate_from_templates(self):
        bundle=ConfigBundle()
        self.assertNotIn('generic_risk_summary',bundle.policy)
        bundle.templates['messages']['risk_current_active']='当前仍存在受限能力，请通过审核渠道办理。'
        r=InvestigationService(bundle=bundle).diagnose('entity-risk','CONTROL')
        self.assertIn('审核渠道',r['customer_response'])
        self.assertNotIn('risk_score',str(r))

    def test_response_contains_each_layer_version(self):
        r=InvestigationService().diagnose('online-card')
        self.assertEqual(set(r['configuration_versions']),{'ontology','mapping','rules','policy','templates'})

class ResponseCodeTests(unittest.TestCase):
    def test_response_code_is_a_versioned_hint_not_root_cause(self):
        from app.adapters import MockBankAdapter
        bundle = ConfigBundle()
        raw = bundle.read('config/raw-bank-example.json')
        raw['checks'] = []
        adapter = MockBankAdapter(records=[raw],mapping=bundle.read('mappings/legacy-demo.json'),bundle=bundle)
        normalized = adapter.get_attempt(raw['attemptId'],raw['subjectId'])
        self.assertEqual(normalized['response_hint']['kind'],'LIMIT_RELATED')
        self.assertEqual(normalized['response_hint']['authority'],'HINT_ONLY')
        result = InvestigationService(adapter=adapter,bundle=bundle).diagnose(raw['attemptId'])
        self.assertEqual(result['findings'][0]['certainty'],'UNKNOWN')
        self.assertIsNone(result['findings'][0]['reason_category'])

    def test_unknown_network_version_does_not_reuse_mapping(self):
        bundle = ConfigBundle()
        raw = bundle.read('config/raw-bank-example.json')
        raw['response_version'] = 'not-registered'
        normalized = BankMapper(bundle.read('mappings/legacy-demo.json')).normalize(raw)
        self.assertEqual(normalized['response_hint']['status'],'UNMAPPED')
        self.assertNotIn('kind',normalized['response_hint'])


class ConfigurationBoundaryTests(unittest.TestCase):
    def test_inappropriate_template_placeholder_rejected_at_startup(self):
        bundle=ConfigBundle()
        bundle.templates['messages']['recorded']='原因：{remaining}'
        with self.assertRaises(ValueError):bundle.validate()

    def test_conflicted_current_limit_keeps_conflict_explanation(self):
        service=InvestigationService()
        record=next(s for s in service.adapter.records if s['id']=='online-card')
        record['controls'][0]['conflict']=True
        f=service.diagnose('online-card','LIMIT')['findings'][0]
        self.assertEqual(f['certainty'],'CONFLICTED')
        self.assertIn('冲突',f['safe_summary'])

    def test_silent_policy_hides_reason_and_control_metadata(self):
        bundle=ConfigBundle()
        bundle.policy['categories']['RISK_CONTROLS']='SILENT'
        result=InvestigationService(bundle=bundle).diagnose('entity-risk')
        f=result['findings'][0]
        self.assertIsNone(f['reason_category'])
        self.assertIsNone(f['control_level'])
        self.assertNotIn('control_ref',f)
        self.assertEqual(f['evidence_refs'],[])
        self.assertNotIn('安全限制',f['safe_summary'])

class ReviewRegressionTests(unittest.TestCase):
    def test_risk_pass_stays_ruled_out_after_disclosure(self):
        service=InvestigationService()
        record=next(s for s in service.adapter.records if s['id']=='entity-risk')
        record['controls'][0]['evaluation']='PASS'
        f=service.diagnose('entity-risk')['findings'][0]
        self.assertEqual(f['causal_role'],'RULED_OUT')
        self.assertIn('排除',f['safe_summary'])
        self.assertNotIn('受到安全限制',f['safe_summary'])

    def test_invalid_normalized_enum_rejected_at_startup_and_mapper(self):
        for domain,source,bad in [('evaluations','FAIL','FIAL'),('origins','ISSUER','ISSUER_TYPO'),
                                  ('decisions','DECLINED','DECLINE_TYPO'),('periods','DAILY','DAILY_TYPO')]:
            with self.subTest(domain=domain):
                bundle=ConfigBundle()
                bundle.mapping['enums'][domain][source]=bad
                with self.assertRaises(ValueError):bundle.validate()
                with self.assertRaises(MappingError):BankMapper(bundle.mapping)
