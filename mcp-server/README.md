# AI 编曲助手 — MCP 工具服务（M2 全功能，5 工具）

## 前置

- Python ≥ 3.10（开发环境为 3.13）
- `fluidsynth`（渲染用；conda 安装：`conda install -c conda-forge fluidsynth`，
  安装到 `/opt/anaconda3/bin/fluidsynth`；本机无 brew）
- GM SoundFont（`assets/GeneralUser_GS.sf2`，随仓库提供；获取记录见
  `evidence/validation/incidents.md` INC-011，GitHub LFS 渠道）

> 未安装 fluidsynth 时 render 步骤如实返回 `skipped`，不阻塞其它工具。
> SoundFont 缺失时 render 自动降级为 pretty_midi 波形合成（有声、音色粗糙），
> 并带 WAV 静音检测。

## 安装

```bash
cd mcp-server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> requirements：`fastmcp`（MCP server 框架）+ `pretty_midi`（MIDI 读写，
> 其依赖含 `mido`）。

## 生成测试样例

```bash
# C major 4/4 基线样例
.venv/bin/python make_test_midi.py test.mid
# 3/4 拍样例（拍号写入路径复测用）
.venv/bin/python make_test_midi.py test-34.mid
```

## 运行 MCP 服务（stdio）

```bash
.venv/bin/python mcp_server.py
```

## 验证

```bash
# 直接调用 core（不经 MCP 协议）；写入 ../evidence/call-chains/02-full-chain.json
.venv/bin/python evidence_runner.py

# 完整 MCP 协议冒烟测试（5 工具注册 + analyze/validate/chords/stems/render 实装）
.venv/bin/python mcp_smoke_test.py
```

## 端到端出 demo.wav（最快路径）

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
# 产物：output/stems/*.mid + output/stems/combined.mid + output/demo.wav
```

## 交付物（M2）

| 文件 | 说明 |
|------|------|
| `core.py` | analyze / validate / chords / stems / render 五个工具核心实现 |
| `mcp_server.py` | FastMCP 入口，5 工具注册（analyze、validate、chords、stems、render） |
| `make_test_midi.py` | 生成 C 大调 90 BPM 4/4 与 3/4 测试 MIDI |
| `evidence_runner.py` | 全链路调用证据生成（02-full-chain.json） |
| `mcp_smoke_test.py` | MCP 协议冒烟测试 |
| `requirements.txt` | 依赖声明 |
| `assets/GeneralUser_GS.sf2` | GM SoundFont（31MB，INC-011 获取） |
| `test.mid` | 基线测试样例 |

## 已知限制

- 渲染默认走 `assets/GeneralUser_GS.sf2`；如缺失，自动降级为波形合成
  （有声但音色粗糙），并在结果 `renderer` 字段中如实标注。
- `validate` 的 BPM 默认允许区间为 40–300（M4 起放宽以覆盖 240 BPM 边界用例）。
- 3/4 拍号：`analyze` 输出 `melody_time_signature`（事件优先），`chords/stems`
  优先读它排布小节；无拍号事件时回退统计推断（保守 4/4）。
