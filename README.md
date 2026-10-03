# Ragnarok / Web Studio Handoff

Ragnarok 把一个明确的修复任务交给 Codex，再把可审阅的补丁、人的批准和真实测试结果串起来。本轮目标是修复 Todo 勾选状态刷新后丢失，并通过 Rinx 卡片在原生页面中查看结果。

## 当前版本

| 分支 | 提交 | 能力 |
|---|---|---|
| `live-codex-todo` | `9da2f90b882ef3e9831c642f78942c0f07bc2a67` | 固定 demo + 可选真实 Codex CLI 执行链 |
| `main` | `2c2b51ce8c7f1a8bfff667fb9dac9fbc525928ca` | 原固定补丁 demo |

本轮工作树正在补齐文档和干净复现材料，尚未产生新的冻结提交。[PROCESS.md](PROCESS.md) 记录阶段、时间和结果；[脱敏验收摘要](evidence/live-verification.json) 保留源码、补丁和源证据哈希。

## 已完成的流程

1. **生成候选。** Codex CLI 0.160.0 只接收任务、Todo 源码和源码哈希，以只读模式返回结构化源码；服务端生成 diff。
2. **审阅并批准。** 人工查看实际 diff，批准绑定候选字节、完整 fixture 基线、计划及 revision。
3. **应用并测试。** 只在该任务的独立副本修改 `fixture/store.mjs`。基线 9 通过 / 1 失败，应用后原测试 10 通过 / 0 失败，退出码依次为 `1、0、0、0`。
4. **保留结果。** 测试文件和原始 fixture 未改。相同批准重放返回相同结果，执行次数保持 1。
5. **在 Rinx 打开。** 2026-10-03 20:55 北京时间（12:55 UTC），同 Mac 的第二账号成功解密新卡，在原生 WKWebView 打开结果，勾选后刷新、返回聊天并重开，状态均保留。此次验收共两张卡，没有触发新的模型任务。

原生验收对应本分支 `9da2f90` 与 Rinx `c515e5fc9b6dc22e67f7d551b09fdd793ec685a1`。这组结果与 59 项后端／HTTP 测试、22 项离线卡片测试分别记录；新增测试中的 stub 用于故障分支，不替代真实模型调用。

## 启动与复现

需要已有 Python 3.9+、git、Node.js。固定 demo 支持 Node 20+；live 验证需要 Node 26+ 和已登录的 Codex CLI。核心代码无需 npm/pip 安装。

```sh
python3 --version
node --version
git --version
codex --version
codex login status

# 从公开固定提交建立独立目录；不要复制旧 var/ 或任务数据库
git clone --branch live-codex-todo https://github.com/JadeSnow7/Ragnarok.git Ragnarok-clean
cd Ragnarok-clean
git checkout --detach 9da2f90b882ef3e9831c642f78942c0f07bc2a67

python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test rinx-contract/card-contract.test.mjs
node --check web/app.js
python3 tests/run_demo.py
```

`tests/run_demo.py` 复现固定补丁审批链，使用自己的 `var/demo`。原始 bug 可通过下列命令观察：预期 9 通过、1 失败，退出码 1。

```sh
node --test --test-reporter=tap fixture/store.test.mjs
```

启动工作台时可选一个空闲 loopback 端口：

```sh
python3 app.py --enable-live --port 8766 --data-dir var/clean-live
```

在同一台 Mac 打开 `http://127.0.0.1:8766`。固定模式重放已知补丁；Live 模式调用现有 Codex 会话生成新候选。任务页显示实际模式、模型记录和目标执行次数。Health 中 `live_model=false` 表示默认模式，`live_available=true` 表示已允许 Live 创建。

也可不启动 HTTP，直接生成一次候选：

```sh
python3 tools/live_probe.py --data-dir var/clean-live --generate
# 审阅输出的真实 diff、task、revision 和 plan_digest，再取得对该候选的人工批准
python3 tools/live_probe.py --data-dir var/clean-live --approve TASK_ID --plan-digest REVIEWED_PLAN_SHA256 --revision REVIEWED_REVISION
```

新的候选单独批准，不沿用旧任务的决定。模型不会读取 `patches/` 或历史答案。固定测试使用 Node 权限模式限制候选代码；服务端还检查路径、基线哈希、文件范围及体积。生成限时 120 秒、固定命令限时 15 秒；取消显示为完成前会确认进程退出。

可选浏览器验收使用已经安装的 Playwright 与 Chrome，先启动服务，再运行：

```sh
HANDOFF_URL=http://127.0.0.1:8766 python3 tests/browser_smoke.py
```

## 验收记录

| 检查 | 已完成结果 |
|---|---|
| 后端／HTTP | 59 通过，含拒绝、重复批准、错误基线、越界、模型失败、超时与取消 |
| 离线卡片协议 | 22 通过 |
| 固定 HTTP demo | 8 条断言通过 |
| 浏览器 | 固定流程 12 项、真实候选审阅 7 项、已批准修复 9 项通过 |
| 真实模型执行 | 一次目标执行；基线失败、原测试修复后全部通过 |
| Rinx 同 Mac 双账号 | 新卡及原生页面 11 项检查通过，目标执行次数仍为 1 |

早期 exec 初始化曾受外层环境权限限制；正常临时许可解决后，适配器对两条启动诊断的误判修正并重试一次成功。旧的固定版本记录保留在 [历史摘要](evidence/verification-summary.json)，当前结果以 live 摘要及流程记录为准。详细身份日志与截图保存在仓库外，只在本地审阅。

## 本次干净复现

2026-10-03 21:36 北京时间（13:36 UTC），从 `9da2f90` 的新独立副本复跑 59 项后端／HTTP、22 项离线契约和 8 项固定 demo 断言，全部通过。没有复制旧 `var/` 或任务数据库；叠加的本地差异仅为文档、摘要和一处状态文案，完整补丁哈希见 [干净复现记录](evidence/clean-reproduction.json)。

随后一次新的真实 Codex 调用生成候选。2026-10-03 22:04 北京时间（14:04 UTC），用户对该新候选明确批准后，独立目标执行 1 次：基线 9 通过 / 1 失败，原测试修复后 10 通过 / 0 失败。相同批准重放返回完全相同的结果，未新增执行或模型调用；22:05 的浏览器 9 项检查确认刷新与关闭重开后勾选保留。它与上方首次执行及 Rinx 验收分别记录。演示脚本见 [DEMO.md](DEMO.md)，待冻结文件和校验命令见 [FREEZE.md](FREEZE.md)。

## 已知限制

- 原生验收只覆盖同一 Mac 的两个账号和一张成功的新卡。旧卡仍缺 room key，原因未确定；跨设备和其他加密问题尚未验证。
- 本轮只支持 Todo fixture。每个新候选需要独立批准，没有自动修复循环。
- 服务面向单一本机操作者；loopback 不提供跨设备访问，目录隔离和 Node 权限模式不是通用容器沙箱。
- 2 分 10.72 秒原生操作回顾视频及截图已完成本地检查；冻结提交、公开媒体发布、main 合并和公网部署尚未执行。

## 文件与许可证

`app.py` / `live_executor.py` 实现服务与执行链；`web/` 是工作台；`fixture/` 保留原 bug 和固定测试；`patches/` 是固定 demo；`evidence/` 只收纳脱敏摘要与干净补丁。本项目使用 [Apache License 2.0](LICENSE)，不包含 Rinx 源码。
