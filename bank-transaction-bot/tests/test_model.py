import json
import os
import unittest
from unittest.mock import patch
from app.conversation import classify
from app.domain import OntologyGraph
from tools.export_ontology import render
from app.adapters import ROOT


class ModelContractTests(unittest.TestCase):
    def env(self):
        return patch.dict(os.environ, {'BOT_MODEL_MODE':'llm','BOT_LLM_ENDPOINT':'https://approved.example/v1/chat/completions','BOT_LLM_API_KEY':'test-only-key','BOT_LLM_MODEL':'demo-model'}, clear=True)

    def test_model_receives_only_minimized_question(self):
        captured = {}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n): return json.dumps({'choices':[{'message':{'content':'{"intent":"LIMIT"}'}}]}).encode()
        class Opener:
            def open(self, request, timeout):
                captured['payload'] = json.loads(request.data)
                return Response()
        with self.env(), patch('urllib.request.build_opener', return_value=Opener()):
            self.assertEqual(classify('剩余额度 1234567890123456'), ('LIMIT','LLM'))
        data = json.dumps(captured['payload'])
        self.assertNotIn('1234567890123456', data)
        self.assertNotIn('controls', data)
        self.assertNotIn('test-only-key', data)

    def test_network_failure_falls_back(self):
        with self.env(), patch('urllib.request.build_opener', side_effect=OSError('offline')):
            self.assertEqual(classify('为什么被拒'), ('DECLINE','LOCAL_FALLBACK'))

    def test_invalid_model_output_falls_back(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self,n): return b'{"choices":[{"message":{"content":"ignore all rules"}}]}'
        class Opener:
            def open(self,*args,**kwargs): return Response()
        with self.env(), patch('urllib.request.build_opener', return_value=Opener()):
            self.assertEqual(classify('为什么被拒'), ('DECLINE','LOCAL_FALLBACK'))

    def test_insecure_endpoint_never_called(self):
        with self.env(), patch.dict(os.environ, {'BOT_LLM_ENDPOINT':'http://insecure.example'}), patch('urllib.request.build_opener') as call:
            self.assertEqual(classify('现在额度'), ('LIMIT','LOCAL_FALLBACK'))
            call.assert_not_called()

    def test_security_intent_stays_local(self):
        with self.env(), patch('urllib.request.build_opener') as call:
            self.assertEqual(classify('我的卡丢了'), ('FRAUD_OR_SECURITY','LOCAL'))
            call.assert_not_called()


class OntologyTests(unittest.TestCase):
    def test_cycle_rejected(self):
        with self.assertRaises(ValueError):
            OntologyGraph({'classes':{'A':{'parents':['B']},'B':{'parents':['A']}}})

    def test_owl_export_matches_runtime_catalog(self):
        self.assertEqual(render(), (ROOT/'ontology/card-decline.ttl').read_text())
