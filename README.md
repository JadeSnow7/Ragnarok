# Ragnarok / Web Studio Handoff

Ragnarok 是用于 GOSIM 的本地 Web Studio Handoff 原型，保留审批→固定补丁→真实回归的可复现路径，并新增可选 Codex CLI 候选生成链。范围仅限 Todo 刷新丢失问题。

## 已跑通的部分

- Web UI：任务描述、固定范围审阅、补丁预览、批准/拒绝、执行证据与结果入口
- Python HTTP 服务、SQLite 任务与决定持久化、重复请求防重、修订号与计划指纹校验
- 每个任务新建独立 Todo 示例副本，先复现失败，再应用补丁，最后运行原测试
- 真实结果：基线 9 通过 / 1 失败；补丁后 10 通过 / 0 失败；原测试文件保持一致
- 拒绝不创建目标执行目录或运行目标命令；Live 的先前模型调用仍保留记录。重复批准不会再次运行；执行异常保留失败状态和日志
- Rinx 消息卡片的 source-informed 离线协议检查，见 rinx-contract/；它不是原生宿主集成测试

当前默认是 **fixed**：预生成补丁回放，无模型调用。显式 `--enable-live` 后才允许 **live**：使用现有 Codex CLI 登录，发送任务描述和 `fixture/store.mjs`，返回结构化完整源码，由服务端生成 diff。模型不会收到 `patches/`、期望实现或测试答案。`/api/health.live_model=false` 表示默认模式；`live_available` 表示配置允许尝试，**不表示真实模型已验证成功**。任务中的 `mode/live_model` 标记所选路径，是否完成调用必须检查 `model_calls` 和候选状态。

**真实验证**：2026-10-03，使用 Mac Codex CLI 0.160.0 完成 **真实模型→候选→人工批准→应用→固定回归** 闭环，目标执行恰好 1 次。基线 9 通过 / 1 失败，应用后原测试 10 通过 / 0 失败；实际 diff 与批准候选一致，原始 fixture 和测试文件未修改。执行环境最初限制 app-server 初始化；正常临时执行许可解决后，适配器对两条启动诊断的误判经过修正，再做一次真实重试成功。没有更改登录、持久权限或关闭 Codex 只读沙箱。见 [脱敏验证摘要](evidence/live-verification.json) 和 [真实候选补丁](evidence/live-candidate.patch)。摘要明确区分真实模型结果与 stub 测试，不公开原始模型日志、任务标识、账号信息、本机路径或截图。

最新本地复验：59 项完整测试（含 20 项明确标记的 stub/进程/解析器测试）、22 项离线契约、8 项固定 HTTP demo 断言、12 项固定浏览器场景通过；真实候选的审阅页面另有 7 项检查通过，包括 390px 无溢出和零目标执行。浏览器为现有 Google Chrome；不代表 Rinx 内嵌验证。最终真实候选浏览器验收另有 9 项通过，直接确认原版勾选刷新丢失、修复版勾选及取消勾选均跨刷新保留。相同批准请求重放返回完全相同结果，执行次数仍为 1。

## 快速启动（Mac / Linux）

固定路径需要已有 Python 3.9+、Node.js 20+、git。Live 验证要求 Node.js 26+（禁网络的权限模式）及已安装、已登录的 Codex CLI；本次读取版本为 0.160.0。应用无需 npm/pip 安装，不自动安装或登录。

```sh
cd Ragnarok
python3 app.py --port 8765
```

在运行它的同一台机器打开 http://127.0.0.1:8765 。这是 loopback 地址，不能让其他设备打开，也不是公网部署地址。

1. 查看或编辑默认任务描述，点击「生成审阅单」
2. 展开补丁，审阅目标文件和固定命令
3. 点击「批准并验证」，等待真实命令完成
4. 展开输出，检查基线 exit 1 和最终验证 exit 0
5. 打开修复后示例，添加待办、勾选、立即刷新，检查状态
6. 新建另一审阅单并拒绝，检查实际执行次数为 0

原始问题示例 /fixture/index.html 始终保留 bug，修复只发生在任务副本中。浏览器存储按示例 URL 加前缀：原始示例与每个任务预览互不覆盖，刷新同一个 URL 时保留自己的状态。

