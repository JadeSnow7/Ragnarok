# Ragnarok / Web Studio Handoff

> **初赛评审入口（2026-10-04）**：请查看 [`live-codex-todo` 分支](https://github.com/JadeSnow7/Ragnarok/tree/live-codex-todo)、固定提交 [`787ee3b4d5069ab64aefe9104966117e2f01cb3d`](https://github.com/JadeSnow7/Ragnarok/tree/787ee3b4d5069ab64aefe9104966117e2f01cb3d) 和 [初赛 Release（演示视频、截图及评委复现须知）](https://github.com/JadeSnow7/Ragnarok/releases/tag/demo-live-codex-2026-10-03)。初赛版本包含受人工批准约束的 Codex CLI 候选生成与验证流程；本页下文保留 main 原固定补丁 demo 的说明。

Ragnarok 是用于 GOSIM 的本地 Web Studio Handoff 原型，证明审批→应用预生成补丁→真实回归→证据留存的有限闭环。它不是实时自主编程 agent。

## 已跑通的部分

- Web UI：任务描述、固定范围审阅、补丁预览、批准/拒绝、执行证据与结果入口
- Python HTTP 服务、SQLite 任务与决定持久化、重复请求防重、修订号与计划指纹校验
- 每个任务新建独立 Todo 示例副本，先复现失败，再应用补丁，最后运行原测试
- 真实结果：基线 9 通过 / 1 失败；补丁后 10 通过 / 0 失败；原测试文件保持一致
- 拒绝不创建执行目录或执行命令；重复批准不会再次运行；执行异常保留失败状态和日志
- Rinx 消息卡片的 source-informed 离线协议检查，见 rinx-contract/；它不是原生宿主集成测试

重要：本原型使用 coding assistant 在本次工作中编写的预生成补丁。运行时是受审批的固定补丁重放，不包含“收到任意任务后自主调用模型并生成代码”的执行器，也没有自动修复重试循环；`/api/health` 中 `live_model` 为 `false`。任务文本用于记录目标，不会被解释成 shell 命令。本轮只支持一个明确示例：Todo 勾选状态刷新后丢失。

## 快速启动（Mac / Linux）

需要已有 Python 3.10+、Node.js 20+、git。应用与核心测试没有额外依赖，不需要 npm install、API key 或账户。

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

浏览器脚本包含审批、拒绝、网络失败重试、页面刷新、移动宽度、键盘与截图检查。已有 Mac 浏览器验收通过手动 CUA 操作完成，没有运行此 Playwright 脚本；不能将手动验收视为该脚本全部通过。

## 已有验证及时间边界

公开摘要见 [evidence/verification-summary.json](evidence/verification-summary.json)。它分别记录历史报告和本次发布前检查，不包含原始截图、任务标识、账号信息或本机路径。历史浏览器和原生观察没有在本次发布时重跑。

- 2026-10-03 发布前检查：39 项后端／HTTP 回归、22 项离线卡片检查和 8 项 HTTP 演示断言通过，JavaScript 语法检查通过。Mac 临时路径别名曾使一项故障注入未触发；测试目录规范化后完整回归通过，注入和断言保持不变。
- 早期云端报告：39 项后端／HTTP 检查、22 项 Rinx 离线卡片协议检查、8 项 HTTP 演示断言通过。当时云端浏览器受 socket／loopback 限制而阻塞；这是历史环境限制。
- 2026-10-02 07:03 UTC（北京时间 15:03）：Mac Microsoft Edge 的手动 CUA 验收记录 11 项通过，包括审批前零执行、重复批准仅执行一次、拒绝零执行、基线 9 通过／1 失败、原测试不变且修复后 10 通过、页面刷新验证及输出可见。未覆盖移动宽度、网络失败重试和完整键盘无障碍。
- 2026-10-02：固定版本 Rinx 在 Mac 原生构建成功；11:00 UTC（北京时间 19:00）的观察确认登录成功。WKWebView 内嵌预览和真实 Matrix 卡片收发仍未验证，离线协议检查不能替代原生端到端验证。
- 上述浏览器验收之后，源码修改了链接在当前页面打开的行为及相关说明；发布副本还更正了验证边界文字。当前页面修改没有重新进行浏览器或 Rinx UI 验收。

尚无公网应用部署、演示视频或作品验收结果；发布源码仓库不代表这些项目已完成。

## 审批与执行语义

- 状态：awaiting_approval → running → passed/failed；或者 awaiting_approval → rejected
- 进程重启时，遗留 running 变为 interrupted，不自动重放
- 每次 create/decision 都需要 Idempotency-Key；同 key 同请求返回原任务，同 key 不同请求返回 409
- 审批包含 revision 和 plan_digest；过期审阅返回 409
- 计划包含源文件清单、补丁 SHA-256、允许修改的文件、精确命令
- 执行前校验源与补丁，使用已经校验的字节写入副本；拒绝补丁越界、文件新增/删除和测试改动
- 子进程超时为 15 秒，使用固定参数 argv，不执行用户 shell 字符串
- 证据包含真实 stdout、stderr、exit code、UTC 时间和耗时
- 每个任务目录位于 var/runs/<id>，本机持久化数据库位于 var/tasks.sqlite3
- tests/run_demo.py 使用单独的 var/demo，不修改正常 UI 任务数据库

## 安全边界与未实现部分

本原型只能用于可信示例代码。目录隔离不是容器或操作系统安全沙箱。子进程仍拥有服务账户的文件与网络权限；当前固定示例不会使用网络。不要用它执行不可信仓库，不要监听公网或通过代理暴露它。

它没有用户身份认证、多租户隔离、资源队列、任务取消、恶意代码隔离、分布式锁或跨进程单实例锁；仅设计为单服务进程运行。JSON + Origin/Host 检查是 loopback 辅助防护，不是远程授权方案。审阅人身份与审计防篡改未实现。

未实现：实时模型/API 或 coding CLI 适配器、自动修复循环、任意软件修复能力。未验证：macOS/iOS WKWebView 内嵌与真实 Matrix 卡片收发。原生构建和登录已有上述历史观察；没有调用模型 API、修改用户原项目或公开部署应用。

Rinx 卡片仅包含普通 HTTP(S) URL。没有聊天历史、Matrix token 或 JavaScript 原生能力桥。卡片中使用 cloud localhost 地址不会使用户 Mac 能访问它。只有把此包运行在 Mac 本机，才能用 Mac 的 localhost 做同机试验。

## 结构

- app.py：标准库 HTTP 服务、持久化审批、固定 runner
- web/：原生 HTML/CSS/JS 工作台
- fixture/：带已知 bug 的独立 Todo 示例和 10 个回归测试
- patches/：预生成单文件补丁与来源说明
- tests/：核心、HTTP 演示与可选浏览器测试
- evidence/：整理后的历史和发布前验证摘要；本地运行测试可生成新的日志和结果
- rinx-contract/：固定版本 Rinx 的 source-informed 消息契约检查
- DESIGN.md / UX-CONTRACT.md：设计与交互契约

## 许可证

本仓库使用 [Apache License 2.0](LICENSE)。Rinx 是独立上游项目，本仓库不包含其源码或原生构建产物。
