# AI 编曲助手 — 智能编曲 MCP 系统

以 **Agnes Harness（AGH）** 为底座的 AI 编曲系统：输入一段旋律 MIDI + 风格要求，
自动完成 **调性/拍号分析 → 和声进行 → 五声部分轨 → 音频渲染 → 专业校验** 全链路，
输出多轨 MIDI 与可试听 WAV。以 MCP 工具服务（FastMCP，stdio）形态提供 5 个工具。

## 🌐 在线展示页

> **占位 — 仓库 push 后由队长回填 GitHub Pages 链接。**
> 静态展示页：`docs/index.html`（零构建零依赖，GitHub Pages 兼容，双击本地亦可打开）。
> 构建脚本：`scripts/render_stems_audio.py`（分轨 WAV 渲染，幂等可复跑）。

## 目录

| 路径 | 说明 |
|---|---|
| `mcp-server/` | 核心：MCP 工具服务（`core.py` 五工具实现 + `mcp_server.py` FastMCP 入口） |
| `docs/` | 静态展示页（`index.html` + `assets/`） |
| `scripts/` | 分轨音频渲染脚本（`render_stems_audio.py`） |
| `evidence/` | 4.2 证据体系（会话轨迹 / 调用链 / 验证报告 / 测试样例 / 模型信息 / 事故记录） |
| `PLAN.md` | 编曲方案与 M2/M3/M4 修订记录（§0 规划、§0.1 反馈修订、§0.2 渲染与测试） |

## 快速开始

> 以下命令均在**仓库根目录**执行。详细前置与已知限制见 [`mcp-server/README.md`](mcp-server/README.md)。

**前置**：Python ≥ 3.10；`fluidsynth`（`conda install -c conda-forge fluidsynth`）；
GM SoundFont（`mcp-server/assets/GeneralUser_GS.sf2`，31MB，不入 git，获取方式见该 README 与
`evidence/validation/incidents.md` INC-011）。

**安装三步**（在 `mcp-server/` 内）：

```bash
cd mcp-server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**端到端出 demo.wav（最快路径）**：

```bash
cd mcp-server
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, ".")
from core import analyze_impl, chords_impl, stems_impl, render_impl, validate_impl
a = analyze_impl("test.mid")
c = chords_impl(a, style="pop", output_path="output/chords.json")
s = stems_impl(a, c, style="pop", output_dir="output/stems",
               density=1.0, section_bars=[4, 8], chorus_enhance=True)
r = render_impl(s["combined_midi_path"], "output/demo.wav")
print(r["status"], r.get("renderer"), r.get("wav_path"))
for p in s["midi_paths"].values():
    print(p, validate_impl(p)["all_passed"])
PY
```

产物：`mcp-server/output/stems/*.mid` + `combined.mid` + `mcp-server/output/demo.wav`。

**渲染分轨 WAV 到展示页资源**（展示页用，幂等）：

```bash
python3 scripts/render_stems_audio.py
```

## 验证

```bash
cd mcp-server
.venv/bin/python evidence_runner.py    # 全链路调用证据 → evidence/call-chains/02-full-chain.json
.venv/bin/python mcp_smoke_test.py     # MCP 协议冒烟（5 工具注册 + 实装通路）
```

## 验收状态

- 测试样例：**11 用例 0 FAIL**（`evidence/tests/SUMMARY.md`，normal / boundary / failure 三类）
- 3/4 拍号写路径：**5 项检查全过**（`evidence/tests/normal/time34-write-path/result.json`）
- 干净环境复现：全链路 wall time **25.2s**（render 占 24.7s，见 `evidence/validation/benchmark.json`）
- 事故记录：INC-001…INC-016（`evidence/validation/incidents.md`）

## 4.2 证据体系

完整映射见 [`evidence/INVENTORY.md`](evidence/INVENTORY.md)：
AGH 执行记录（`sessions/`）· 工具调用链（`call-chains/`）· 模型参与证据（`model/`）·
关键配置 · 专业验证结果（`validation/`）· 测试样例（`tests/`）。
