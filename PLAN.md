# AI 编曲助手 — 实现计划

## 0. 当前编曲方案 v1（M2 基线，针对 test.mid）

基于 analyze 输出（C major, 90 BPM, 4/4, 音域 60–72, 33 音, 8 小节）：

- **风格**：轻流行（light pop），harmonic_complexity=2（三和弦为主，允许 IV 级小和弦）
- **配器表**（GM program）：
  | 声部 | GM program | 说明 |
  |---|---|---|
  | melody | 0（Acoustic Grand Piano） | 原旋律保留 |
  | harmony | 4（E.Piano 1） | 三和弦配器，0.5 密度，八度内 C4–G4 位置 |
  | bass | 38（Electric Bass Finger） | 根音 + 经过音，C2–G2（36–43）|
  | drums | 96（Kit 2） | 轻流行 4 拍 pattern：kick 1&3、snare 2&4、hi-hat 八分 |
  | countermelody | 80（Flute） | 仅填充乐句休止点，与主旋律问答式对位 |
- **和声进行**（8 小节）：
  | 小节 | 和弦 | 功能 | 转位 |
  |---|---|---|---|
  | 1 | C（C-E-G） | T | 根位 |
  | 2 | G/B（G-B-D） | D | 三转位（B 低音） |
  | 3 | F（F-A-C） | P | 根位 |
  | 4 | G（G-B-D） | D | 根位 |
  | 5 | Am（A-C-E） | T\' | 根位 |
  | 6 | F（F-A-C） | P | 根位 |
  | 7 | G（G-B-D） | D | 根位 |
  | 8 | C（C-E-G） | T | 根位（终止） |
  和声公式：`I – V⁶⁵ – IV – V – vi – IV – V – I`（终止式 V→I 完整）
- **MIDI 输出**：`output/stems/{melody,harmony,bass,drums,countermelody}.mid` + 合并 `output/stems/combined.mid` + 渲染 `output/demo.wav`

## 0.1 M3 修订（用户反馈：「伴奏太单薄，副歌部分不够饱满」）

乐句结构分析：test.mid 前 4 小列为 A 段（主歌），后 4 小节为 B 段（副歌）。以下修改仅作用于 B 段（小节 5–8），并全局增强各声部厚度：

- ⭐ **和声垫加厚（harmony）**：A 段保持三和弦块和弦不变；B 段改为 16 分音符分解和弦（分解密度 4x），并在根音上方叠加 7 音（E 大七/属七倾向音，C 大调内 diatonic 七和弦），和弦音数 3→4，velocity 70→80
- ⭐ **鼓组副歌加花（drums）**：A 段维持 4 拍基础 pattern（kick 1&3 / snare 2&4 / hi-hat 八分）；B 段 hi-hat 升级为 16 分音符，kick 增加 3.5 拍反拍加花（八分 ghost 击），snare 保持 2&4 不变
- ⭐ **贝斯八度跳进（bass）**：A 段整小节根音不变；B 段（小节 5–8）改为「根音（半拍）→ 根音+12（半拍）→ 低五度半音经过音（1 拍）」的八度跳进模式，增强律动
- ⭐ **副旋律填充（countermelody）**：B 段休止点填充音密度提升，新增 2 个长音呼应（C5/G4，各 1.5 拍，velocity 70），保持 C 大调 diatonic
- 风格/调性/速度/和声进行公式保持不变；仅声部内部参数调整

**调用参数 diff（stems_impl）**：`density 0.5 → 1.0`，新增 `section_bars=[4,8]`（副歌小节区间，0-based [4,8) 对应小节 5–8）、`chorus_enhance=True`
**MIDI 版本**：旧产物已重命名 `output/stems/*-v1.mid` + `output/chords.json` 保留为基线；新产物覆盖 `output/stems/*.mid` + `output/demo.wav`

## 0.2 M4 修订（SoundFont 获取成功 + 渲染尾部修复 + 测试样例）

- ⭐ **真实 GM SoundFont 接入（INC-011）**：`mcp-server/assets/GeneralUser_GS.sf2`（31MB，GitHub LFS 渠道 gh CLI 获取），`render_impl` 默认 `soundfont` 指向它；`demo.wav` 由 fluidsynth 真实 GM 音色渲染（23.9s/2ch/mean -7.0dB），波形合成版保留为 `demo-wave.wav` 对照
- ⭐ **渲染尾部覆盖修复（已知问题#3）**：`_fallback_render_wav` 总时值改为 `max(MIDI 总时值, 最后一声部结束) + 0.5s`，消除「尾部 1.5s 未合成」
- ⭐ **测试样例（Part B）**：`evidence/tests/{normal,boundary,failure}/` 共 11+ 用例 + `SUMMARY.md` 一览
  - normal/：完整链路 `analyze→chords→stems→render→validate` + `regression-g34`（G 大调 3/4 拍，验证 M2 调性修复普适性）
  - boundary/（5 例）：240 BPM 极端速度、2 音符极短旋律、超常规音域 A0–C8、0 音符空旋律、3/4 拍号分支
  - failure/（4 例）：截断损坏 MIDI、.txt 伪装 .mid、不存在路径、渲染环节故障（模拟 SoundFont 缺失 = INC-008 场景）
