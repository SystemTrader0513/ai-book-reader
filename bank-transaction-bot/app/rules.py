"""Ordered JSON decision tables. No eval, Python expressions or tool execution."""
import copy

FACT_NAMES = {'conflict','current','current_known','current_active','evaluation',
              'historical_snapshot','has_evidence','effective_at_transaction','recorded_role',
              'limit_available','has_limit_evidence','limit_exceeded','certainty','period'}
SET_FIELDS = {'certainty','causal_role','message_key','missing_evidence_keys'}
CERTAINTIES = {'CONFIRMED','INFERRED','UNKNOWN','CONFLICTED'}
ROLES = {'CURRENT_STATE','UNDETERMINED','RULED_OUT','RECORDED_PRIMARY_CAUSE',
         'RECORDED_SECONDARY_CAUSE','POTENTIAL_BLOCKER'}


class RuleEngine:
    def __init__(self, config):
        self.config = config
        if config.get('strategy') != 'FIRST_MATCH':
            raise ValueError('Only FIRST_MATCH is supported')
        if set(config['tables']) != {'base','limit'}:
            raise ValueError('Expected base and limit tables')
        seen = set()
        for table in config['tables'].values():
            if not table or table[-1]['when'] != {'always':True}:
                raise ValueError('Each decision table needs a final fallback')
            for rule in table:
                if rule['id'] in seen:
                    raise ValueError('Duplicate rule ID')
                seen.add(rule['id'])
                self.validate_condition(rule['when'])
                self.validate_assignment(rule['set'])
        for name in ('non_issuer','no_information','not_declined'):
            self.validate_assignment(config[name])
        if not set(config['escalate_certainties']) <= CERTAINTIES:
            raise ValueError('Invalid escalation certainty')

    def validate_condition(self, cond):
        if not isinstance(cond,dict):
            raise ValueError('Condition must be an object')
        if cond == {'always':True}:
            return
        if set(cond) in ({'all'},{'any'}):
            values = next(iter(cond.values()))
            if not isinstance(values,list) or not values:
                raise ValueError('Logical conditions must be non-empty lists')
            for item in values:
                self.validate_condition(item)
            return
        if set(cond) not in ({'fact','eq'},{'fact','in'}):
            raise ValueError('Unsupported rule operator')
        if cond['fact'] not in FACT_NAMES:
            raise ValueError('Unknown fact: '+str(cond['fact']))
        if 'in' in cond and not isinstance(cond['in'],list):
            raise ValueError('in requires a list')

    def validate_assignment(self, assignment):
        if not isinstance(assignment,dict) or not set(assignment) <= SET_FIELDS:
            raise ValueError('Unsupported rule assignment')
        for name,value in assignment.items():
            if isinstance(value,dict):
                if name != 'causal_role' or value != {'fact':'recorded_role'}:
                    raise ValueError('Unsupported fact assignment')
            elif name=='certainty' and value not in CERTAINTIES:
                raise ValueError('Invalid certainty')
            elif name=='causal_role' and value not in ROLES:
                raise ValueError('Invalid causal role')
            elif name=='message_key' and not isinstance(value,str):
                raise ValueError('Invalid template key')
            elif name=='missing_evidence_keys' and (not isinstance(value,list) or not all(isinstance(v,str) for v in value)):
                raise ValueError('Invalid missing-evidence keys')

    def matches(self, cond, facts):
        if 'always' in cond:
            return True
        if 'all' in cond:
            return all(self.matches(c,facts) for c in cond['all'])
        if 'any' in cond:
            return any(self.matches(c,facts) for c in cond['any'])
        name = cond['fact']
        if name not in facts:
            raise ValueError('Missing runtime fact: '+name)
        value = facts[name]
        options = cond['in'] if 'in' in cond else [cond['eq']]
        return any(type(value) is type(option) and value==option for option in options)

    def evaluate(self, table, facts):
        for rule in self.config['tables'][table]:
            if self.matches(rule['when'],facts):
                result = copy.deepcopy(rule['set'])
                for field,value in result.items():
                    if isinstance(value,dict):
                        if value['fact'] not in facts:
                            raise ValueError('Missing assignment fact')
                        result[field] = facts[value['fact']]
                return rule['id'], result
        raise ValueError('No decision rule matched')
