"""Customer messages from templates only; no business decisions in this module."""
PUBLIC_FINDING_FIELDS = {'reason_category','control_type','control_level','control_ref',
    'affected_object_ref','certainty','causal_role','evidence_refs','source_system',
    'evaluation_result','rule_version','diagnostic_rule_id','limit_rule_id','observed_at',
    'historical_snapshot_available','limit_type','limit_label','configured','effective','used',
    'remaining','exceeded','currency','period','window_start','window_end','business_timezone'}


class Presenter:
    def __init__(self, bundle):
        self.bundle = bundle
        self.templates = bundle.templates

    def message(self, key, values=None):
        return self.templates['messages'][key].format_map(values or {})

    def finding(self, internal, transaction):
        public = {key:value for key,value in internal.items() if key in PUBLIC_FINDING_FIELDS}
        values = dict(public, reason_label=self.bundle.ontology['reason_categories'].get(internal['reason_category'],''),
                      decision=transaction['decision'])
        public['safe_summary'] = self.message(internal['message_key'],values)
        public['missing_evidence'] = [self.templates['evidence_labels'][key] for key in internal.get('missing_evidence_keys',[])]
        return public

    def action(self, action_id):
        return dict(self.templates['actions'][action_id],id=action_id,requires_confirmation=False,
                    execution_status='NOT_EXECUTED',kind='GUIDANCE')

    def response(self, findings, actions):
        templates = self.templates['response']
        lines = [templates['header']]
        for f in findings:
            lines.append(templates['finding'].format_map(f) if f.get('control_level') else f['safe_summary'])
            if f.get('remaining') is not None:
                key = 'current_daily' if f['causal_role']=='CURRENT_STATE' else 'historical_daily'
                lines.append(templates[key].format_map(f))
            if f.get('period')=='SINGLE':
                lines.append(templates['single'].format_map(f))
        if actions:
            lines.append(actions[0]['instruction'])
        return '\n'.join(lines)