- **渲染产物**：`output/demo.wav`（fluidsynth，真实音色，主交付）、`output/demo-wave.wav`（波形合成，对照 + INC-010 记录）

---

## 1. 系统概述

**输入**：一段旋律 MIDI 文件 + 风格要求（自然语言，如"轻爵士、80 BPM、温暖感"）
**输出**：
- 多轨 MIDI（主旋律、和声、贝斯、鼓、副旋律各独立轨道）
- 可试听音频（通过 fluidsynth 渲染为 WAV）
- 乐理校验报告（和声进行、对位法、节奏密度、调性一致性等）

## 2. 架构分层

```
┌─────────────────────────────────────────────────────┐
│  编排层（AI Agent / 本系统核心）                      │
│  - 解析用户意图与风格要求                              │
│  - 规划编曲策略（和声方向、配器方案）                   │
│  - 按序调用 MCP 工具链                                │
│  - 读取校验报告，触发修订循环                          │
│  - 最终验收与交付                                     │
└──────────────────┬──────────────────────────────────┘
                   │ MCP 协议（stdio）
┌──────────────────▼──────────────────────────────────┐
│  MCP 工具层（Python，4 个工具）                       │
│  ① analyze   — 旋律分析（调性/速度/乐句）             │
│  ② chords    — 和声进行生成                          │
│  ③ stems     — 分声部 MIDI 生成                       │
│  ④ validate  — 乐理校验                              │
└──────────────────┬──────────────────────────────────┘
                   │ 文件 / 内存
┌──────────────────▼──────────────────────────────────┐
│  渲染层                                                │
│  - pretty_midi：MIDI 读写与合成                        │
│  - music21：和声学、乐理分析                           │
│  - fluidsynth：多轨 MIDI → WAV 音频                  │
└───────────────────────────────────────────────────────┘
```

**职责边界**：
- 编排层不直接操作 MIDI 文件，全部通过 MCP 工具调用
- MCP 工具层无状态（每次调用独立），不持有编曲上下文
- 渲染层仅提供基础能力，不含"风格理解"逻辑

## 3. MCP 工具接口定义

所有工具通过 MCP（stdio transport）暴露，参数/返回值均为 JSON。

### 3.1 `analyze`

| 字段 | 类型 | 说明 |
|------|------|------|
| **输入** `midi_path` | `string` | 旋律 MIDI 文件路径 |
| **输入** `style_hint` | `string?` | 可选风格提示（用于辅助 BPM 判断） |
| **输出** `key` | `string` | 调性，如 "C major"、"F# minor" |
| **输出** `key_confidence` | `float` | 调性判定置信度 0–1 |
| **输出** `bpm` | `int` | 检测速度 |
| **输出** `time_signature` | `string` | 拍号，如 "4/4"、"3/4" |
| **输出** `phrases` | `array<Phrase>` | 乐句列表 |
| **输出** `melody_notes` | `array<Note>` | 提取的旋律音序列 |
| **输出** `duration_beats` | `float` | 旋律总时值（拍） |
| **输出** `note_density` | `float` | 每小节日均音数 |

```
Phrase = {
  start_beat: float,
  end_beat: float,
  start_tuplet: string,   // 如 "1|1"（第1小节第1拍）
  end_tuplet: string,
  contour: "ascending" | "descending" | "arch" | "flat",
  peak_pitch: int,        // MIDI note number
  root_motion: string?    // 主要根音运动（如 "I–IV–V"）
}

Note = {
  pitch: int,             // MIDI note number
  start_beat: float,
  end_beat: float,
  velocity: int
}
```

### 3.2 `chords`

| 字段 | 类型 | 说明 |
|------|------|------|
| **输入** `analysis` | `object` | `analyze` 的输出 |
| **输入** `style` | `string` | 风格，如 "jazz"、"pop"、"classical"、"lofi" |
| **输入** `harmonic_complexity` | `int` | 和声复杂度 1–5（1=三和弦，5=延伸和弦） |
| **输入** `progression_hint` | `string?` | 可选，用户指定的和声走向（如 "I-IV-vi-V"） |
| **输出** `progression` | `array<ChordEvent>` | 和声事件序列 |
| **output** `harmonic_figure` | `string` | 和声公式摘要，如 "I-IV-vi-V" |
| **output** `inversions` | `array<ChordEvent>` | 含转位信息（供 stems 对位使用） |

