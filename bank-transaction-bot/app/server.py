"""Loopback-only demonstration HTTP server, not a production web server."""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from app.adapters import ROOT
from app.conversation import chat, INTENTS
from app.service import InvestigationService


class Handler(BaseHTTPRequestHandler):
    server_version = 'CardInvestigationDemo/0.2'

    def log_message(self, format, *args):
        pass  # no request text, bank data or model secrets in default logs

    def reply(self, status, payload, content_type='application/json; charset=utf-8'):
        raw = json.dumps(payload, ensure_ascii=False).encode() if content_type.startswith('application/json') else payload
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {'error':'仅允许本机访问'})
        route = urlparse(self.path).path
        service = self.server.service
        if route == '/api/health':
            return self.reply(200, {'status':'ok','data_mode':'MOCK','model_mode':'LLM_INTENT' if os.environ.get('BOT_MODEL_MODE')=='llm' else 'LOCAL','version':'0.2'})
        if route == '/api/scenarios':
            return self.reply(200, service.list_scenarios())
        if route == '/api/ontology':
            return self.reply(200, service.ontology)
        files = {'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if route in files:
            name, mime = files[route]
            return self.reply(200, (ROOT/'static'/name).read_bytes(), mime)
        return self.reply(404, {'error':'页面不存在'})

    def valid_host(self):
        return self.headers.get('Host') in ('127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port))

    def do_POST(self):
        self.connection.settimeout(20)
        if not self.valid_host():
            return self.reply(403, {'error':'仅允许本机访问'})
        origin = self.headers.get('Origin')
        allowed = {'http://127.0.0.1:'+str(self.server.server_port), 'http://localhost:'+str(self.server.server_port)}
        if origin and origin not in allowed:
            return self.reply(403, {'error':'不允许跨站请求'})
        if self.path != '/api/chat':
            return self.reply(404, {'error':'接口不存在'})
        if self.headers.get_content_type() != 'application/json':
            return self.reply(415, {'error':'请使用 application/json'})
        try:
            if self.headers.get('Transfer-Encoding'):
                raise ValueError('不支持分块请求')
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > 16384:
                raise ValueError('请求长度无效')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('请求须为 JSON 对象')
            message = body.get('message')
            subject = body.get('scenario_id')
            intent = body.get('intent')
            if not isinstance(message, str) or not message.strip() or len(message) > 2000:
                raise ValueError('请输入 1–2000 字的问题')
            if subject is not None and (not isinstance(subject, str) or len(subject)>100):
                raise ValueError('交易引用无效')
            if intent is not None and intent not in INTENTS:
                raise ValueError('意图无效')
            result = chat(self.server.service, message.strip(), subject, intent)
            return self.reply(200, result)
        except KeyError:
            return self.reply(404, {'error':'交易不存在或无权查看'})
        except (ValueError, TypeError, UnicodeError):
            return self.reply(400, {'error':'请求无效，请检查消息、交易和意图字段'})
        except Exception:
            return self.reply(500, {'error':'服务暂时不可用，请稍后重试'})


def create_server(port=8765):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.service = InvestigationService()
    return server


def main():
    parser = argparse.ArgumentParser(description='本地卡交易诊断演示')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = create_server(args.port)
    print('模拟数据 / 只读演示：http://127.0.0.1:%s' % server.server_port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务已停止。')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
