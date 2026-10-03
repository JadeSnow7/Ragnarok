#!/usr/bin/env python3
"""Loopback-only handoff proof. Standard-library server; no live model adapter."""
from __future__ import annotations
import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
TASK_RE = re.compile(r"^[a-f0-9]{32}$")
EXPECTED_FAILURE = 'checkbox state survives reload after toggling'
TERMINAL = {'passed', 'failed', 'rejected', 'interrupted'}

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(data):
    if not isinstance(data, bytes):
        data = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(data).hexdigest()

class Problem(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)

class Handoff:
    def __init__(self, root=ROOT, data_dir=None):
        self.root = Path(root).resolve()
        self.data = Path(data_dir or self.root / 'var').resolve()
        self.data.mkdir(parents=True, exist_ok=True)
        (self.data / 'runs').mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.data / 'tasks.sqlite3', check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, create_key TEXT UNIQUE, fingerprint TEXT, doc TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS decisions(key TEXT PRIMARY KEY, fingerprint TEXT, task_id TEXT)')
        self.lock = threading.RLock()
        self.threads = []
        self.db.commit()
        # A crashed command is not automatically replayed on process restart.
        with self.lock:
            for row in self.db.execute('SELECT doc FROM tasks').fetchall():
                doc = json.loads(row[0])
                if doc['state'] == 'running':
                    self._event(doc, 'interrupted', 'Server restarted during execution. Inspect evidence; create a new task to retry.')
                    self._save(doc)

    def close(self):
        for thread in self.threads:
            thread.join(20)
        self.db.close()

    def _event(self, doc, state, message):
        doc['state'] = state
        doc['revision'] += 1
        doc['updated_at'] = now()
        doc['events'].append({'at': now(), 'state': state, 'message': message})

    def _save(self, doc):
        self.db.execute('UPDATE tasks SET doc=? WHERE id=?', (json.dumps(doc), doc['id']))
        self.db.commit()

    def _get(self, task_id):
        if not TASK_RE.fullmatch(task_id):
            raise Problem(404, 'not_found', 'Task not found')
        row = self.db.execute('SELECT doc FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not row:
            raise Problem(404, 'not_found', 'Task not found')
        return json.loads(row[0])

    def get(self, task_id):
        with self.lock:
            return self._get(task_id)

    @staticmethod
    def _key(key):
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', key):
            raise Problem(400, 'invalid_key', 'Use an Idempotency-Key of 8–100 letters, digits, underscores or hyphens')

    def create(self, body, key):
        self._key(key)
        if not isinstance(body, dict) or set(body) != {'objective', 'recipe'}:
            raise Problem(400, 'invalid_request', 'Expected objective and recipe only')
        objective = body['objective']
        if not isinstance(objective, str) or not 5 <= len(objective.strip()) <= 2000:
            raise Problem(400, 'invalid_objective', 'Task description must contain 5–2000 characters')
        if body['recipe'] != 'todo-persistence-v1':
            raise Problem(422, 'unsupported_recipe', 'This proof supports only the todo persistence fixture; no general model runner is connected')
        fp = digest(body)
        with self.lock:
            old = self.db.execute('SELECT fingerprint,doc FROM tasks WHERE create_key=?', (key,)).fetchone()
            if old:
                if old[0] != fp:
                    raise Problem(409, 'idempotency_conflict', 'This key belongs to a different task input')
                return json.loads(old[1]), False
            patch = self.root / 'patches/todo-persistence.patch'
            manifest = {str(p.relative_to(self.root)): digest(p.read_bytes()) for p in sorted((self.root / 'fixture').glob('*')) if p.is_file()}
            plan = {'recipe': body['recipe'], 'objective_sha256': digest(objective),
                    'changed_files': ['fixture/store.mjs'], 'fixture_sha256': manifest,
                    'patch_sha256': digest(patch.read_bytes()),
                    'commands': ['node --test --test-reporter=tap fixture/store.test.mjs', 'git apply --check patch.diff', 'git apply patch.diff', 'node --test --test-reporter=tap fixture/store.test.mjs'],
                    'scope': 'New per-task fixture copy only; no user repository or network operations',
                    'executor': 'Agent-authored reviewed patch replay; no embedded autonomous model',
                    'expected_baseline_failure': EXPECTED_FAILURE}
            task_id = uuid.uuid4().hex
            doc = {'id':task_id, 'objective':objective.strip(), 'state':'awaiting_approval', 'revision':1,
                   'created_at':now(), 'updated_at':now(), 'plan':plan, 'plan_digest':digest(plan),
                   'events':[{'at':now(), 'state':'awaiting_approval', 'message':'Review the fixed recipe, patch and scope before execution'}],
                   'checks':[], 'run_count':0, 'error':None}
            self.db.execute('INSERT INTO tasks VALUES(?,?,?,?)', (task_id,key,fp,json.dumps(doc)))
            self.db.commit()
            return doc, True

    def decide(self, task_id, body, key):
        self._key(key)
        if not isinstance(body, dict) or set(body) != {'decision','revision','plan_digest'} or not isinstance(body.get('decision'), str) or body['decision'] not in {'approve','reject'}:
            raise Problem(400, 'invalid_decision', 'Expected approve/reject, revision and plan_digest')
        fp = digest({'task':task_id, 'body':body})
        with self.lock:
            old = self.db.execute('SELECT fingerprint,task_id FROM decisions WHERE key=?', (key,)).fetchone()
            if old:
                if old[0] != fp:
                    raise Problem(409, 'idempotency_conflict', 'Decision key already used for different input')
                return self._get(old[1]), False
            doc = self._get(task_id)
            if doc['state'] != 'awaiting_approval':
                raise Problem(409, 'invalid_transition', 'This task already has a decision. Create a new task to retry.')
            if type(body['revision']) is not int or body['revision'] != doc['revision'] or body['plan_digest'] != doc['plan_digest']:
                raise Problem(409, 'stale_approval', 'The reviewed plan or revision does not match. Reload before deciding.')
            approved = body['decision'] == 'approve'
            self._event(doc, 'running' if approved else 'rejected', 'Approved fixed patch and isolated fixture commands' if approved else 'Rejected; no workspace was created and no command ran')
            self.db.execute('INSERT INTO decisions VALUES(?,?,?)', (key,fp,task_id))
            self._save(doc)
            if approved:
                thread = threading.Thread(target=self._run, args=(task_id,), daemon=True)
                self.threads.append(thread)
                thread.start()
            return doc, True

    def _update(self, task_id, callback):
        with self.lock:
            doc = self._get(task_id)
            callback(doc)
            self._save(doc)
            return doc

    def _run(self, task_id):
        work = self.data / 'runs' / task_id
        try:
            doc = self.get(task_id)
            # Binding the approval to exact bytes prevents unreviewed source or patch changes.
            sources = {}
            for rel, sha in doc['plan']['fixture_sha256'].items():
                source = self.root / rel
                data = source.read_bytes()
                if source.is_symlink() or digest(data) != sha:
                    raise RuntimeError('Fixture changed after review; create a fresh task')
                sources[rel] = data
            patch = (self.root / 'patches/todo-persistence.patch').read_bytes()
            if digest(patch) != doc['plan']['patch_sha256']:
                raise RuntimeError('Patch changed after review; create a fresh task')
            patch_text = patch.decode('utf-8')
            if re.findall(r'^--- .+$', patch_text, re.M) != ['--- a/fixture/store.mjs'] or re.findall(r'^\+\+\+ .+$', patch_text, re.M) != ['+++ b/fixture/store.mjs']:
                raise RuntimeError('Patch scope must be exactly fixture/store.mjs')
            if re.search(r'^(diff |old mode|new mode|new file|deleted file|rename |copy |GIT binary)', patch_text, re.M):
                raise RuntimeError('Patch metadata is unsupported in this bounded recipe')
            work.mkdir(exist_ok=False)
            (work / 'fixture').mkdir()
            for rel, data in sources.items():
                (work / rel).write_bytes(data)
            (work / 'patch.diff').write_bytes(patch)
            (work / 'approved-plan.json').write_text(json.dumps(doc['plan'], indent=2))
            self._update(task_id, lambda d:d.update(run_count=d['run_count']+1))
            before_test = (work / 'fixture/store.test.mjs').read_bytes()
            base = self._command(task_id, work, 'baseline', ['node','--test','--test-reporter=tap','fixture/store.test.mjs'])
            if base['exit_code'] != 1 or f'not ok ' not in base['stdout'] or EXPECTED_FAILURE not in base['stdout'] or not re.search(r'# fail 1\b',base['stdout']):
                raise RuntimeError('Baseline did not fail exactly one expected regression test; patch withheld')
            if not re.search(r'not ok \d+ - '+re.escape(EXPECTED_FAILURE),base['stdout']):
                raise RuntimeError('Baseline failed for a different reason; patch withheld')
            checked = self._command(task_id, work, 'patch-check', ['git','apply','--check','patch.diff'])
            if checked['exit_code'] != 0:
                raise RuntimeError('Patch no longer applies cleanly')
            applied = self._command(task_id, work, 'patch-apply', ['git','apply','patch.diff'])
            if applied['exit_code'] != 0:
                raise RuntimeError('Patch application failed')
            if before_test != (work / 'fixture/store.test.mjs').read_bytes():
                raise RuntimeError('Verification tests changed; rejecting result')
            for rel, sha in doc['plan']['fixture_sha256'].items():
                if rel not in doc['plan']['changed_files'] and digest((work / rel).read_bytes()) != sha:
                    raise RuntimeError('Patch changed an unapproved file')
            actual_files = {str(p.relative_to(work)) for p in (work/'fixture').rglob('*') if p.is_file()}
            if actual_files != set(doc['plan']['fixture_sha256']):
                raise RuntimeError('Patch created or removed unapproved fixture files')
            verify = self._command(task_id, work, 'verification', ['node','--test','--test-reporter=tap','fixture/store.test.mjs'])
            if verify['exit_code'] != 0:
                raise RuntimeError('Post-patch verification failed; inspect command evidence')
            self._update(task_id, lambda d:self._event(d,'passed','Real baseline failed; approved patch applied; unchanged regression suite passed'))
        except Exception as exc:
            def failed(doc):
                doc['error'] = str(exc)
                self._event(doc,'failed',str(exc))
            self._update(task_id, failed)
        finally:
            if work.exists():
                doc = self.get(task_id)
                (work / 'evidence.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2))

    def _command(self, task_id, work, name, argv):
        started = now()
        t = time.monotonic()
        env = {'PATH':os.environ.get('PATH','/usr/bin:/bin'), 'HOME':str(work), 'LANG':'C.UTF-8', 'NO_COLOR':'1', 'GIT_CONFIG_NOSYSTEM':'1'}
        try:
            r = subprocess.run(argv, cwd=work, env=env, capture_output=True, text=True, timeout=15)
            code, stdout, stderr = r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired as exc:
            code, stdout, stderr = 124, str(exc.stdout or ''), 'Command exceeded the 15-second limit'
        check = {'name':name, 'argv':argv, 'started_at':started, 'duration_ms':round((time.monotonic()-t)*1000),
                 'exit_code':code, 'stdout':stdout, 'stderr':stderr}
        (work / f'{name}.log').write_text(f'$ {" ".join(argv)}\nexit_code={code}\n'+stdout+stderr)
        self._update(task_id, lambda d:d['checks'].append(check))
        return check

class Handler(BaseHTTPRequestHandler):
    server_version = 'HandoffProof/1.0'
    def log_message(self, fmt, *args):
        pass

    @property
    def app(self):
        return self.server.app

    def _guard(self, write=False):
        port = self.server.server_address[1]
        if self.headers.get('Host') not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
            raise Problem(403, 'host_rejected', 'Only loopback hostnames are accepted')
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://127.0.0.1:{port}', f'http://localhost:{port}'}:
            raise Problem(403,'origin_rejected','Cross-origin requests are not accepted')
        if write and self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            raise Problem(415,'json_required','Use application/json')

    def _send(self, status, data, mime='application/json'):
        payload = json.dumps(data,ensure_ascii=False).encode() if mime == 'application/json' else data
        self.send_response(status)
        self.send_header('Content-Type', mime + ('; charset=utf-8' if mime.startswith('text/') or mime=='application/json' else ''))
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, err):
        self._send(err.status, {'error':{'code':err.code,'message':err.message}})

    def do_GET(self):
        try:
            self._guard()
            path = urlparse(self.path).path
            if path == '/api/health':
                self._send(200,{'ok':True,'executor':'reviewed-patch-replay','live_model':False,'rinx_host_integration':False}); return
            match = re.fullmatch(r'/api/tasks/([a-f0-9]{32})(/evidence)?',path)
            if match:
                self._send(200,self.app.get(match[1])); return
            if path == '/api/patch':
                self._send(200,{'patch':(self.app.root/'patches/todo-persistence.patch').read_text()}); return
            match = re.fullmatch(r'/preview/([a-f0-9]{32})/(index.html|store.mjs|app.mjs|style.css)',path)
            if match:
                doc=self.app.get(match[1])
                if doc['state'] != 'passed':
                    raise Problem(409,'preview_unavailable','Preview is available only after verification passes')
                target = self.app.data/'runs'/match[1]/'fixture'/match[2]
            elif path.startswith('/fixture/') and re.fullmatch(r'/fixture/(index.html|store.mjs|app.mjs|style.css)',path):
                target = self.app.root/path.lstrip('/')
            else:
                files={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
                if path not in files:
                    raise Problem(404,'not_found','Page not found')
                target=self.app.root/'web'/files[path]
            if not target.is_file():
                raise Problem(404,'not_found','File not found')
            mime = 'text/javascript' if target.suffix in {'.js','.mjs'} else mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
            self._send(200,target.read_bytes(),mime)
        except Problem as err:
            self._error(err)
        except Exception:
            self._error(Problem(500,'internal_error','Unexpected server failure; inspect local server logs'))

    def do_POST(self):
        try:
            self._guard(write=True)
            try:
                size=int(self.headers.get('Content-Length','0'))
            except ValueError:
                raise Problem(400,'invalid_length','Invalid content length')
            if not 0 < size <= 16384:
                raise Problem(413,'invalid_size','JSON body must be 1–16384 bytes')
            try:
                body=json.loads(self.rfile.read(size))
            except (ValueError,UnicodeDecodeError):
                raise Problem(400,'invalid_json','Malformed JSON')
            key=self.headers.get('Idempotency-Key')
            path=urlparse(self.path).path
            if path == '/api/tasks':
                doc,created=self.app.create(body,key)
                self._send(201 if created else 200,doc);return
            match=re.fullmatch(r'/api/tasks/([a-f0-9]{32})/decision',path)
            if match:
                doc,changed=self.app.decide(match[1],body,key)
                self._send(202 if changed and doc['state']=='running' else 200,doc);return
            raise Problem(404,'not_found','API route not found')
        except Problem as err:
            self._error(err)
        except Exception:
            self._error(Problem(500,'internal_error','Unexpected server failure; inspect local server logs'))

def make_server(port=8765, data_dir=None, root=ROOT):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.app=Handoff(root,data_dir)
    return server

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--data-dir',type=Path)
    args=parser.parse_args()
    server=make_server(args.port,args.data_dir)
    print(f'Handoff Proof running at http://127.0.0.1:{server.server_address[1]}',flush=True)
    print('Loopback only. Reviewed fixture patch replay; no live model or Rinx host bridge.',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.app.close()
