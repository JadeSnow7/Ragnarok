const $ = id => document.getElementById(id);
const states = {awaiting_approval:'待批准', running:'正在验证', passed:'验证通过', failed:'执行失败', rejected:'已拒绝', interrupted:'执行中断'};
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
  $('run-meta').textContent=`RUN ${data.id.slice(0,8)} · revision ${data.revision} · 实际执行 ${data.run_count} 次`;
  $('plan-hash').textContent='PLAN SHA-256 '+data.plan_digest;
  $('approval').hidden=data.state!=='awaiting_approval';
  $('step-approval').classList.add('active');$('step-proof').classList.toggle('active',data.state==='passed');
  const checks=$('check-list');checks.replaceChildren();
  const titles={baseline:'基线：复现刷新丢失', 'patch-check':'补丁：可干净应用', 'patch-apply':'改动：写入示例副本', verification:'回归：原测试全部通过'};
  for(const check of data.checks) {
    const expected=check.name==='baseline'&&check.exit_code===1;const success=check.exit_code===0;
    const row=make('div',undefined,'check '+(expected?'expected':success?'success':'error'));
    row.append(make('span',expected?'×':success?'✓':'!', 'check-icon'));
    const body=make('div');body.append(make('strong',titles[check.name]||check.name),make('small',check.argv.join(' ')));row.append(body,make('span',`exit ${check.exit_code}`,'exit'));
    const details=make('details');details.append(make('summary',`查看命令输出 · ${check.duration_ms} ms`),make('pre',check.stdout+check.stderr || '(no output)'));row.append(details);checks.append(row);
  }
  $('result').hidden=!['passed','failed','rejected','interrupted'].includes(data.state);
  $('result').className='result '+data.state;
  $('result').textContent=data.state==='passed'?'✓ 基线恰好一个测试失败；补丁应用后全部通过。测试文件没有被修改。':data.state==='rejected'?'已拒绝。未创建执行目录，未运行命令。':data.error||'执行中断。请检查记录，再创建新任务重试。';
  $('events').replaceChildren(...data.events.map(event=>{const li=make('li');li.append(make('time',new Date(event.at).toISOString()+' UTC'),make('span',event.message));return li;}));
  $('result-links').hidden=data.state!=='passed';$('preview-link').href=`/preview/${data.id}/index.html`;$('evidence-link').href=`/api/tasks/${data.id}/evidence`;
  document.title=`${states[data.state]} · Web Studio Handoff`;
  clearTimeout(timer);if(data.state==='running')timer=setTimeout(()=>poll(data.id),400);
}
async function poll(id) {
  const current=generation;
  try {const data=await api('/api/tasks/'+id);if(current===generation) {render(data);notice('');}}
  catch(error) {if(current===generation){notice('暂时无法获取结果。任务可能仍在运行；正在重连，请勿重复创建。');timer=setTimeout(()=>poll(id),2000);}}
}
async function loadPatch() {try {$('patch').textContent=(await api('/api/patch')).patch;}catch{$('patch').textContent='暂时无法获取补丁；请恢复连接后刷新。';}}
$('task-form').addEventListener('submit',async event=>{
  event.preventDefault();if(busy||event.isComposing)return;
  const objective=$('objective').value.trim();
  if(objective.length<5||objective.length>2000){$('objective-error').textContent='请填写 5–2000 字的任务描述';$('objective').setAttribute('aria-invalid','true');$('objective').focus();return;}
  const body={objective,recipe:'todo-persistence-v1'};const serialized=JSON.stringify(body);
  if(serialized!==createPayload){createPayload=serialized;createKey=randomKey();}
  setBusy(true);notice('正在创建审阅单…');generation++;clearTimeout(timer);
  try {const data=await api('/api/tasks',body,createKey);render(data);history.replaceState(null,'','/?task='+data.id);await loadPatch();notice('审阅单已创建。请核对补丁和范围，再批准执行。');createPayload=null;pendingDecision=null;}
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
