#!/usr/bin/env python3
"""Run a real end-to-end HTTP proof and save machine-readable evidence."""
import json
from pathlib import Path
import sys
import threading
import time
import urllib.request
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import make_server
ROOT=Path(__file__).resolve().parents[1]
server=make_server(0,data_dir=ROOT/'var/demo')
thread=threading.Thread(target=server.serve_forever,daemon=True)
thread.start()
BASE=f'http://127.0.0.1:{server.server_address[1]}'
def request(path,body=None,key=None):
    encoded=json.dumps(body).encode() if body is not None else None
    headers={'Content-Type':'application/json'}
    if key:headers['Idempotency-Key']=key
    req=urllib.request.Request(BASE+path,data=encoded,headers=headers)
    with urllib.request.urlopen(req,timeout=10) as response:
        return response.status,json.load(response)
try:
    _,health=request('/api/health')
    key=uuid.uuid4().hex
    status,task=request('/api/tasks',{'objective':'修复待办事项勾选状态在刷新后丢失的问题，并保留可核验的测试证据。','recipe':'todo-persistence-v1'},key)
    assert status==201 and task['state']=='awaiting_approval' and task['run_count']==0
    _,again=request('/api/tasks',{'objective':'修复待办事项勾选状态在刷新后丢失的问题，并保留可核验的测试证据。','recipe':'todo-persistence-v1'},key)
    assert again['id']==task['id']
    decision={'decision':'approve','revision':task['revision'],'plan_digest':task['plan_digest']}
    decision_key=uuid.uuid4().hex
    request('/api/tasks/'+task['id']+'/decision',decision,decision_key)
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        _,done=request('/api/tasks/'+task['id'])
        if done['state']!='running':break
        time.sleep(.05)
    assert done['state']=='passed',done
    assert [c['exit_code'] for c in done['checks']]==[1,0,0,0]
    assert done['run_count']==1
    _,replay=request('/api/tasks/'+task['id']+'/decision',decision,decision_key)
    assert replay['run_count']==1 and replay['state']=='passed'
    _,rejected=request('/api/tasks',{'objective':'拒绝此示例任务，验证不执行命令。','recipe':'todo-persistence-v1'},uuid.uuid4().hex)
    _,rejected=request('/api/tasks/'+rejected['id']+'/decision',{'decision':'reject','revision':rejected['revision'],'plan_digest':rejected['plan_digest']},uuid.uuid4().hex)
    assert rejected['state']=='rejected' and rejected['run_count']==0 and not rejected['checks']
    assert not (ROOT/'var/demo/runs'/rejected['id']).exists()
    out=ROOT/'evidence';out.mkdir(exist_ok=True)
    (out/'successful-task.json').write_text(json.dumps(done,ensure_ascii=False,indent=2))
    (out/'rejected-task.json').write_text(json.dumps(rejected,ensure_ascii=False,indent=2))
    for check in done['checks']:
        (out/(check['name']+'.log')).write_text('$ '+' '.join(check['argv'])+'\nexit_code='+str(check['exit_code'])+'\n'+check['stdout']+check['stderr'])
    report={'status':'passed','health':health,'task_id':done['id'],'run_count':done['run_count'],'checks':[{'name':c['name'],'exit_code':c['exit_code']} for c in done['checks']],
            'assertions':['HTTP health','create waits for approval','create idempotency','real expected baseline failure','real approved patch application','unchanged regression suite passes','decision idempotency prevents rerun','reject causes no execution or workspace'],
            'browser_verification':'not run in this script'}
    (out/'http-demo-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
finally:
    server.shutdown();server.server_close();server.app.close()
