# M4 测试样例汇总（evidence/tests/SUMMARY.md）

生成时间：2026-10-06T22:58:50.014656+00:00

三类共 11 用例。

| 用例 | 类别 | 输入特征 | 预期 | 实际 | 判定 | 行为合理 |
|---|---|---|---|---|---|---|
| full-chain | normal | C major 4/4, 12 音, 8 小节 | 完整链路 analyze→…→validate 全过 | 全链路正常 | **PASS** | — |
| regression-g34 | normal | G major 3/4, 6 音, 回归调性 | analyze 判定 G 大调 + 3/4 拍 | analyze→G 大调判定 + validate 全过；调性判定 G major（期望 G major） | **PASS** | — |
| bpm240 | boundary | 240 BPM 极端速度, 7 音 | 240 BPM 链路不崩溃 | 全链路正常 | **PASS** | — |
| two-notes | boundary | 仅 2 个音符极短旋律 | 2 音仍可生成 stems（和声/鼓） | 全链路正常 | **PASS** | — |
| extreme-range | boundary | A0(21)–C8(108) 超常规音域, 8 音 | 音域 A0–C8 校验边界 | 全链路正常 | **PASS** | — |
| empty-melody | boundary | 合法 MIDI 但 0 音符 | 0 音符 → 空旋律处理 | 全链路正常 | **PASS** | — |
| time34 | boundary | 3/4 拍, 6 音, 拍号分支 | 3/4 拍号分支正确 | 全链路正常 | **PASS** | — |
| corrupt-mid | failure | 截断字节（82B）损坏 MIDI | 报错，不崩溃 | 按预期抛出/报错：MidiLoadError: 无法解析 MIDI: ；系统给出明确错误未崩溃 ✓ | **PASS** | 硬失败报错 |
| wrong-extension | failure | .txt 伪装 .mid | 报错，不崩溃 | 按预期抛出/报错：MidiLoadError: 无法解析 MIDI: MThd not found. Probably not a MIDI file；系统给出明确错误未崩溃 ✓ | **PASS** | 硬失败报错 |
| nonexistent-path | failure | 不存在的文件路径 | 报错，不崩溃 | 按预期抛出/报错：MidiLoadError: 文件不存在: /tmp/definitely-not-here-nonexistent.mid；系统给出明确错误未崩溃 ✓ | **PASS** | 硬失败报错 |
| render-sf-missing | failure | 渲染故障（SoundFont 缺失=INC-008 场景） | 渲染失败给出明确错误 | 渲染环节：None / status=failed（硬失败：明确报错）；系统给出明确错误未崩溃 ✓ | **PASS** | 硬失败报错 |
| time34-write-path（M5） | normal | make_test_midi 正式生成器写 3/4 元事件, 12 音 4 小节 | 拍号写入→读回→chords/stems 全链路按 3 拍/小节 | write_ts=True analyze_ts=True chords_bars=True stems_drums=True validate_all=True | **PASS** | — |

## FAIL 用例明细（如实列出）

（无 FAIL 用例）

## M5 failure 两档判定说明
failure 用例「行为合理」拆成两档：
- **软降级成功（soft）**：遇到可恢复问题时系统自动 fallback（如 render 默认 allow_fallback=True 时 SoundFont 缺失→降级波形合成出声），链路继续走通。
- **硬失败报错（hard）**：问题不可恢复时抛出明确、可读的错误（MidiLoadError / render status=failed + stderr），不静默不崩溃。
本次 4 个 failure 用例全部落在 **hard 档**（均按设计显式排除了 soft 降级路径）。

## 说明
- normal/boundary 用例执行完整 MCP 工具链（analyze→chords→stems→render→validate），产物落盘到各 case 目录。
- failure 用例验证系统面对非法/缺失输入的健壮性：预期为给出明确错误而非崩溃。
- `render-sf-missing` 通过显式传入不存在的 soundfont + `allow_fallback=False` 模拟 INC-008 场景，验证渲染环节故障路径。
- `regression-g34` 验证 M2 调性修复（key_signature 优先读）在 G 大调 3/4 拍下的普适性。
- `time34-write-path`（M5）验证 3/4 拍号元事件「写入→读回→chords/stems 排布」全链路，独立于 run_tests.py 11 用例。
- 渲染用真实 GM SoundFont（`assets/GeneralUser_GS.sf2`，INC-011）；波形合成版留作对照。
