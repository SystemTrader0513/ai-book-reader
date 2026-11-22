"""Orchestration only: mapping → configured rules → policy → presentation."""
from app.adapters import MockBankAdapter
from app.configuration import ConfigBundle
from app.domain import OntologyGraph
from app.diagnosis import DiagnosisEngine
from app.disclosure import DisclosurePolicy
from app.presentation import Presenter


class InvestigationService:
    def __init__(self, adapter=None, bundle=None):
        self.bundle = bundle or ConfigBundle()
        self.bundle.validate()
        self.ontology = self.bundle.ontology
        self.policy = self.bundle.policy
        self.graph = OntologyGraph(self.ontology)
        self.adapter = adapter or MockBankAdapter(bundle=self.bundle)
        self.engine = DiagnosisEngine(self.bundle,self.graph)
        self.disclosure = DisclosurePolicy(self.policy)
        self.presenter = Presenter(self.bundle)

    def list_scenarios(self):
        return self.adapter.list_attempts(self.bundle.runtime['demo_customer'])

    def diagnose(self, attempt_id, intent='DECLINE'):
        if intent not in ('DECLINE','CONTROL','LIMIT'):
            raise ValueError('Unsupported investigation intent')
        s = self.adapter.get_attempt(attempt_id,self.bundle.runtime['demo_customer'])
        internal, candidates = self.engine.investigate(s,intent)
        findings, action_ids = [], []
        for f in internal:
            permitted, allowed = self.disclosure.apply(f,candidates.get(f.get('control_ref'),[]) if candidates else [])
            findings.append(self.presenter.finding(permitted,s))
            action_ids.extend(a for a in allowed if a not in action_ids)
        if not action_ids:
            action_ids.append(self.policy['fallback_action'])
        actions = [self.presenter.action(a) for a in action_ids]
        return {'intents':[intent],
                'workflow_status':'NEEDS_ESCALATION' if any(f['certainty'] in self.bundle.rules['escalate_certainties'] for f in findings) else 'ANSWERED',
                'transaction_ref':s['id'],
                'transaction':{k:s[k] for k in ('card_label','occurred_at','retrieved_at','amount','currency','channel')},
                'findings':findings,'next_actions':actions,'data_mode':self.adapter.data_mode,
                'ontology_version':self.ontology['version'],'policy_version':self.policy['version'],
                'configuration_versions':self.bundle.versions(s.get('mapping_version')),
                'customer_response':self.presenter.response(findings,actions)}
