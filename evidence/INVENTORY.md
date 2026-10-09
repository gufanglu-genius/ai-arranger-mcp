# 4.2 证据清单（INVENTORY）

按 4.2 八项必填逐条登记。每项标注**证据路径 + 一句话说明 + 完整状态**。
「AGH 执行记录」与「工具调用链」严格区分：前者 = sessions/ 导出 HTML，后者 = call-chains/ JSON，不混用。

---

## 4.2 八项 ↔ 证据类别映射总表

| 4.2 项 | 对应证据类别（目录/文件） | 归属 |
|---|---|---|
| ① AGH 执行记录 | `evidence/sessions/`（01-m1-m4-full.html、02-m5-fork.html 会话轨迹）+ 轨迹截图 02/04/05 | 本系统 ✅ |
| ② 工具调用链 | `evidence/call-chains/`（02-full-chain.json、03-feedback.json 为主，01-analyze/04-m4-normal 辅） | 本系统 ✅ |
| ③ 模型参与证据 | `evidence/model/`（model-info.txt + provider-config.png）+ sessions 轨迹 + 轨迹截图 01 | 本系统 ✅ |
| ④ 关键配置 | `mcp-server/requirements.txt` + `README.md` + `assets/GeneralUser_GS.sf2`(INC-011) + model-info.txt | 本系统 ✅ |
| ⑤ 专业验证结果 | `evidence/validation/`（report-001/002、render-check、benchmark、incidents、verification-final） | 本系统 ✅ |
| ⑥ 测试样例 | `evidence/tests/`（SUMMARY + 12 目录 + time34-write-path） | 本系统 ✅ |
| ⑦ 成员声明 | （占位，无文件） | **队长/主持人** ⬜ |
| ⑧ 公开内容 | （占位，无文件） | **队长/主持人** ⬜ |

> 本表与下方逐条登记一致；展示页 `docs/index.html` 的「可运行作品」卡片亦按此映射呈现。

---

## ① AGH 执行记录（AGH 会话轨迹 = 模型参与的原始证据）

| 文件 | 说明 | 状态 |
|---|---|---|
| `evidence/sessions/01-m1-m4-full.html` | 主会话 M1–M4 全程轨迹（规划→全链路→反馈修订→M4 测试），经 `--standalone` 进程内导出（daemon 大会话断连缺陷见 INC-014） | ✅ |
| `evidence/sessions/02-m5-fork.html` | M5 fork 会话全程（拍号写路径复测/两档分类/README 复现），同上导出方式 | ✅ |

> 注：4.2「AGH 执行记录」的权威形式即这两份会话轨迹 HTML，而非 call-chains JSON。

## ② 工具调用链（MCP 工具调用链，含参数与返回）

| 文件 | 说明 | 状态 |
|---|---|---|
| `evidence/call-chains/02-full-chain.json` | analyze→chords→stems→render→validate 全链路逐步调用（5 工具各 1 次，含每步 input/return/status） | ✅ |
| `evidence/call-chains/03-feedback.json` | M3 反馈「伴奏太单薄」→参数 diff 修订前后两次调用对比（stems 参数 diff） | ✅ |
| `evidence/call-chains/01-analyze.json` | 单步 analyze 证据（M4 已刷新：含 melody_time_signature 字段） | ✅ |
| `evidence/call-chains/04-m4-normal.json` | M4 全链路 4 例（含 regression-g34 调性回归）逐步调用 | ✅ |

## ③ 模型参与证据（模型在编曲中的实际角色，配套 AGH 配置）

| 文件 | 说明 | 状态 |
|---|---|---|
| `evidence/model/model-info.txt` | 模型名 agnes-3.0-flash、preset/route/provider + 使用环节（方案规划/反馈修订/测试验证）+ AGH 配置交叉 | ✅ |
| `evidence/model/provider-config.png` | AGH Provider 页截图（宿主已备好，与 model-info.txt 配套） | ✅ |
| `evidence/sessions/01-m1-m4-full.html` | 模型规划 M2 §0 当前编曲方案、M3 §0.1 反馈修订的原始轨迹 | ✅（与①共用） |

## ④ 关键配置（系统配置、依赖、渲染音色来源）

| 文件 | 说明 | 状态 |
|---|---|---|
| `mcp-server/requirements.txt` | 依赖声明（fastmcp + pretty_midi） | ✅ |
| `mcp-server/README.md` | M5 修订版：安装/生成/运行/验证/端到端最快路径/交付物/已知限制 | ✅ |
| `mcp-server/assets/GeneralUser_GS.sf2` | 真实 GM SoundFont（31MB，INC-011 GitHub LFS 渠道获取） | ✅ |
| `mcp-server/test.mid` / `test-34.mid` | 基线 C major 4/4 与 3/4 测试样例 | ✅ |
| `evidence/model/model-info.txt` | AGH 模型/Provider 配置 | ✅（与③共用） |

## ⑤ 专业验证结果（验证报告 + 事故记录 + 渲染检查 + 基准）

| 文件 | 说明 | 状态 |
|---|---|---|
| `evidence/validation/report-001.json` | M2 首次验证（validate 初版全项通过） | ✅ |
| `evidence/validation/report-002.json` | M2 验证复跑 | ✅ |
| `evidence/validation/render-check.json` | 渲染双文件对照（demo.wav fluidsynth vs demo-wave.wav 波形） | ✅ |
| `evidence/validation/incidents.md` | INC-001…INC-016（含 INC-014 导出缺陷、INC-015 3/4 鼓组裁剪、INC-016 无效 SF2 硬失败） | ✅ |
| `evidence/validation/benchmark.json` | 干净目录全链路 wall time + 分步（analyze/chords/stems/render） | ✅ |
| `evidence/verification-final.md` | 干净目录复现演练（命令序列 + 总耗时 + 四步闭环↔证据映射） | ✅ |

