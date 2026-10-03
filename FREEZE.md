# 冻结准备（未提交）

基线：`live-codex-todo@9da2f90b882ef3e9831c642f78942c0f07bc2a67`。`main` 保持 `2c2b51c`。本轮只统一验收文档、流程和一处界面状态文案，未改执行逻辑、fixture 或测试。

## 拟纳入文件

| 文件 | 变化 |
|---|---|
| `.gitignore` | 允许干净复现的脱敏摘要 |
| `README.md` | 目标、步骤、复现、验收与集中限制 |
| `UX-CONTRACT.md` | 补齐观察到的原生导航与重开结果 |
| `web/index.html` | 更新同 Mac 新卡的验收状态文案 |
| `evidence/live-verification.json` | 真实执行和原生验收的统一摘要、来源哈希 |
| `evidence/verification-summary.json` | 标明历史固定版本记录的范围 |
| `evidence/clean-reproduction.json` | 新独立目录的检查与候选状态 |
| `PROCESS.md` | 按时间记录本轮阶段与下一决定 |
| `DEMO.md` | 2 分 10.72 秒成片说明、实际镜头及播放检查 |
| `FREEZE.md` | 本清单与冻结检查 |

私有原件、模型日志、账号／房间／event、机器路径、任务数据库及媒体候选留在仓库外或既有本地运行目录，不纳入上述清单。

## 核验命令

```sh
git status --short --branch
git rev-parse HEAD
git diff --check
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test rinx-contract/card-contract.test.mjs
node --check web/app.js
python3 tests/run_demo.py
```

完整测试在独立副本运行，59 项通过；离线契约 22 项、固定 demo 8 条断言通过。失败、重复批准、越界、超时等分支包含在既有套件中。原有真实执行与本次干净复现分别通过。本次新批准绑定既有候选，固定回归 9/1 → 10/0，四步退出码 1、0、0、0，重复批准无重跑；浏览器新增 9 项通过。固定套件使用 stub 验证模型故障分支；本次真实调用单独留证。

冻结前应核对本轮最终文件哈希、仅文档／状态文案差异、真实候选的批准与实际结果，并对将公开的文件和媒体做最后一次脱敏检查。最终文档与测试时的叠加补丁相比只增加了流程、演示和冻结说明，没有新的运行逻辑改动。

## 下一步范围

1. 已完成新候选批准、固定回归、重复批准及浏览器验收；摘要与截图已更新。
2. 集中确认本清单的 10 个文件、仓库外视频 `Ragnarok-result-review.mp4`、主选两张图片及分支策略。视频 SHA-256：`770f8164d9be8546324d191bb584c16d62aecd83a1e2716221a0222f2fa6004c`。原始录像和中间文件不纳入公开候选。
3. 建议获批后在 `live-codex-todo` 的 `9da2f90` 上创建一个仅含这 10 个文件的文档／证据提交；保留父提交，禁止 amend 或 force push。新提交用完整 SHA 固定，后续复现同时记录运行代码基线 `9da2f90` 和材料提交 SHA。
4. 如另获推送授权，仅推送该分支；main、PR、tag、release 和媒体公开范围独立确认。当前不创建提交或新分支。

拟用提交说明：`Document native acceptance and clean reproduction`。当前不执行 commit、push、merge、tag、release 或公开媒体上传。脱敏视频及两张主审图已私存用户 Library。


## 拟公开目标（待集中确认）

仓库为 `JadeSnow7/Ragnarok`。获批后只将上表 10 个文件创建为一个文档／证据提交并正常推送到 `live-codex-todo`，父提交固定为 `9da2f90b882ef3e9831c642f78942c0f07bc2a67`。不 amend、不 force push，不修改 main。

视频与两张图片不加入 Git 树。建议作为同一 GitHub prerelease 的三个附件：tag `demo-live-codex-2026-10-03`，标题 `Ragnarok — Live Codex Todo result review (2026-10-03)`，tag 精确指向上述新文档提交的完整 SHA；此 SHA 只能在实际提交后记录，不预造。若分支基线或 tag 状态变化，停止该发布步骤重新核对。

| 拟附件 | 来源与检查 |
|---|---|
| `Ragnarok-result-review.mp4` | 130.72 秒、1080p 真实 Rinx 原生操作录屏，回顾此前已完成结果；剪去路径片段、裁剪聊天身份并加说明字幕。无截图拼接、变速或合成界面。整段解码、Edge 播放通过；每半秒抽样 261 帧未发现指定敏感模式。 |
| `03-clean-live-passed.png` | 本次干净复现实际通过页面；仅在浏览器画面中隐藏任务标识、机器路径及原始日志，后台证据不变。 |
| `01-native-acceptance-existing.png` | 此前同 Mac 第二账号原生重开后的实际截图；与本次干净复现分别标注。无身份、房间、event 或机器路径可见。 |

两图已逐张检查；PNG 元数据仅含尺寸、分辨率和截图说明或为空。发布文案只使用仓库相对路径、附件名及证据哈希，不含本地绝对路径、Library ID、原始数据库、模型日志或未脱敏录像。三个附件的逐字节大小和 SHA-256 随本地发布审批清单固定。