```
ChordEvent = {
  root: string,           // "C"、"F#"
  quality: string,        // "major"、"minor"、"dim7"、"7sus4"
  inversion: int,         // 0=根位, 1=一转, 2=二转, 3=三转
  start_beat: float,
  end_beat: float,
  tension: int,           // 和声紧张度 1-10
  function: string        // 功能：T(主)、P(下属)、D(属)、D7
}
```

### 3.3 `stems`

| 字段 | 类型 | 说明 |
|------|------|------|
| **输入** `analysis` | `object` | `analyze` 的输出 |
| **输入** `chords` | `object` | `chords` 的输出 |
| **输入** `style` | `string` | 风格 |
| **输入** `parts` | `array<string>` | 请求生成的声部，如 ["harmony","bass","drums","countermelody"] |
| **输入** `density` | `float` | 节奏密度 0–1（影响和弦配器疏密） |
| **输出** `midi_paths` | `array<StemFile>` | 各声部 MIDI 文件路径 |
| **output** `combined_midi_path` | `string` | 合并多轨 MIDI 路径 |
| **output** `audio_path` | `string` | fluidsynth 渲染的 WAV 路径 |
| **output** `tracks` | `array<TrackInfo>` | 各轨道元信息 |

```
StemFile = {
  part: string,           // "melody"、"harmony"、"bass"、"drums"、"countermelody"
  midi_path: string,
  instrument: string,     // 推荐乐器名，如 "Acoustic Grand"、"Electric Piano"
  program: int            // GM program number
}

TrackInfo = {
  part: string,
  note_count: int,
  avg_notes_per_bar: float
}
```

**声部规则**（供 `stems` 内部实现参考）：

| 声部 | 职责 | 关键约束 |
|------|------|----------|
| melody | 原旋律 | 最高声部，不可被其他声部掩盖 |
| harmony | 和弦配器 | 与旋律保持至少 2 音程间距；同向/平行五度检查 |
| bass | 根音/和弦音行走 | 根音为主，允许经过音；八度内活动 |
| drums | 节奏骨架 | 按风格选择 pattern（4/4 rock: 4on4 kick）；不填旋律乐句空隙 |
| countermelody | 副旋律 | 填充乐句呼吸点；与主旋律形成问答或对话；避免同度/五度 |

### 3.4 `validate`

| 字段 | 类型 | 说明 |
|------|------|------|
| **输入** `analysis` | `object` | `analyze` 的输出 |
| **输入** `chords` | `object` | `chords` 的输出 |
| **输入** `stems` | `object` | `stems` 的输出 |
| **输入** `style` | `string` | 风格（用于风格适切性检查） |
| **输出** `score` | `float` | 综合得分 0–100 |
| **output** `checks` | `array<CheckResult>` | 各校验项结果 |
| **output** `issues` | `array<Issue>` | 问题列表（含定位与建议） |
| **output** `suggestions` | `array<string>` | 改进建议 |

```
CheckResult = {
  name: string,           // 校验项名称
  status: "pass" | "warn" | "fail",
  detail: string,
  affected_beats: array<float>?
}

Issue = {
  severity: "error" | "warning",
  category: string,       // "voicing"、"counterpoint"、"harmonic"、"rhythmic"、"style"
  message: string,
  beat: float,
  part: string,
  suggestion: string
}
```

**校验项清单**：

| 校验项 | 说明 | 级别 |
|--------|------|------|
| 调性一致性 | 所有声部音高在目标调内（允许经过音） | error |
| 平行五度/八度 | 和声与旋律、副旋律与旋律之间无平行五八度 | error |
| 声部间距 | 相邻声部音程 ≥ 三度（允许四度经过） | warning |
| 和声进行 | 无连续属→主以外的解决不当；功能序合理 | error |
| 低音独立性 | 低音与旋律不同向同音（避免同度/八度齐奏） | warning |
| 节奏密度 | 各声部每小节音符数在合理范围内 | warning |
| 风格适切 | 和弦延伸度、配器选择符合风格要求 | info |
| 力度层次 | 各声部 velocity 有合理动态范围 | info |

## 4. 里程碑拆分

### M1：骨架（Day 1–2）

**目标**：MCP 服务可启动、可调用、工具可注册。

