"""Stub model tests are explicitly separate from a real Codex model invocation."""
import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Problem, digest
from live_executor import LiveHandoff, candidate_patch, ProcessRunner, SOURCE, validate_cli_events
ROOT=Path(__file__).resolve().parents[1]

class Stub:
    def __init__(self,kind='ok',gate=None): self.kind=kind; self.gate=gate; self.count=0
    def generate(self,work,objective,source,base_hash,cancel):
        self.count+=1
        if self.gate:
            while not self.gate.wait(.01) and not cancel.is_set(): pass
        record={'name':'stub-model','argv':['STUB-NOT-CODEX'],'exit_code':7 if self.kind=='failure' else 0,
                'stdout':'STUB','stderr':'','duration_ms':0,'exit_confirmed':True,'stop_reason':None}
        if self.kind=='failure': return None,record
        content=source.replace('// Known baseline bug: the in-memory toggle is not saved before reload.','persist();')
        if self.kind=='badfix': content=source+'\n// deliberately not fixed\n'
        if self.kind=='permission': content="import {execSync} from 'node:child_process';\nexecSync('touch forbidden');\n"+content
        return {'path':SOURCE if self.kind!='path' else 'fixture/store.test.mjs',
                'base_sha256':base_hash if self.kind!='base' else '0'*64,'content':content},record

class LiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)/'repo';self.root.mkdir()
        for name in ('fixture','patches','web'): shutil.copytree(ROOT/name,self.root/name)
        self.data=Path(self.temp.name)/'data'; self.stub=Stub()
        self.app=LiveHandoff(self.root,self.data,live_enabled=True,adapter=self.stub)
    def tearDown(self): self.app.close();self.temp.cleanup()
    def create(self,key='live-create-0001'):
        return self.app.create({'mode':'live','recipe':'todo-persistence-v1','objective':'Fix Todo checkbox persistence after reload'},key)[0]
    def finish(self,d):
        for t in self.app.threads:
            t.join(10);self.assertFalse(t.is_alive())
        return self.app.get(d['id'])
    def ready(self): return self.finish(self.create())
    def body(self,d,choice='approve'): return {'decision':choice,'revision':d['revision'],'plan_digest':d['plan_digest']}
    def approve(self,d): self.app.decide(d['id'],self.body(d),'approval-0001');return self.finish(d)
    def test_stub_candidate_waits_then_real_fixed_tests_pass_once(self):
        d=self.ready();self.assertEqual(d['state'],'awaiting_approval');self.assertEqual(d['checks'],[])
        self.assertFalse((self.data/'runs'/d['id']).exists())
        self.assertEqual(self.stub.count,1)
        result=self.approve(d);self.assertEqual(result['state'],'passed',result['error'])
        self.assertEqual([c['exit_code'] for c in result['checks']],[1,0,0,0])
        self.assertIn('--permission',result['checks'][-1]['argv'])
        replay,changed=self.app.decide(d['id'],self.body(d),'approval-0001')
        self.assertFalse(changed);self.assertEqual(replay['run_count'],1)
        self.assertEqual(result['approval']['candidate_id'],d['plan']['candidate_id'])
        self.assertEqual((ROOT/'fixture/store.test.mjs').read_bytes(),(self.data/'runs'/d['id']/'fixture/store.test.mjs').read_bytes())
    def test_reject_zero_target_commands(self):
        d=self.ready();result,_=self.app.decide(d['id'],self.body(d,'reject'),'reject-key-0001')
        self.assertEqual(result['state'],'rejected');self.assertEqual(result['checks'],[]);self.assertEqual(result['run_count'],0)
        self.assertFalse((self.data/'runs'/d['id']).exists());self.assertEqual(self.stub.count,1)
    def test_create_idempotency_and_mode_conflict(self):
        d=self.ready();again=self.create();self.assertEqual(d['id'],again['id']);self.assertEqual(self.stub.count,1)
        with self.assertRaises(Problem):
            self.app.create({'mode':'fixed','recipe':'todo-persistence-v1','objective':d['objective']},'live-create-0001')
    def test_wrong_base_and_out_of_scope_fail_before_approval(self):
        for i,kind in enumerate(('base','path','failure')):
            self.stub.kind=kind;d=self.finish(self.create('create-key-'+str(i)))
            self.assertEqual(d['state'],'failed');self.assertIsNone(d['candidate_patch']);self.assertEqual(d['checks'],[])
    def test_drift_after_review_zero_execution(self):
        d=self.ready();(self.root/SOURCE).write_text('drift')
        result=self.approve(d);self.assertEqual(result['state'],'failed');self.assertEqual(result['checks'],[])
    def test_candidate_tamper_zero_execution(self):
        d=self.ready();self.app._update(d['id'],lambda x:x.update(candidate_patch=x['candidate_patch']+'tampered'))
        result=self.approve(d);self.assertEqual(result['state'],'failed');self.assertEqual(result['checks'],[])
    def test_stale_approval_cannot_apply(self):
        d=self.ready()
        with self.assertRaises(Problem): self.app.decide(d['id'],self.body(d)|{'plan_digest':'0'*64},'approval-0001')
        self.assertEqual(self.app.get(d['id'])['state'],'awaiting_approval')
    def test_bad_fix_fails_real_verification(self):
        self.stub.kind='badfix';d=self.approve(self.ready())
        self.assertEqual(d['state'],'failed');self.assertEqual(d['checks'][-1]['exit_code'],1)
    def test_candidate_cannot_spawn_external_command(self):
        self.stub.kind='permission';d=self.approve(self.ready())
        self.assertEqual(d['state'],'failed');self.assertIn('ERR_ACCESS_DENIED',d['checks'][-1]['stdout']+d['checks'][-1]['stderr'])
        self.assertFalse((self.data/'runs'/d['id']/'forbidden').exists())
    def test_single_slot_and_cancel_generation(self):
        self.stub.gate=threading.Event();d=self.create()
        with self.assertRaises(Problem) as err: self.create('second-create-0001')
        self.assertEqual(err.exception.code,'executor_busy')
        result=self.app.cancel(d['id'],{},'cancel-key-0001');self.assertEqual(result['state'],'cancelling')
        d=self.finish(d);self.assertEqual(d['state'],'cancelled');self.assertEqual(d['checks'],[])
        self.assertEqual(self.app.cancel(d['id'],{},'cancel-key-0001')['state'],'cancelled')
    def test_concurrent_approval_runs_once(self):
        d=self.ready()
        def approve(key):
            try:self.app.decide(d['id'],self.body(d),key);return 'ok'
            except Problem:return 'blocked'
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertCountEqual(list(pool.map(approve,['approve-key-0001','approve-key-0002'])),['ok','blocked'])
        self.assertEqual(self.finish(d)['run_count'],1)
    def test_live_disabled_has_no_model_call(self):
        self.app.live_enabled=False
        with self.assertRaises(Problem):self.create()
        self.assertEqual(self.stub.count,0)
    def test_exclusive_data_directory_lease(self):
        with self.assertRaises(RuntimeError):LiveHandoff(self.root,self.data)
    def test_restart_unknown_blocks_execution(self):
        d=self.ready();self.app._update(d['id'],lambda x:self.app._event(x,'generating','Injected crash state'))
        self.app.close();self.app=LiveHandoff(self.root,self.data,live_enabled=True,adapter=self.stub)
        self.assertEqual(self.app.get(d['id'])['state'],'unknown')
        with self.assertRaises(Problem):self.create('restart-create-0001')
    def test_patch_size_text_path_constraints(self):
        source=(self.root/SOURCE).read_text();base=digest(source.encode())
        for content in ('a'*40000+'\n','bad\x00\n',source):
            with self.assertRaises(ValueError): candidate_patch({'path':SOURCE,'base_sha256':base,'content':content},source,base)

