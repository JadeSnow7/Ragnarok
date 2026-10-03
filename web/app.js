const $ = id => document.getElementById(id);
const states = {generating:'模型生成中', cancelling:'正在停止', cancelled:'已停止', unknown:'退出状态未知', awaiting_approval:'待批准', running:'正在验证', passed:'验证通过', failed:'执行失败', rejected:'已拒绝', interrupted:'执行中断'};
let task = null, timer = null, busy = false;
let createKey = null, createPayload = null, pendingDecision = null;
let generation = 0;
const randomKey = () => crypto.randomUUID();
const defaultTask = $('objective').value;
try { $('objective').value = sessionStorage.getItem('handoff-draft') || defaultTask; } catch {}
$('objective').addEventListener('input', () => {try {sessionStorage.setItem('handoff-draft',$('objective').value);} catch {} $('objective').removeAttribute('aria-invalid'); $('objective-error').textContent='';});
function notice(message) {$('notice').textContent=message;}
function setBusy(value) {busy=value; $('create').disabled=value; for(const id of ['approve','reject']) $(id).disabled=value || task?.state!=='awaiting_approval';}
async function api(path, body, key) {
  const controller=new AbortController(); const timeout=setTimeout(()=>controller.abort(),12000);
  try {
    const options={signal:controller.signal,headers:{}};
    if(body) {options.method='POST';options.headers={'Content-Type':'application/json','Idempotency-Key':key};options.body=JSON.stringify(body);}
    const response=await fetch(path,options); const data=await response.json();
    if(!response.ok) {const error=new Error(data.error?.message || `HTTP ${response.status}`);error.code=data.error?.code;throw error;}
    return data;
  } finally {clearTimeout(timeout);}
}
const make=(tag,text,className)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;};
function render(data) {
  task=data; setBusy(busy); $('empty').hidden=true;$('task-content').hidden=false;
  $('status').textContent=states[data.state]||data.state;$('status').className='status-pill '+data.state;
  $('run-title').textContent=data.state==='passed'?'修复成立，证据已保留':data.state==='awaiting_approval'?'先审阅，再执行':'执行结果';
  $('run-meta').textContent=`${data.mode==='live'?'LIVE · Codex CLI':'FIXED · 固定补丁'} · RUN ${data.id.slice(0,8)} · revision ${data.revision} · 实际执行 ${data.run_count} 次`;
  $('plan-hash').textContent='PLAN SHA-256 '+(data.plan_digest||'候选生成后提供')+' · BASE '+(data.plan.base_sha256||'见完整证据');
  $('patch').textContent=data.candidate_patch||'候选生成中，尚无可批准补丁。';
  $('cancel').hidden=!['generating','running','cancelling'].includes(data.state);
  $('cancel').disabled=data.state==='cancelling';
  $('model-evidence').textContent=data.mode==='live'?`真实 CLI 调用记录：${data.model_calls?.length||0} · 目标执行 ${data.run_count} 次`:'固定补丁回放：没有模型调用';
  $('test-command').textContent=data.plan.commands[0];
  $('approval').hidden=data.state!=='awaiting_approval';
  $('step-approval').classList.add('active');$('step-proof').classList.toggle('active',data.state==='passed');
  const checks=$('check-list');checks.replaceChildren();
  const titles={baseline:'基线：复现刷新丢失', 'patch-check':'补丁：可干净应用', 'patch-apply':'改动：写入示例副本', verification:'回归：原测试全部通过'};
  for(const check of [...(data.model_calls||[]),...data.checks]) {
    const expected=check.name==='baseline'&&check.exit_code===1;const success=check.exit_code===0;
    const row=make('div',undefined,'check '+(expected?'expected':success?'success':'error'));
    row.append(make('span',expected?'×':success?'✓':'!', 'check-icon'));
    const body=make('div');body.append(make('strong',titles[check.name]||check.name),make('small',check.argv.join(' ')));row.append(body,make('span',`exit ${check.exit_code}`,'exit'));
    const details=make('details');details.append(make('summary',`查看命令输出 · ${check.duration_ms} ms`),make('pre',check.stdout+check.stderr || '(no output)'));row.append(details);checks.append(row);
  }
  $('result').hidden=!['passed','failed','rejected','interrupted','cancelled','unknown'].includes(data.state);
  $('result').className='result '+data.state;
  $('result').textContent=data.state==='passed'?'✓ 基线恰好一个测试失败；补丁应用后全部通过。测试文件没有被修改。':data.state==='rejected'?'已拒绝。目标应用与测试未执行；先前候选生成记录保留。':data.state==='cancelled'?'已确认子进程退出。检查证据中的已执行步骤。':data.state==='unknown'?'无法确认先前进程退出，执行槽已锁定。请人工检查本地进程与证据。':data.error||'执行中断。请检查记录，再创建新任务重试。';
  $('events').replaceChildren(...data.events.map(event=>{const li=make('li');li.append(make('time',new Date(event.at).toISOString()+' UTC'),make('span',event.message));return li;}));
  $('result-links').hidden=data.state!=='passed';$('preview-link').href=`/preview/${data.id}/index.html`;$('evidence-link').href=`/api/tasks/${data.id}/evidence`;
  document.title=`${states[data.state]} · Web Studio Handoff`;
  clearTimeout(timer);if(['running','generating','cancelling'].includes(data.state))timer=setTimeout(()=>poll(data.id),400);
}
async function poll(id) {
  const current=generation;
  try {const data=await api('/api/tasks/'+id);if(current===generation) {render(data);notice('');}}
  catch(error) {if(current===generation){notice('暂时无法获取结果。任务可能仍在运行；正在重连，请勿重复创建。');timer=setTimeout(()=>poll(id),2000);}}
}
async function loadPatch() {if(task?.candidate_patch||task?.mode==='live')return;try {$('patch').textContent=(await api('/api/patch')).patch;}catch{$('patch').textContent='暂时无法获取补丁；请恢复连接后刷新。';}}
$('task-form').addEventListener('submit',async event=>{
  event.preventDefault();if(busy||event.isComposing)return;
  const objective=$('objective').value.trim();
  if(objective.length<5||objective.length>2000){$('objective-error').textContent='请填写 5–2000 字的任务描述';$('objective').setAttribute('aria-invalid','true');$('objective').focus();return;}
  const body={objective,recipe:'todo-persistence-v1',mode:document.querySelector('input[name=mode]:checked').value};const serialized=JSON.stringify(body);
  if(serialized!==createPayload){createPayload=serialized;createKey=randomKey();}
  setBusy(true);notice('正在创建审阅单…');generation++;clearTimeout(timer);
  try {const data=await api('/api/tasks',body,createKey);render(data);history.replaceState(null,'','/?task='+data.id);await loadPatch();notice(data.state==='generating'?'正在调用 Codex 生成候选；生成后请审阅批准。':'审阅单已创建。请核对补丁和范围，再批准执行。');createPayload=null;pendingDecision=null;}
  catch(error){notice(`创建未确认：${error.message}。再次点击会使用相同请求编号，避免重复创建。`);}
  finally{setBusy(false);}
});
async function decide(decision) {
  if(!task||busy)return;
  if(pendingDecision && pendingDecision.decision!==decision){notice('上一次决定的结果尚未确认。请刷新任务状态后再操作。');return;}
  pendingDecision ||= {decision,key:randomKey(),body:{decision,revision:task.revision,plan_digest:task.plan_digest}};
  setBusy(true);notice(decision==='approve'?'正在提交批准…':'正在提交拒绝…');
  try {const data=await api(`/api/tasks/${task.id}/decision`,pendingDecision.body,pendingDecision.key);render(data);pendingDecision=null;notice('');}
  catch(error){notice(`决定未确认：${error.message}。请重试同一操作或刷新查看状态。`);}
  finally {setBusy(false);}
}
$('approve').addEventListener('click',()=>decide('approve'));$('reject').addEventListener('click',()=>decide('reject'));
const id=new URL(location.href).searchParams.get('task');
if(id){setBusy(true);notice('正在恢复任务…');try {render(await api('/api/tasks/'+encodeURIComponent(id)));await loadPatch();notice('');}catch(error){notice(`无法恢复此任务：${error.message}。可以创建新审阅单。`);}finally{setBusy(false);}}

$('cancel').addEventListener('click',async()=>{if(!task)return;try{render(await api(`/api/tasks/${task.id}/cancel`,{},randomKey()));}catch(error){notice('取消尚未确认；任务可能仍运行。'+error.message);}});
try{const health=await api('/api/health');$('live-mode').disabled=!health.live_available;$('mode-help').textContent=health.live_available?'Live 已启用，创建任务会调用现有 Codex 会话。':'Live 未启用。启动时使用 --enable-live；固定模式仍可使用。';}catch{$('mode-help').textContent='无法确认服务状态，Live 暂不可选。';}
