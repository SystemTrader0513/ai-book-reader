import json
import threading
import unittest
import urllib.error
import urllib.request
from app.server import create_server
from app.conversation import classify_local


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, body=None):
        req = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type':'application/json'})
        return urllib.request.urlopen(req, timeout=3)

    def test_page_and_health(self):
        self.assertIn('交易诊断工作台', self.request('/').read().decode())
        self.assertEqual(json.load(self.request('/api/health'))['data_mode'], 'MOCK')

    def test_chat_and_context(self):
        r = json.load(self.request('/api/chat', {'scenario_id':'online-card','message':'这笔为什么被拒'}))
        self.assertEqual(r['transaction_ref'], 'online-card')
        self.assertIn('300.00', r['customer_response'])

    def test_chat_needs_selection(self):
        r = json.load(self.request('/api/chat', {'message':'帮我查一下'}))
        self.assertEqual(r['workflow_status'], 'NEEDS_INPUT')

    def test_invalid_input(self):
        for body in ([], {'message':3}, {'message':''}, {'message':'x'*2001}, {'message':'查原因','scenario_id':[]}):
            with self.assertRaises(urllib.error.HTTPError) as e:
                self.request('/api/chat', body)
            self.assertEqual(e.exception.code, 400)

    def test_unknown_id(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('/api/chat', {'message':'查原因','scenario_id':'fake'})
        self.assertEqual(e.exception.code, 404)

    def test_no_write_or_arbitrary_file_routes(self):
        for route in ('/config/scenarios.json','/../config/policy.json','/api/unfreeze'):
            with self.assertRaises(urllib.error.HTTPError) as e:
                self.request(route)
            self.assertEqual(e.exception.code, 404)

    def test_cross_origin_post_rejected(self):
        req = urllib.request.Request(self.base+'/api/chat', data=b'{}', headers={'Origin':'https://evil.example','Content-Type':'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        self.assertEqual(e.exception.code, 403)

    def test_security_intent_without_subject(self):
        r = json.load(self.request('/api/chat', {'message':'我的卡丢了'}))
        self.assertEqual(r['intents'], ['FRAUD_OR_SECURITY'])
        self.assertIn('官方', r['customer_response'])

    def test_general_question_without_selection(self):
        r = json.load(self.request('/api/chat', {'message':'什么是控制层级'}))
        self.assertEqual(r['intents'], ['GENERAL'])

    def test_explicit_intent_buttons(self):
        r = json.load(self.request('/api/chat', {'scenario_id':'unlocked-now','message':'查看当前控制','intent':'CONTROL'}))
        self.assertIn('已解除', r['customer_response'])

    def test_limit_question_maps_to_limit(self):
        self.assertEqual(classify_local('现在剩余额度是多少'), 'LIMIT')
        self.assertEqual(classify_local('为什么限额导致拒绝'), 'DECLINE')
