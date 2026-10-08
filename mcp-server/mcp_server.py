"""AI 编曲助手 — MCP 工具服务（M2）

安装：
    cd mcp-server
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

启动（stdio 模式）：
    .venv/bin/python mcp_server.py

M2 交付：
  - analyze：调性 / BPM / 拍号 / 旋律音域 / 乐句统计（M1 实装）
  - validate：音域越界 / 速度异常 / 空轨检查（M1 实装）
  - chords：和声进行生成（含转位），输出 chords.json（M2 实装）
  - stems：分声部 MIDI 生成（melody/harmony/bass/drums/countermelody）（M2 实装）
  - render：fluidsynth 渲染多轨 MIDI → WAV（M2 实装，未安装 fluidsynth 时如实 skipped）
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent))
from core import (  # noqa: E402
    MidiLoadError,
    analyze_impl,
    chords_impl,
    render_impl,
    stems_impl,
    validate_impl,
)

mcp = FastMCP("compose-assistant")


# ---------------------------------------------------------------------------
# 工具 1：analyze
# ---------------------------------------------------------------------------

@mcp.tool(
    name="analyze",
    description=(
        "读取旋律 MIDI，返回调性（含置信度与来源）、BPM、拍号、旋律音域、"
        "乐句数、音符总数和时值分布。"
    ),
)
def analyze(midi_path: Annotated[str, "旋律 MIDI 文件路径"]) -> dict[str, Any]:
    """旋律分析。返回 key/key_confidence/key_source/bpm/time_signature/pitch_min/pitch_max/..."""
    try:
        return analyze_impl(midi_path)
    except MidiLoadError as exc:
        return {"error": exc.message, "midi_path": midi_path}


# ---------------------------------------------------------------------------
# 工具 2：validate
# ---------------------------------------------------------------------------

@mcp.tool(
    name="validate",
    description=(
        "乐理校验：检查 MIDI 是否存在音域越界、速度异常、轨道为空等问题，"
        "返回通过/失败项列表。M1 覆盖音域/速度/空轨；M3 扩展对位法/和声功能校验。"
    ),
)
def validate(
    midi_path: Annotated[str, "待校验 MIDI 文件路径"],
    expected_bpm_range: Annotated[tuple[int, int], "允许 BPM 区间，默认 40–300"] = (40, 300),
    expected_pitch_range: Annotated[tuple[int, int], "允许音高范围（MIDI 1–127），默认 21–108"] = (21, 108),
    min_notes_per_track: Annotated[int, "每轨最少音符数，默认 1"] = 1,
) -> dict[str, Any]:
    """校验 MIDI，返回 all_passed / failures / checks。"""
    try:
        return validate_impl(
            midi_path,
            expected_bpm_range=expected_bpm_range,
            expected_pitch_range=expected_pitch_range,
            min_notes_per_track=min_notes_per_track,
        )
    except MidiLoadError as exc:
        return {"error": exc.message, "midi_path": midi_path, "all_passed": False, "failures": -1}


# ---------------------------------------------------------------------------
# 工具 3：chords（M2 实装）
# ---------------------------------------------------------------------------

@mcp.tool(
    name="chords",
    description="基于调性生成和声进行（支持转位），输出 chords.json。",
)
def chords(
    analysis: Annotated[dict[str, Any], "analyze 工具的输出"],
    style: Annotated[str, "风格：pop / jazz / lofi / classical"] = "pop",
    harmonic_complexity: Annotated[int, "和声复杂度 1–5，默认 3"] = 3,
    progression_hint: Annotated[str | None, "可选和声走向 token，如 'I V6/5 IV V vi IV V I'"] = None,
    output_path: Annotated[str | None, "可选 JSON 输出路径，如 output/chords.json"] = None,
) -> dict[str, Any]:
    """和声进行。M2 实装。"""
    return chords_impl(
        analysis,
        style=style,
        harmonic_complexity=harmonic_complexity,
        progression_hint=progression_hint,
        output_path=output_path,
    )


# ---------------------------------------------------------------------------
# 工具 4：stems（M2 实装）
# ---------------------------------------------------------------------------

@mcp.tool(
    name="stems",
    description="分声部 MIDI 生成（melody/harmony/bass/drums/countermelody），输出 output/stems/*.mid。",
)
def stems(
    analysis: Annotated[dict[str, Any], "analyze 工具的输出"],
    chords_out: Annotated[dict[str, Any], "chords 工具的输出"],
    style: Annotated[str, "风格"] = "pop",
    parts: Annotated[list[str] | None, "请求声部列表"] = None,
    density: Annotated[float, "节奏密度 0–1，默认 0.5"] = 0.5,
    output_dir: Annotated[str | None, "MIDI 输出目录，如 output/stems"] = None,
    section_bars: Annotated[list[int] | None, "副歌小节区间（0-based），如 [4,8] = 小节 5–8"] = None,
    chorus_enhance: Annotated[bool, "副歌增强开关：和声加 7 音 + 鼓组加花 + 贝斯八度跳进"] = False,
) -> dict[str, Any]:
    """分声部 MIDI。M2 实装；M3 增加副歌增强参数。"""
    return stems_impl(
        analysis,
        chords_out,
        style=style,
        parts=parts or ["melody", "harmony", "bass", "drums", "countermelody"],
        density=density,
        output_dir=output_dir,
        section_bars=section_bars,
        chorus_enhance=chorus_enhance,
    )


# ---------------------------------------------------------------------------
# 工具 5：render（M2 实装）
# ---------------------------------------------------------------------------

@mcp.tool(
    name="render",
    description="fluidsynth 渲染多轨 MIDI → WAV（44.1kHz 16-bit PCM）。未安装 fluidsynth 时如实返回 skipped。",
)
def render(
    midi_path: Annotated[str, "多轨 MIDI 路径（如 combined.mid）"],
    wav_path: Annotated[str, "输出 WAV 路径（如 output/demo.wav）"],
    soundfont: Annotated[str | None, "可选 SoundFont 路径，默认系统 SF"] = None,
) -> dict[str, Any]:
    """音频渲染。M2 实装（依赖本机 fluidsynth）。"""
    return render_impl(midi_path, wav_path, soundfont)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
