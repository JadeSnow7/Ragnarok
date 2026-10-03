"""Browser evidence for the local app. Requires an already installed Playwright + Chromium."""
import json
import os
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence'
OUT.mkdir(exist_ok=True)
URL=os.environ.get('HANDOFF_URL','http://127.0.0.1:8765').rstrip('/')
report={'browser':'Chromium','scenarios':[],'console_errors':[]}
def passed(name, detail=''):
    report['scenarios'].append({'name':name,'status':'passed','detail':detail})

with sync_playwright() as p:
    executable=os.environ.get('CHROMIUM_EXECUTABLE') or shutil.which('chromium') or shutil.which('google-chrome')
    mac_chrome=Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    if not executable and mac_chrome.exists(): executable=str(mac_chrome)
    browser=p.chromium.launch(executable_path=executable,headless=True)
    ctx=browser.new_context(viewport={'width':1440,'height':1100},device_scale_factor=1)
    page=ctx.new_page()
    page.on('pageerror',lambda e:report['console_errors'].append(str(e)))
    page.goto(URL)
    expect(page.locator('#empty')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(OUT/'01-empty-desktop.png'),full_page=True)
    passed('initial empty state and desktop layout')
    page.locator('#objective').fill('')
    page.locator('#create').click()
    expect(page.locator('#objective-error')).to_contain_text('5–2000')
    expect(page.locator('#objective')).to_be_focused()
    assert page.locator('#objective').get_attribute('aria-invalid')=='true'
    passed('empty input accessible validation and focus')
    page.locator('#objective').fill('修复待办事项勾选状态刷新后丢失，并用原回归测试验证。')
    page.locator('#create').click()
    expect(page.locator('#status')).to_have_text('待批准')
    task_id=page.url.split('task=')[1]
    data=page.request.get(URL+'/api/tasks/'+task_id).json()
    assert data['run_count']==0 and data['checks']==[]
    passed('creation requires explicit approval; no command before approval')
    page.locator('#patch-details').click()
    page.screenshot(path=str(OUT/'02-approval-desktop.png'),full_page=True)
    page.locator('#approve').click()
    expect(page.locator('#status')).to_have_text('验证通过',timeout=15000)
    data=page.request.get(URL+'/api/tasks/'+task_id).json()
    assert data['run_count']==1
    assert [c['exit_code'] for c in data['checks']]==[1,0,0,0]
    assert '# pass 10' in data['checks'][-1]['stdout']
    assert '# fail 1' in data['checks'][0]['stdout']
    (OUT/'successful-task.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    page.locator('#patch-details').click()
    page.screenshot(path=str(OUT/'03-passed-desktop.png'),full_page=True)
    passed('real baseline failure → approved patch → passing regression',task_id)
    page.reload()
    expect(page.locator('#status')).to_have_text('验证通过')
    assert page.request.get(URL+'/api/tasks/'+task_id).json()['run_count']==1
    passed('task survives browser reload without rerun')
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(OUT/'04-passed-mobile.png'),full_page=True)
    passed('390px narrow layout has no horizontal overflow')
    page.emulate_media(reduced_motion='reduce')
    assert page.locator('#create').evaluate("el => getComputedStyle(el).transitionDuration")=='0s'
    page.keyboard.press('Tab')
    assert page.evaluate('document.activeElement !== document.body')
    passed('reduced motion and keyboard focus')
    baseline=ctx.new_page()
    baseline.goto(URL+'/fixture/index.html')
    baseline.evaluate('localStorage.clear()')
    baseline.reload()
    baseline.get_by_role('textbox',name='New task').fill('Reload proof')
    baseline.get_by_role('button',name='Add task').click()
    baseline.get_by_role('checkbox').check()
    baseline.reload()
    expect(baseline.get_by_role('checkbox')).not_to_be_checked()
    baseline.screenshot(path=str(OUT/'05-baseline-after-reload.png'),full_page=True)
    passed('real browser baseline reproduces checkbox state loss')
    fixed=ctx.new_page()
    fixed.goto(URL+f'/preview/{task_id}/index.html')
    fixed.evaluate('localStorage.clear()')
    fixed.reload()
    fixed.get_by_role('textbox',name='New task').fill('Reload proof')
    fixed.get_by_role('button',name='Add task').click()
    fixed.get_by_role('checkbox').check()
    fixed.reload()
    expect(fixed.get_by_role('checkbox')).to_be_checked()
    fixed.screenshot(path=str(OUT/'06-fixed-after-reload.png'),full_page=True)
    passed('real browser patched checkbox survives page reload')
    page.goto(URL)
    page.locator('#create').click()
    expect(page.locator('#status')).to_have_text('待批准')
    rejected_id=page.url.split('task=')[1]
    page.locator('#reject').click()
    expect(page.locator('#status')).to_have_text('已拒绝')
    rejected=page.request.get(URL+'/api/tasks/'+rejected_id).json()
    assert rejected['run_count']==0 and rejected['checks']==[]
    page.screenshot(path=str(OUT/'07-rejected-mobile.png'),full_page=True)
    passed('rejection UI and zero execution',rejected_id)
    page.goto(URL)
    page.route('**/api/tasks',lambda route:route.abort())
    page.locator('#create').click()
    expect(page.locator('#notice')).to_contain_text('创建未确认')
    assert not page.locator('#create').is_disabled()
    page.unroute('**/api/tasks')
    page.locator('#create').click()
    expect(page.locator('#status')).to_have_text('待批准')
    passed('network failure retains input and supports safe idempotent retry')
    page.locator('#reject').click()
    expect(page.locator('#status')).to_have_text('已拒绝')
    assert not report['console_errors'],report['console_errors']
    passed('no browser JavaScript errors')
    report['passed']=len(report['scenarios'])
    report['failed']=0
    (OUT/'browser-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    browser.close()
print(json.dumps(report,ensure_ascii=False,indent=2))
