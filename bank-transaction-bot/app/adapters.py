"""Read-only fixture adapter; every record passes an independently configured map."""
import copy
from app.paths import ROOT, read_json
from app.configuration import ConfigBundle
from app.mapping import BankMapper


def load_json(name):
    return read_json(ROOT/'config'/name)


class MockBankAdapter:
    data_mode = 'MOCK'

    def __init__(self, records=None, mapping=None, bundle=None):
        bundle = bundle or ConfigBundle()
        self.records = copy.deepcopy(records) if records is not None else load_json('scenarios.json')
        self.mapper = BankMapper(mapping or bundle.mapping,ontology=bundle.ontology)

    def list_attempts(self, principal):
        records = [self.mapper.normalize(raw) for raw in self.records]
        return [{k:s[k] for k in ('id','title','card_label','amount','currency','occurred_at')}
                for s in records if s['owner']==principal]

    def get_attempt(self, attempt_id, principal):
        for raw in self.records:
            record = self.mapper.normalize(raw)
            if record['id']==attempt_id and record['owner']==principal:
                return record
        raise KeyError('Transaction not found or not authorized')