## ⑥ 测试样例（normal / boundary / failure + 3/4 写路径）

| 文件 | 说明 | 状态 |
|---|---|---|
| `evidence/tests/SUMMARY.md` | 11 用例 0 FAIL + M5 两档判定说明（soft/hard） | ✅ |
| `evidence/tests/run_tests.py` | 测试生成器 + failure 两档分类逻辑 | ✅ |
| `evidence/tests/normal/full-chain/` | C major 完整链路（input/chords/stems/demo.wav/result.json） | ✅ |
| `evidence/tests/normal/regression-g34/` | G major 调性回归 | ✅ |
| `evidence/tests/normal/time34-write-path/` | M5 3/4 拍号「写入→读回→chords/stems」全链路（make_test_midi 正式生成器，PASS） | ✅ |
| `evidence/tests/boundary/{bpm240,two-notes,extreme-range,empty-melody,time34}/` | 5 边界用例 | ✅ |
| `evidence/tests/failure/{corrupt-mid,wrong-extension,nonexistent-path,render-sf-missing}/` | 4 故障用例（均 hard 档） | ✅ |

## ⑦ 成员声明

> **本系统范围外**：成员名单与分工由队长（主持人）提供，非 MCP 工具服务可产出的证据。此处仅登记占位。

| 文件 | 说明 | 状态 |
|---|---|---|
| （占位，队长提供） | 团队成员声明 | ⬜ 非本系统职责 |

## ⑧ 公开内容（开源/发布说明）

> **本系统范围外**：公开仓库/发布说明由队长统筹。此处仅登记占位。

| 文件 | 说明 | 状态 |
|---|---|---|
| （占位，队长提供） | 公开内容 | ⬜ 非本系统职责 |

---

## 轨迹截图（AGH 交互截图，宿主已备好）

| 文件 | 说明 | 归入项 |
|---|---|---|
| `evidence/trajectory/01-conversation-plan-top.png` | 编曲方案规划对话顶 | ③ 模型参与 |
| `evidence/trajectory/02-trace-timeline-overview.png` | 轨迹时间线总览 | ① AGH 执行记录 |
| `evidence/trajectory/03-trace-tool-steps.png` | 轨迹工具步骤 | ② 工具调用链 |
| `evidence/trajectory/04-trace-deeper.png` | 轨迹深层展开 | ① AGH 执行记录 |
| `evidence/trajectory/05-trace-early-records.png` | 轨迹早期记录 | ① AGH 执行记录 |

---

## 可运行作品 · 在线体验（4.2 官方八项结构对应，M5 静态展示页交付）

> 本系统负责人：MCP 工具服务（Agnes）。队长负责 push 后回填 Pages 仓库链接。

| 字段 | 内容 | 状态 | 负责人 |
|---|---|---|---|
| 在线体验链接 | `https://gufanglu-genius.github.io/ai-arranger-mcp/`（GitHub Pages，已上线） | ✅ 已回填 | 队长 |
| 代码仓库 | `https://github.com/gufanglu-genius/ai-arranger-mcp`（仓库根 `README.md` 含 5 工具 MCP 服务 + 展示页 + 证据体系完整说明） | ✅ 已回填 | 队长 |
| 复现说明 | `README.md`「快速开始」节 + `mcp-server/README.md`「端到端出 demo.wav（最快路径）」（venv→pip→make_test_midi→smoke→5 工具全链路） | ✅ | Agnes |
| 展示页 | `docs/index.html`（单文件、内联 CSS/JS、零构建零依赖、GitHub Pages 兼容、双击本地可开；含整曲波形/分轨试听/和弦卡片/系统链路/快速开始/验证证据/页脚如实说明） | ✅ | Agnes |
| 构建脚本 | `scripts/render_stems_audio.py`（fluidsynth + `GeneralUser_GS.sf2` 把 6 轨 MIDI → WAV 到 `docs/assets/stems/`，幂等可复跑；已验收 6/6 OK，peak=32768 非静音） | ✅ | Agnes |
| 验收自查 | `python3 -m http.server -d docs 8099` 首页 200、assets 相对路径 404=0；六轨 WAV 全部 2.9–4.0MB（<10MB，无需改单声道）且峰值非 0；chords.json 内嵌与源文件 diff 一致；375px 窄屏 `overflow-x:hidden` + `@media (max-width:640px)` 断点无横向溢出 | ✅ | Agnes |
| 红线合规 | `.gitignore` 已排除 `.DS_Store`、`~/.agh/`、`mcp-server/assets/*.sf2`（31MB，获取方式见 `mcp-server/README.md` INC-011）、`mcp-server/.venv/`、`__pycache__/`；六轨 WAV 单文件最大 4.02MB < 10MB 红线 | ✅ | Agnes |

---

## 完整性速览

- ✅ ①②③④⑤⑥ 全部齐备（sessions 2 HTML + call-chains 4 JSON + model 2 + 配置 5 + 验证 6 + 测试 12 目录）。
- ✅ 「可运行作品 · 在线体验」：展示页 `docs/index.html` + 构建脚本 `scripts/render_stems_audio.py` + 复现说明 `README.md` 就绪；在线体验链接 `https://gufanglu-genius.github.io/ai-arranger-mcp/` 与代码仓库 `https://github.com/gufanglu-genius/ai-arranger-mcp` 已回填（Pages 已上线）。
- ⬜ ⑦⑧ 不在本系统职责（队长提供）。
- 轨迹截图 5 张已登记归入 ①/②/③。
