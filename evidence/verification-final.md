# verification-final · 干净环境复现演练（M5）

在全新临时目录 `/tmp/clean-repro/`（无 .venv、无 output、无预生成 mid，仅源码 + requirements + README）严格照修订版 `mcp-server/README.md` 从零执行。记录每条命令、实际耗时、遇到的坑。

## 命令序列与实测耗时

| # | 命令 | 实测耗时 | 结果 |
|---|---|---|---|
| 1 | `python3 -m venv .venv` | （<1s，本机秒建） | ✅ |
| 2 | `.venv/bin/pip install -r requirements.txt` | **21.3s** | ✅ |
| 3 | `.venv/bin/python make_test_midi.py test.mid` / `test-34.mid` | <1s | ✅ 33 音 4/4 + 4小节 3/4 |
| 4 | `.venv/bin/python mcp_smoke_test.py` | **2.3s** | ✅ 5 工具注册 + 实装通路 |
| 5 | 端到端最快路径（analyze→chords→stems→render→validate） | **全链路 wall 25.2s**（其中 render ≈24.7s） | ✅ demo.wav + 6 段全 validate=True |

> 全链路总 wall time（步骤5，含 5 个工具 + 6 段 validate）：**25.158s**。其中 render（fluidsynth 合成 23.9s 音频）独占 **24.684s**，其余四工具 <0.01s。分步数据存 `evidence/validation/benchmark.json`。

## 全链路 wall time（性能数字）

- **全链路（analyze+chords+stems+render+validate×6）：25.158s**
- 瓶颈：`render`（fluidsynth 真实 GM SoundFont 合成）= **24.684s**，占 98%。MIDI 排布/和声/校验步骤 <10ms。
- 产物：`output/demo.wav`（4,217,900 B ≈ 4.2MB，44.1kHz 16-bit 双声道，~23.9s 音频）

## 遇到的坑（如实记录）

1. **首次跑 `run_write_path.py` 报 `ModuleNotFoundError: No module named 'core'`** —— 脚本在 `evidence/tests/normal/time34-write-path/`，`ROOT` 层级算错（原 `parent×3` 指向 `tests/`）。修为 `parent×5` 指向项目根。
2. **3/4 样例 stems 鼓组 48 音（预期 36）** —— INC-015：`_DRUM_PATTERN+_HIHAT` 固定 4/4 位置，3/4 小节 hi-hat 3.0/3.5 越界仍写入。修为按 `beats_per_bar` 裁剪。
3. **`render-sf-missing` 返回 status=ok（应为硬失败）** —— INC-016：fluidsynth 对缺失 SF2 静默用内置音色。修 `render_impl` 先校验 soundfont 存在性，不存在直接 `status=failed`。
4. **干净目录复现本身一次跑通**（venv→pip→make_test_midi→smoke→端到端），无额外阻塞。

## 四步闭环 ↔ 证据文件映射（规划/调用/反馈/验证）

| 闭环步 | 含义 | 证据文件 |
|---|---|---|
| 规划 | M2 §0 当前编曲方案（analyze→风格/配器/和声） | `evidence/sessions/01-m1-m4-full.html`（规划轨迹）+ `call-chains/01-analyze.json` |
| 调用 | 工具链 5 步实调 | `evidence/call-chains/02-full-chain.json`（逐步 input/return） |
| 反馈 | 用户「伴奏太单薄」→参数 diff 修订 | `evidence/call-chains/03-feedback.json` + `sessions/01-m1-m4-full.html`（M3 §0.1） |
| 验证 | 专业校验 + 故障/边界 + 渲染 + 基准 | `evidence/validation/report-00{1,2}.json`、`render-check.json`、`benchmark.json`、`evidence/tests/`（12 目录） |

## 结论

修订版 README 照跑**一次跑通**（无需再改）。全链路可复现、性能数字（wall 25.2s / render 24.7s）已存 `benchmark.json`。