class ProcessTests(unittest.TestCase):
    def test_real_timeout_reaps_process(self):
        with tempfile.TemporaryDirectory() as work:
            r=ProcessRunner().run([sys.executable,'-c','import time; time.sleep(30)'],work,{'PATH':os.environ['PATH']},threading.Event(),.1)
            self.assertEqual(r['stop_reason'],'timeout');self.assertNotEqual(r['exit_code'],0);self.assertTrue(r['exit_confirmed'])
            with self.assertRaises(ProcessLookupError):os.kill(r['pid'],0)
    def test_real_cancel_reaps_process(self):
        with tempfile.TemporaryDirectory() as work:
            cancel=threading.Event();timer=threading.Timer(.15,cancel.set);timer.start()
            r=ProcessRunner().run([sys.executable,'-c','import time; time.sleep(30)'],work,{'PATH':os.environ['PATH']},cancel,5)
            timer.join();self.assertEqual(r['stop_reason'],'cancelled');self.assertTrue(r['exit_confirmed'])
    def test_generation_timeout_is_failure_with_evidence(self):
        # Adapter deliberately returns a timeout record: no live invocation in this test.
        class TimeoutStub(Stub):
            def generate(self,*args):return None,{'name':'STUB timeout','exit_code':-15,'stop_reason':'timeout','exit_confirmed':True}
        with tempfile.TemporaryDirectory() as work:
            a=LiveHandoff(ROOT,work,live_enabled=True,adapter=TimeoutStub())
            try:
                d,_=a.create({'mode':'live','recipe':'todo-persistence-v1','objective':'Fix Todo persistence'},'timeout-create-01')
                for t in a.threads:t.join()
                d=a.get(d['id']);self.assertEqual(d['state'],'failed');self.assertEqual(d['checks'],[]);self.assertEqual(d['model_calls'][0]['stop_reason'],'timeout')
            finally:a.close()

class CliEventTests(unittest.TestCase):
    def test_known_startup_diagnostics_are_not_model_tools(self):
        events=[{'type':'thread.started'}, {'type':'item.completed','item':{'type':'error','message':'Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`.'}}, {'type':'turn.started'}, {'type':'item.completed','item':{'type':'agent_message','text':'{}'}}, {'type':'turn.completed'}]
        self.assertEqual(len(validate_cli_events('\n'.join(map(json.dumps,events)))),1)
    def test_tool_unknown_error_and_missing_completion_fail_closed(self):
        cases=[[{'type':'turn.started'},{'type':'item.completed','item':{'type':'command_execution'}},{'type':'turn.completed'}], [{'type':'item.completed','item':{'type':'error','message':'unknown error'}}], [{'type':'turn.started'}], [{'type':'turn.failed'}]]
        for events in cases:
            with self.assertRaises(RuntimeError):validate_cli_events('\n'.join(map(json.dumps,events)))
