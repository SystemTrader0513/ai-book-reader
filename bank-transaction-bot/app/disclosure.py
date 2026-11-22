"""Apply configured disclosure before rendering or sending anything to an LLM."""
import copy


class DisclosurePolicy:
    def __init__(self, config):
        self.config = config

    def apply(self, finding, action_ids):
        f = copy.deepcopy(finding)
        category = f['reason_category']
        if category is None:
            return f, [self.config['fallback_action']]
        level = self.config['categories'].get(category,self.config['default'])
        if level=='FULL':
            return f,action_ids
        if level=='SILENT':
            return {'reason_category':None,'control_level':None,'certainty':'UNKNOWN',
                    'causal_role':'UNDETERMINED','message_key':self.config['silent']['message'],
                    'evidence_refs':[],'missing_evidence_keys':[]},self.config['silent']['allowed_actions']
        generic = self.config['generic']
        context = 'uncertain'
        if f['certainty']=='CONFIRMED':
            if f['causal_role']=='RULED_OUT':
                context = 'ruled_out'
            elif f.get('_current'):
                context = 'current_active' if f.get('_current_active') else 'current_inactive'
            else:
                context = 'historical'
        f['message_key'] = generic['messages'][context]
        # Amount and limit fields are excluded from generic explanations.
        for field in ('limit_type','limit_label','configured','effective','used','remaining','exceeded',
                      'currency','period','window_start','window_end','business_timezone'):
            f.pop(field,None)
        for field in generic['mask_fields']:
            f[field] = [] if field=='evidence_refs' else (None if field=='control_level' else generic['replacement'])
        return f, generic['allowed_actions']
