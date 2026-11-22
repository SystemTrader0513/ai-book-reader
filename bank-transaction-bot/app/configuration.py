"""Versioned configuration bundle with cross-layer reference validation."""
from string import Formatter
from pathlib import Path
from app.paths import ROOT, read_json
from app.domain import OntologyGraph
from app.mapping import BankMapper
from app.rules import RuleEngine

TEMPLATE_FIELDS = {'reason_label','limit_label','decision','control_level','safe_summary',
                   'effective','used','remaining','currency'}
REQUIRED_MESSAGES = {'fraud','general','out_of_scope','needs_selection'}


class ConfigBundle:
    def __init__(self, root=None):
        self.root = Path(root) if root else ROOT
        self.ontology = self.read('config/ontology.json')
        self.runtime = self.read('config/runtime.json')
        self.mapping = self.read(self.runtime['mapping_profile'])
        self.rules = self.read('rules/diagnosis.json')
        self.policy = self.read('policies/disclosure.json')
        self.templates = self.read('templates/zh-CN.json')
        self.validate()

    def read(self, path):
        target = (self.root/path).resolve()
        if self.root.resolve() not in target.parents:
            raise ValueError('Configuration path must stay inside project')
        return read_json(target)

    def validate(self):
        graph = OntologyGraph(self.ontology)
        RuleEngine(self.rules)
        BankMapper(self.mapping,ontology=self.ontology)
        levels = set(self.ontology['control_levels'])
        for enum,allowed in [('levels',levels),('types',set(self.ontology['classes']))]:
            if not set(self.mapping['enums'][enum].values()) <= allowed:
                raise ValueError('Mapping references unknown ontology '+enum)
        for name in self.ontology['classes']:
            if name != 'Control':
                graph.category(name)
        messages = self.templates['messages']
        required = set(REQUIRED_MESSAGES)
        assignments = [r['set'] for table in self.rules['tables'].values() for r in table]
        assignments += [self.rules[k] for k in ('non_issuer','no_information','not_declined')]
        for assignment in assignments:
            if 'message_key' in assignment:
                required.add(assignment['message_key'])
            for key in assignment.get('missing_evidence_keys',[]):
                if key not in self.templates['evidence_labels']:
                    raise ValueError('Unknown evidence template: '+key)
        if set(self.policy['generic']['messages']) != {'historical','uncertain','current_active','current_inactive','ruled_out'}:
            raise ValueError('Missing generic disclosure context')
        required.update(self.policy['generic']['messages'].values())
        required.add(self.policy['silent']['message'])
        if not required <= set(messages):
            raise ValueError('Missing message templates: '+str(required-set(messages)))
        base_fields = {'reason_label','control_level','decision'}
        uses = [(a.get('message_key'),base_fields) for a in [r['set'] for r in self.rules['tables']['base']]]
        uses += [(a.get('message_key'),base_fields) for a in [self.rules[k] for k in ('non_issuer','no_information','not_declined')]]
        for rule in self.rules['tables']['limit']:
            allowed = base_fields if rule['id'] in ('no-current-limit','no-historical-limit') else base_fields | {'limit_label'}
            uses.append((rule['set'].get('message_key'),allowed))
        uses += [(key,set()) for key in REQUIRED_MESSAGES]
        uses += [(key,base_fields) for key in self.policy['generic']['messages'].values()]
        uses += [(self.policy['silent']['message'],base_fields)]
        for key,allowed in uses:
            if key is not None:
                fields = {f for _,f,_,_ in Formatter().parse(messages[key]) if f is not None}
                if not fields <= allowed:
                    raise ValueError('Template variables unavailable in context: '+key)
        for text in list(messages.values())+list(self.templates['response'].values()):
            if not isinstance(text,str):
                raise ValueError('Template must be a string')
            for _,field,spec,conversion in Formatter().parse(text):
                if field is not None and (field not in TEMPLATE_FIELDS or spec or conversion):
                    raise ValueError('Unsupported template placeholder: '+str(field))
        for key in ('header','finding','historical_daily','current_daily','single'):
            if key not in self.templates['response']:
                raise ValueError('Missing response template: '+key)
        action_ids = {a['id'] for a in self.ontology['actions']}
        if len(action_ids) != len(self.ontology['actions']):
            raise ValueError('Duplicate ontology action IDs')
        for action in self.ontology['actions']:
            if action['applies_to'] not in self.ontology['classes']:
                raise ValueError('Action references unknown concept')
            if 'instruction' in action or 'label' in action:
                raise ValueError('Customer action text belongs in templates')
        used_actions = action_ids | set(self.policy['generic']['allowed_actions']) | set(self.policy['silent']['allowed_actions']) | {self.policy['fallback_action']}
        for action in used_actions:
            if action not in self.templates['actions'] or set(self.templates['actions'][action]) != {'label','instruction'}:
                raise ValueError('Missing action templates: '+action)
        if not set(self.policy['categories']) <= set(self.ontology['reason_categories']):
            raise ValueError('Disclosure references unknown reason category')
        if not (set(self.policy['categories'].values()) | {self.policy['default']}) <= {'FULL','GENERIC','SILENT'}:
            raise ValueError('Unknown disclosure level')
        if not set(self.policy['generic']['mask_fields']) <= {'evaluation_result','rule_version','control_ref','affected_object_ref','source_system','evidence_refs','control_type','control_level'}:
            raise ValueError('Unsupported disclosure mask field')

    def versions(self, mapping_version=None):
        return {'ontology':self.ontology['version'], 'mapping':mapping_version or self.mapping['version'],
                'rules':self.rules['version'], 'policy':self.policy['version'], 'templates':self.templates['version']}
