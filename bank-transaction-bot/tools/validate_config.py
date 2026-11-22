"""Validate cross-layer references and replay every simulated case, offline."""
import sys
from pathlib import Path

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from app.configuration import ConfigBundle
from app.mapping import BankMapper
from app.adapters import MockBankAdapter
from app.service import InvestigationService


def main():
    bundle = ConfigBundle()
    service = InvestigationService(bundle=bundle)
    count = 0
    for scenario in service.list_scenarios():
        for intent in ('DECLINE','CONTROL','LIMIT'):
            service.diagnose(scenario['id'],intent)
            count += 1
    legacy = bundle.read('mappings/legacy-demo.json')
    raw = bundle.read('config/raw-bank-example.json')
    mapper = BankMapper(legacy)
    mapped = mapper.normalize(raw)
    service = InvestigationService(adapter=MockBankAdapter(records=[raw],mapping=legacy,bundle=bundle),bundle=bundle)
    service.diagnose(mapped['id'])
    print('Configuration valid; %s normalized-case replays + legacy mapping replay passed.' % count)
    print('Versions: '+str(bundle.versions()))


if __name__=='__main__':
    main()