## Live 候选与人工批准

```sh
python3 app.py --enable-live --port 8765
# 或无需 HTTP 的一次候选探测：只生成、展示，不自动应用
python3 tools/live_probe.py --generate
```

Live 创建会发起一次模型请求（使用现有账户额度），随后停在 `awaiting_approval`。查看真实 diff、`candidate_id`、`base_sha256`、`plan_digest`、revision 和命令，再通过 UI 批准。CLI 方式必须由人审阅后显式提供：

```sh
python3 tools/live_probe.py --approve TASK_ID --plan-digest REVIEWED_PLAN_SHA256 --revision REVIEWED_REVISION
```

同一审批重复提交只执行一次。失败重试必须创建新任务、产生新候选并重新审阅，不复用旧批准。此工具不自动重试修复。已完成的真实验证在审阅 revision 2 时取得明确人工批准，最终状态 passed；重复批准没有新增命令。每次本地运行的详细模型、候选、决定与进程证据保存在 `var/`，不随仓库发布。任何新候选仍需独立人工批准。

## 可重复验证

```sh
# HTTP 端到端执行；运行后生成 evidence/*.json 与 *.log（未随仓库发布）
python3 tests/run_demo.py

# 审批、拒绝、防重、并发、错误、重启、HTTP 防护等测试
python3 -m unittest discover -s tests -p 'test_*.py' -v

# 语法
python3 -m py_compile app.py
node --check web/app.js

# 原始基线应失败：恰好 1 个测试失败，exit code 1 属于预期
node --test --test-reporter=tap fixture/store.test.mjs

# Rinx 离线卡片协议检查
node --test rinx-contract/card-contract.test.mjs
```

可选浏览器脚本：仅在已经有 Playwright 与 Chromium/Chrome 的环境中使用。它不自动安装依赖。

```sh
# 另一个终端先启动 app.py
python3 tests/browser_smoke.py
# 可选：HANDOFF_URL=http://127.0.0.1:8765
# 可选：CHROMIUM_EXECUTABLE=/path/to/chrome
```

浏览器脚本包含审批、拒绝、网络失败重试、页面刷新、移动宽度、键盘与截图检查。本次已使用现有 Google Chrome 运行此脚本，12 项场景通过；下方历史 Mac 手动 CUA 验收是另一组记录。

## 已有验证及时间边界

公开摘要见 [evidence/verification-summary.json](evidence/verification-summary.json)。它分别记录历史报告和本次发布前检查，不包含原始截图、任务标识、账号信息或本机路径。该文件保留固定版本发布时的历史观察；本分支新增真实模型与浏览器验证见上方独立 live 摘要。

- 2026-10-03 固定版本首次发布前检查：39 项后端／HTTP 回归、22 项离线卡片检查和 8 项 HTTP 演示断言通过，JavaScript 语法检查通过。Mac 临时路径别名曾使一项故障注入未触发；测试目录规范化后完整回归通过，注入和断言保持不变。
- 早期云端报告：39 项后端／HTTP 检查、22 项 Rinx 离线卡片协议检查、8 项 HTTP 演示断言通过。当时云端浏览器受 socket／loopback 限制而阻塞；这是历史环境限制。
- 2026-10-02 07:03 UTC（北京时间 15:03）：Mac Microsoft Edge 的手动 CUA 验收记录 11 项通过，包括审批前零执行、重复批准仅执行一次、拒绝零执行、基线 9 通过／1 失败、原测试不变且修复后 10 通过、页面刷新验证及输出可见。未覆盖移动宽度、网络失败重试和完整键盘无障碍。
- 2026-10-02：固定版本 Rinx 在 Mac 原生构建成功；11:00 UTC（北京时间 19:00）的观察确认登录成功。WKWebView 内嵌预览和真实 Matrix 卡片收发仍未验证，离线协议检查不能替代原生端到端验证。
- 上述浏览器验收之后，源码修改了链接在当前页面打开的行为及相关说明；发布副本还更正了验证边界文字。这是固定版本首次发布时的边界；本分支浏览器已复验，Rinx UI 仍未复验。

尚无公网应用部署、演示视频或作品验收结果；发布源码仓库不代表这些项目已完成。

## 审批与执行语义

