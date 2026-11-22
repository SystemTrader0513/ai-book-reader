"""Build typed evidence facts, evaluate configured decisions, retain provenance."""
from app.domain import evaluate_limit
from app.rules import RuleEngine


class DiagnosisEngine:
    def __init__(self, bundle, graph):
        self.bundle = bundle
        self.graph = graph
        self.rules = RuleEngine(bundle.rules)

    def control_finding(self, s, c, current):
        context = {
            'conflict':c['conflict'], 'current':current,
            'current_known':type(c['current_active']) is bool,
            'current_active':c['current_active'], 'evaluation':c['evaluation'],
            'historical_snapshot':s['historical_snapshot'],
            'has_evidence':bool(c['evidence_refs']),
            'effective_at_transaction':c['effective_at_transaction'],
            'recorded_role':'RECORDED_PRIMARY_CAUSE' if c['primary'] else 'RECORDED_SECONDARY_CAUSE'
        }
        rule_id, decision = self.rules.evaluate('base',context)
        finding = {'reason_category':self.graph.category(c['type']),
                   'control_type':c['type'], 'control_level':c['level'],
                   'control_ref':c['id'], 'affected_object_ref':c['target_ref'],
                   'certainty':'UNKNOWN', 'causal_role':'UNDETERMINED',
                   'message_key':'unknown_cause', 'missing_evidence_keys':[],
                   'evidence_refs':c['evidence_refs'], 'source_system':c['source_system'],
                   'evaluation_result':'NOT_EVALUATED' if current else c['evaluation'],
                   'rule_version':c['rule_version'], 'diagnostic_rule_id':rule_id,
                   'observed_at':s['retrieved_at'],
                   'historical_snapshot_available':s['historical_snapshot'],
                   '_current':current, '_current_active':c['current_active']}
        finding.update(decision)
        if self.graph.is_a(c['type'],'LimitControl'):
            self.limit_finding(s,c,context,finding)
        return finding

    def limit_finding(self, s, c, context, f):
        current = context['current']
        lim = c.get('current_limit') if current else (c.get('limit') if s['historical_snapshot'] else None)
        result = {'exceeded':None,'remaining':None}
        if lim is not None:
            if lim['currency']==s['currency']:
                result = evaluate_limit(lim['effective'],lim['used'],s['amount'],lim['period'])
            f.update(limit_type=c['type'],limit_label=self.bundle.ontology['limit_types'].get(c['type'],{}).get('label',self.bundle.ontology['reason_categories'][f['reason_category']]),
                     configured=lim['configured'],effective=lim['effective'],used=lim['used'],
                     remaining=result['remaining'],exceeded=result['exceeded'],currency=lim['currency'],
                     period=lim['period'],window_start=lim['window_start'],window_end=lim['window_end'],
                     business_timezone=lim['timezone'])
            if current:
                f['evidence_refs'] = lim['evidence_refs']
        facts = dict(context, certainty=f['certainty'],limit_available=lim is not None,
                     has_limit_evidence=bool(lim and lim['evidence_refs']),
                     limit_exceeded=result['exceeded'],period=lim['period'] if lim else None)
        rule_id, decision = self.rules.evaluate('limit',facts)
        f.update(decision)
        f['limit_rule_id'] = rule_id

    def investigate(self, s, intent):
        special = None
        if s['decision_origin']!='ISSUER':
            special = 'non_issuer'
        elif intent=='DECLINE' and s['decision']!='DECLINED':
            special = 'not_declined'
        controls = sorted(s['controls'],key=lambda c:not c['primary'])
        if intent=='LIMIT':
            controls = [c for c in controls if self.graph.is_a(c['type'],'LimitControl')]
        if special is None and not controls:
            special = 'no_information'
        if special:
            return [dict(self.bundle.rules[special],reason_category=None,control_level=None,
                         evidence_refs=[],diagnostic_rule_id=special)],[]
        findings = [self.control_finding(s,c,intent in ('CONTROL','LIMIT')) for c in controls]
        action_ids = {f['control_ref']:[a['id'] for a in self.graph.actions(f['control_type'])] for f in findings}
        return findings,action_ids
