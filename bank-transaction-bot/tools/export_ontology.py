"""Export the executable JSON catalog to a reviewable OWL/Turtle vocabulary."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render():
    o = json.loads((ROOT/'config/ontology.json').read_text())
    lines = ['@prefix cd: <urn:bank-demo:> .',
             '@prefix owl: <http://www.w3.org/2002/07/owl#> .',
             '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .',
             '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .',
             'cd:Ontology a owl:Ontology ; owl:versionInfo "'+o['version']+'" .']
    core = ['Entity','Card','Account','Product','ControlLevel','ReasonCategory','PaymentAttempt','AuthorizationDecision','ControlEvaluation','DiagnosticCase','DiagnosticFinding','Evidence','Action','ActionRecommendation']
    for name in core:
        lines.append('cd:'+name+' a owl:Class .')
    for name, value in o['classes'].items():
        lines.append('cd:'+name+' a owl:Class .')
        for parent in value['parents']:
            lines.append('cd:'+name+' rdfs:subClassOf cd:'+parent+' .')
        if 'reason_category' in value:
            lines.append('cd:'+name+' cd:defaultReasonCategory cd:'+value['reason_category']+' .')
    lines.append('cd:appliesToConcept a owl:AnnotationProperty .')
    for action in o['actions']:
        lines.append('cd:'+action['id']+' a cd:Action ; cd:appliesToConcept cd:'+action['applies_to']+' .')
    lines.append('cd:defaultReasonCategory a owl:AnnotationProperty .')
    for level in o['control_levels']:
        lines.append('cd:'+level+' a cd:ControlLevel .')
    for category, label in o['reason_categories'].items():
        lines.append('cd:'+category+' a cd:ReasonCategory ; rdfs:label '+json.dumps(label,ensure_ascii=False)+' .')
    properties = {'controlLevel':('Control','ControlLevel'),'evaluatedControl':('ControlEvaluation','Control'),
                  'hasEvaluation':('AuthorizationDecision','ControlEvaluation'),'hasDecision':('PaymentAttempt','AuthorizationDecision'),
                  'hasFinding':('DiagnosticCase','DiagnosticFinding'),'supportedBy':('DiagnosticFinding','Evidence'),
                  'reasonCategory':('DiagnosticFinding','ReasonCategory')}
    for prop,(domain,range_) in properties.items():
        lines.append('cd:'+prop+' a owl:ObjectProperty ; rdfs:domain cd:'+domain+' ; rdfs:range cd:'+range_+' .')
    for prop in ('appliesTo','concernsAttempt','hasRecommendation'):
        lines.append('cd:'+prop+' a owl:ObjectProperty .')
    for prop in ('controlRef','certainty','causalRole','sourceSystem','sourceRecordId','observedAt','validAt','ruleVersion','evaluationResult','amount','currency','configuredValue','effectiveValue','usedAmount','windowStart','windowEnd','businessTimezone','aggregationKey'):
        lines.append('cd:'+prop+' a owl:DatatypeProperty .')
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    path=ROOT/'ontology/card-decline.ttl'
    path.write_text(render(),encoding='utf-8')
    print('Exported: '+str(path))