- [ ] Python 项目结构搭建（`server/`、`tools/`、`render/`、`tests/`）
- [ ] MCP server 入口（FastMCP / mcp-python 库，stdio transport）
- [ ] 4 个工具函数签名 + 空实现（返回 mock JSON）
- [ ] 与编排层连通验证（`analyze` 调用成功）
- [ ] pretty_midi / music21 依赖安装与基础 API 验证
- [ ] fluidsynth 可执行文件确认，一次空渲染测试

**验收标准**：
1. MCP server 独立启动，4 个工具在注册表中可见
2. 编排层成功调用 `analyze`（mock 返回），无协议错误
3. fluidsynth 命令可执行，输出合法 WAV（可静音）
4. 单元测试：MIDI 文件读写往返（写入→读取→比对音高/时值）

### M2：核心链路（Day 3–5）

**目标**：`analyze` → `chords` → `stems` 三步跑通，输出可用 MIDI + WAV。

- [ ] `analyze` 实现：
  - music21 读取 MIDI，提取旋律音
  - 调性判定（Krumhansl-Schmuckler 算法 / 统计方法）
  - BPM 检测（onset 间隔聚类）
  - 乐句切分（基于停顿 + 小句对称 + 呼吸点）
- [ ] `chords` 实现：
  - 基于调性 + 旋律音推导和声（旋律音→和弦成员/经过/延伸）
  - 风格模板（pop: I-V-vi-IV 为主；jazz: ii-V-I + 延伸）
  - 转位优化（低音线性，避免根音跳 > 五度）
  - 和声公式输出
- [ ] `stems` 实现：
  - harmony：和弦配置器（voicing algorithm，按风格选择延伸音）
  - bass：根音 + 经过音，八度内
  - drums：风格 pattern 库（pop/rock/jazz/lofi 各一套 4-bar pattern）
  - countermelody：旋律问答（填充乐句间隙，同调性，节奏互补）
  - 多轨 MIDI 组装（pretty_midi Inbound 合并）
  - fluidsubsynth 渲染（GM SoundFont，各轨道映射 GM program）
- [ ] 端到端：输入示例 MIDI → 输出 5 轨 MIDI + WAV

**验收标准**：
1. 给定 3 个不同调性/拍号的示例 MIDI，`analyze` 调性判定准确率 ≥ 80%
2. `chords` 输出和声进行在乐理上合法（无连续平行五度、功能序无矛盾）
3. `stems` 输出 5 轨 MIDI，各轨音高在 GM 范围内（21–108）
4. WAV 文件时长与 MIDI 一致，采样率 44.1kHz，可正常播放
5. 全程无 crash，异常路径（空 MIDI、单音 MIDI）有优雅降级

### M3：反馈修订（Day 6–7）

**目标**：`validate` 实现 + 编排层闭环反馈。

- [ ] `validate` 实现：
  - 音高校验（调内性、平行五八度）
  - 和声进行校验（功能序、解决）
  - 对位法校验（间距、同向）
  - 节奏密度统计
  - 风格适切性匹配
  - 输出结构化问题列表 + 改进建议
- [ ] 编排层反馈循环：
  - 读取 `validate` 报告，按 severity 排序
  - error 级问题 → 调整 `chords` 参数重新生成
  - warning 级 → 记录，可选微调
  - 最多 3 轮修订，收敛或停止
  - 最终报告生成（Markdown，含得分、问题、建议）
- [ ] 人工试听回路：
  - WAV 输出到指定路径
  - 报告附试听文件引用
  - 用户可基于报告手动指定修订方向（如"和声太满"→降低 density）

**验收标准**：
1. `validate` 对故意注入错误的 MIDI（平行五度、调外音）100% 检出
2. 反馈循环：第一轮修复后 error 数下降 ≥ 50%，或 3 轮后 error = 0
3. 最终校验报告为 Markdown，含：得分、逐项 check 状态表、问题定位（beat + part）、建议
4. 用户可在编排层对话中指定修订指令，系统正确路由到对应参数

### M4：验证导出（Day 8–9）

**目标**：端到端稳定、交付物完整。

- [ ] 多轨 MIDI 导出验证：
  - 各轨道独立可导出（用于 DAW 导入）
  - 合并 MIDI 文件轨道顺序与命名规范
- [ ] 音频导出验证：
  - WAV 44.1kHz 16-bit，时长准确
  - 可选 MP3 转码（ffmpeg）
- [ ] 报告导出：
  - Markdown 校验报告（人类可读）
  - JSON 校验报告（机器可读，供后续自动化）
- [ ] 性能测试：
  - 3 分钟旋律：全链路 < 60s
  - 5 轨 MIDI 文件大小 < 500KB