- Fixed：awaiting_approval → running → passed/failed；Live：generating → awaiting_approval → running → passed/failed；拒绝为 rejected
- 服务重启时遗留活动状态变为 unknown，锁住执行槽，不自动重放；人工核查旧进程后使用新数据目录。旧 Handoff 测试类保留历史 interrupted 行为
- 每次 create/decision 都需要 Idempotency-Key；同 key 同请求返回原任务，同 key 不同请求返回 409
- 审批包含 revision 和 plan_digest；过期审阅返回 409
- 计划包含源文件清单、补丁 SHA-256、允许修改的文件、精确命令
- 执行前校验源与补丁，使用已经校验的字节写入副本；拒绝补丁越界、文件新增/删除和测试改动
- 模型限时 120 秒，固定命令限时 15 秒；取消先显示 cancelling，进程回收且进程组清理确认后才显示 cancelled。无法确认则 unknown。固定 argv，不执行模型/用户 shell 字符串
- 证据包含真实 stdout、stderr、exit code、UTC 时间和耗时
- 候选资料位于 var/candidates/<id>；批准后执行目录位于 var/runs/<id>，数据库位于 var/tasks.sqlite3。模型记录与目标 checks 分开；拒绝为零目标执行，之前的模型调用仍计入记录
- tests/run_demo.py 使用单独的 var/demo，不修改正常 UI 任务数据库

## 安全边界与未实现部分

仅适用于本机、单一受信操作人的 Todo fixture。Live CLI 使用只读沙箱、临时会话、结构化输出，并在本次调用禁用 shell、exec、插件、浏览器和多 agent 等能力；跳过用户配置及项目指令，不改变持久设置。本次两次真实调用均收到模型响应，成功候选调用只出现模型消息与已核实的启动诊断，没有工具执行事件；未知错误或工具事件仍阻断候选。

批准绑定完整 fixture 清单与源码哈希、候选 patch 哈希、命令及 revision。仅允许修改 `fixture/store.mjs`，源码最大 32 KiB，patch 最大 16 KiB；不改测试。Live 固定 Node 测试只读当前执行副本，禁文件写入、网络、子进程；已用恶意子进程调用 stub 验证拒绝。Node 权限与目录隔离不是容器级安全边界，不应推广为任意不可信代码执行平台。固定历史路径仍只运行仓库中可信代码。

同一数据目录用文件锁防止双服务实例，服务内模型生成与目标执行共用一个槽；不同数据目录不共享全局锁。重启后 unknown 不代表进程已退出。没有远程身份认证、多租户隔离或审计防篡改；本机审批端点视为人的决定，不验证现实身份。Origin/Host 防护不能代替远程认证。

未实现自动修复循环或任意软件修复能力。本机真实模型应用/回归与浏览器刷新闭环已完成；Rinx 内嵌、Matrix 卡片收发仍未验证。原项目、原 prototype、WebStudio/Rein 均未修改；本分支发布源码与脱敏摘要，不包含公网应用部署或任何 Rinx／Matrix 验证结论。

Rinx 卡片仅包含普通 HTTP(S) URL。没有聊天历史、Matrix token 或 JavaScript 原生能力桥。卡片中使用 cloud localhost 地址不会使用户 Mac 能访问它。只有把此包运行在 Mac 本机，才能用 Mac 的 localhost 做同机试验。

## 结构

- app.py：标准库 HTTP 服务、持久化审批、固定 runner
- live_executor.py：受限 Codex CLI、候选验证、审批绑定、进程生命周期
- tools/live_probe.py：单次真实候选生成及显式哈希审批入口
- web/：原生 HTML/CSS/JS 工作台
- fixture/：带已知 bug 的独立 Todo 示例和 10 个回归测试
- patches/：预生成单文件补丁与来源说明
- tests/：核心、HTTP 演示与可选浏览器测试
- evidence/：整理后的历史和发布前验证摘要；本地运行测试可生成新的日志和结果
- rinx-contract/：固定版本 Rinx 的 source-informed 消息契约检查
- DESIGN.md / UX-CONTRACT.md：设计与交互契约

## 许可证

本仓库使用 [Apache License 2.0](LICENSE)。Rinx 是独立上游项目，本仓库不包含其源码或原生构建产物。
