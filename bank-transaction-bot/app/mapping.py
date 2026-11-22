"""Declarative, whitelist-only mapping. Source response codes are not diagnoses."""
import copy
from app.domain import money
from app.paths import ROOT, read_json


class MappingError(ValueError):
    pass


def lookup(data, path):
    for part in path.split('.'):
        if not isinstance(data, dict) or part not in data:
            raise KeyError(path)
        data = data[part]
    return data


class BankMapper:
    def __init__(self, profile, ontology=None):
        self.profile = copy.deepcopy(profile)
        self.version = profile['version']
        ontology = ontology or read_json(ROOT/'config/ontology.json')
        self.domains = {
            'types':set(ontology['classes'])-{'Control'},
            'levels':set(ontology['control_levels']),
            'evaluations':{'PASS','FAIL','SKIPPED','ERROR','UNKNOWN'},
            'origins':{'ISSUER','NETWORK','MERCHANT','ACQUIRER','UNKNOWN'},
            'decisions':{'DECLINED','APPROVED','TIMEOUT','UNKNOWN'},
            'periods':{'SINGLE','DAILY'}
        }
        for domain, allowed in self.domains.items():
            values = profile['enums'].get(domain)
            if not isinstance(values,dict) or not set(values.values()) <= allowed:
                raise MappingError('Invalid normalized enum domain: '+domain)
        if set(profile['fields']) != {'transaction','control','limit'}:
            raise MappingError('Mapping requires transaction/control/limit fields')
        for fields in profile['fields'].values():
            for spec in fields.values():
                if not isinstance(spec.get('source'),str) or not spec['source']:
                    raise MappingError('Invalid mapping source')
                if 'enum' in spec and spec['enum'] not in profile['enums']:
                    raise MappingError('Unknown enum dictionary')

    def fields(self, source, group):
        if not isinstance(source, dict):
            raise MappingError('Mapped source must be an object: '+group)
        result = {}
        for target, spec in self.profile['fields'][group].items():
            try:
                value = lookup(source, spec['source'])
            except KeyError:
                if spec.get('required',False):
                    raise MappingError('Missing required field: '+group+'.'+target)
                value = copy.deepcopy(spec.get('default'))
            if 'enum' in spec:
                values = self.profile['enums'][spec['enum']]
                if not isinstance(value,str) or value not in values:
                    raise MappingError('Unmapped enum: '+group+'.'+target)
                value = values[value]
            result[target] = copy.deepcopy(value)
        return result

    def normalize(self, raw):
        record = self.fields(raw,'transaction')
        try:
            source_controls = lookup(raw,self.profile['collections']['controls'])
        except KeyError as exc:
            raise MappingError('Missing control collection') from exc
        if not isinstance(source_controls,list):
            raise MappingError('Controls must be a list')
        controls = []
        for source in source_controls:
            c = self.fields(source,'control')
            for key,domain in (('type','types'),('level','levels'),('evaluation','evaluations')):
                if c[key] not in self.domains[domain]:
                    raise MappingError('Invalid normalized control value: '+key)
            for key in ('current_active','effective_at_transaction'):
                if c[key] is not None and type(c[key]) is not bool:
                    raise MappingError('Control state must be bool or unknown: '+key)
            for key in ('primary','conflict'):
                if type(c[key]) is not bool:
                    raise MappingError('Invalid boolean: '+key)
            if not isinstance(c['evidence_refs'],list) or not all(isinstance(v,str) for v in c['evidence_refs']):
                raise MappingError('Invalid evidence references')
            for target, collection in (('limit','historical_limit'),('current_limit','current_limit')):
                try:
                    lim = lookup(source,self.profile['collections'][collection])
                except KeyError:
                    continue
                if lim is None:
                    continue
                normalized = self.fields(lim,'limit')
                if normalized['period'] not in self.domains['periods']:
                    raise MappingError('Invalid normalized limit period')
                for key in ('configured','effective','used'):
                    if normalized[key] is not None:
                        money(normalized[key])
                        normalized[key] = str(normalized[key])
                if not isinstance(normalized['evidence_refs'],list) or not all(isinstance(v,str) for v in normalized['evidence_refs']):
                    raise MappingError('Invalid limit evidence references')
                c[target] = normalized
            controls.append(c)
        for key,domain in (('decision_origin','origins'),('decision','decisions')):
            if record[key] not in self.domains[domain]:
                raise MappingError('Invalid normalized decision')
        money(record['amount'])
        record['amount'] = str(record['amount'])
        if type(record['historical_snapshot']) is not bool:
            raise MappingError('Historical snapshot flag must be boolean')
        for key in ('id','owner','currency','decision_origin','decision'):
            if not isinstance(record[key],str) or not record[key]:
                raise MappingError('Invalid transaction field: '+key)
        code = record.get('response_code')
        if code is not None:
            key = str(record.get('response_network'))+'@'+str(record.get('response_version'))+':'+str(code)
            hint = self.profile.get('response_codes',{}).get(key)
            record['response_hint'] = dict(hint,status='MAPPED') if hint else {'status':'UNMAPPED'}
        record['controls'] = controls
        record['mapping_version'] = self.version
        return record