- [ ] 文档：
  - `README.md`：安装、运行、配置
  - 示例输入/输出
  - 风格模板说明
- [ ] 回归测试：
  - 5 个不同风格 × 3 个调性 = 15 个组合测试用例
  - 通过率 100%，无 crash

**验收标准**：
1. 15 个测试用例全部通过（校验得分 ≥ 80，无 error）
2. 3 分钟 MIDI 全链路耗时 < 60s
3. 交付物三件套：多轨 MIDI + WAV + Markdown 报告，均在指定输出目录
4. 各轨 MIDI 可导入主流 DAW（Cubase/Logic/Ableton）无音高/时值异常
5. 项目有 README，新人 10 分钟内可跑通 demo

## 5. 技术选型摘要

| 组件 | 选型 | 理由 |
|------|------|------|
| MCP 框架 | FastMCP (Python) | 轻量、stdio transport、类型提示友好 |
| 和声分析 | music21 | 和声学 API 完整（Scale、Chord、RomanNumeral） |
| MIDI 操作 | pretty_midi | 多轨读写 API 简洁 |
| 音频渲染 | fluidsynth (CLI) | 支持 SoundFont、多轨渲染、非交互式 |
| SoundFont | GM 标准 SF2（如 Fluid） | 覆盖 128 种 GM 乐器 |
| 调性检测 | Krumhansl-Schmuckler + 统计 | 纯 Python 实现，无外部依赖 |
| 输出格式 | MIDI (Type 1) + WAV (PCM 16-bit) | DAW 通用 + 即时试听 |

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 调性判定不准（小调/关系大小调混淆） | 和声全错 | confidence < 0.6 时要求用户确认调性 |
| fluidsynth 渲染多轨音色冲突 | 音频不清晰 | 各轨独立 program，预留 velocity 层次 |
| 副旋律与主旋律节奏冲突 | 听觉混乱 | countermelody 仅在乐句间隙出现，节奏互补算法 |
| 风格要求模糊（"有点爵士"） | 输出不匹配 | 编排层澄清后映射为 1–5 参数（complexity/density） |
| MIDI 文件损坏/格式异常 | 链路中断 | `analyze` 入口做 schema 校验，提前报错 |

## 7. 目录结构（预期）

```
compose-assistant/
├── server/
│   ├── __init__.py
│   ├── mcp_server.py        # FastMCP 入口，注册 4 工具
│   └── models.py            # Pydantic 数据模型
├── tools/
│   ├── analyze.py
│   ├── chords.py
│   ├── stems.py
│   └── validate.py
├── render/
│   ├── midi_io.py           # pretty_midi 封装
│   ├── fluidsynth.py        # fluidsynth CLI 调用
│   └── soundfont.py         # SF2 管理
├── theory/
│   ├── key_detection.py     # 调性判定
│   ├── harmony.py           # 和声推导
│   ├── voicing.py           # 配置算法
│   ├── counterpoint.py      # 对位检查
│   └── rhythm.py            # 节奏 pattern 库
├── templates/
│   ├── styles/              # 风格模板 JSON
│   │   ├── pop.json
│   │   ├── jazz.json
│   │   ├── lofi.json
│   │   └── classical.json
│   └── drum_patterns/       # 鼓组 pattern
├── tests/
│   ├── test_analyze.py
│   ├── test_chords.py
│   ├── test_stems.py
│   ├── test_validate.py
│   └── test_e2e.py
├── output/                  # 运行时生成
├── README.md
└── requirements.txt
```

## 8. 编排层调用序列（标准流程）

```
用户输入：melody.mid + "轻爵士，不要太满"
    │
    ▼
[编排层] 解析风格 → {style: "jazz", density: 0.5, complexity: 3}
    │
    ▼
[1] analyze(melody.mid, style_hint="jazz")
    → key, bpm, phrases, melody_notes
    │
    ▼
[2] chords(analysis, style="jazz", complexity=3)
    → progression, inversions
    │
    ▼
[3] stems(analysis, chords, style="jazz", parts=["harmony","bass","drums","countermelody"], density=0.5)
    → 5 轨 MIDI + WAV
    │
    ▼
[4] validate(analysis, chords, stems, style="jazz")
    → score=87, issues=[2 warnings, 0 errors]
    │
    ▼
[编排层] score ≥ 80 且无 error → 通过
    │
    ▼
交付：多轨 MIDI + WAV + 校验报告（Markdown）
```

若 `validate` 返回 error → 编排层根据 issue.suggestion 调整参数，回到 [2] 或 [3]，最多 3 轮。
