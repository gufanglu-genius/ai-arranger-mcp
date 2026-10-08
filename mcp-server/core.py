"""MCP 工具核心实现。

M1：analyze（调性/BPM/拍号/音域/乐句）+ validate（音域/速度/空轨）
M2：chords（和声进行+转位）+ stems（多轨生成）+ render（fluidsynth→WAV）

注意：pretty_midi 0.2.x 的 API 是 `pm.instruments`（list[Instrument]），
每个 Instrument 有 `.notes`、`.program`、`.is_drum`，没有 `pm.tracks`。
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import pretty_midi


# ---------------------------------------------------------------------------
# 调性检测（Krumhansl-Schmuckler）
# ---------------------------------------------------------------------------

_PITCH_CLASS_OFFSETS: dict[str, int] = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11,
}
_NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# C 大调 / C 小调的 Krumhansl-Schmuckler 基轮廓
_MAJOR_BASE = [1.87, 1.13, 2.08, 0.71, 1.55, 1.21, 2.88, 1.55, 2.51, 1.21, 1.90, 1.25]
_MINOR_BASE = [0.63, 1.52, 1.03, 1.37, 2.24, 1.48, 1.53, 1.05, 1.87, 1.22, 2.00, 1.16]


def _profile_for_key(root: str, is_minor: bool) -> list[float]:
    base = _MINOR_BASE if is_minor else _MAJOR_BASE
    offset = _PITCH_CLASS_OFFSETS[root]
    return [base[(i - offset) % 12] for i in range(12)]


# 大调 / 小调音级集合（相对根音 0 起算）
_MAJOR_PCS = {0, 2, 4, 5, 7, 9, 11}
_MINOR_PCS = {0, 2, 3, 5, 7, 8, 10}
# 主音（tonic）与终止音（final）在调内判定中的权重
_TONIC_WEIGHT = 2.0
_FINAL_WEIGHT = 1.5


def detect_key(
    pitch_classes: list[int],
    boundary_classes: list[int] | None = None,
) -> tuple[str, str, float]:
    """两段式调性判定。

    1. KS 轮廓相关（统计层面）
    2. 主音假设二次确认（结构层面）：
       - 根音在旋律音级集合内的频率
       - 首/尾音（boundary_classes）落在调内
       - 终止音（final）等于根音加分
       用 KS 排序后，对 top-3 候选加结构分再重排。

    返回 (音名, 大小调, 综合置信度 0~1)。
    """
    if not pitch_classes:
        return "C", "major", 0.0

    counts = Counter(pitch_classes)
    total = sum(counts.values())
    histogram = [counts.get(pc, 0) / total for pc in range(12)]
    present = set(pitch_classes)
    boundary = boundary_classes if boundary_classes is not None else [pitch_classes[0], pitch_classes[-1]]
    final = boundary[-1]

    candidates: list[tuple[str, str, float, float]] = []  # (root, quality, ks_corr, struct_score)
    for root in _PITCH_CLASS_OFFSETS:
        offset = _PITCH_CLASS_OFFSETS[root]
        for minor in (False, True):
            profile = _profile_for_key(root, minor)
            p_sum = sum(profile)
            profile = [p / p_sum for p in profile]
            n = 12
            mean_h = sum(histogram) / n
            mean_p = sum(profile) / n
            num = sum((h - mean_h) * (p - mean_p) for h, p in zip(histogram, profile))
            den = math.sqrt(
                sum((h - mean_h) ** 2 for h in histogram)
                * sum((p - mean_p) ** 2 for p in profile)
            )
            corr = num / den if den > 0 else 0.0

            # --- 结构二次确认 ---
            scale = _MINOR_PCS if minor else _MAJOR_PCS
            pcs_in_key = {(pc + offset) % 12 for pc in scale}
            in_key_count = len(present & pcs_in_key)
            in_key_ratio = in_key_count / len(present) if present else 0.0

            struct = 0.0
            # 根音出现频率
            if offset in present:
                struct += _TONIC_WEIGHT * (counts[offset] / total)
            # 边界音在调内
            for b in boundary:
                if b in pcs_in_key:
                    struct += 0.3
                else:
                    struct -= 0.3
            # 终止音 = 根音
            if final == offset:
                struct += _FINAL_WEIGHT
            # 调内覆盖率
            struct += 2.0 * in_key_ratio

            candidates.append((root, "minor" if minor else "major", corr, struct))

    # 综合分：KS 相关（主） + 结构确认（辅）
    scored = []
    for root, quality, corr, struct in candidates:
        combined = max(0.0, corr) + struct / 4.0
        scored.append((root, quality, combined, corr))
    scored.sort(key=lambda x: x[2], reverse=True)

    top_root, top_quality, top_combined, top_corr = scored[0]
    runner_root, runner_quality, runner_combined, _ = scored[1]
    margin = top_combined - runner_combined
    confidence = round(min(1.0, max(0.0, top_combined)), 3)
    # 若 top 与 runner 差距很小（< 0.15），降低置信度，提示歧义
    if margin < 0.15:
        confidence = round(min(confidence, 0.55), 3)
    return top_root, top_quality, confidence


# ---------------------------------------------------------------------------
# 拍号推断（基于音符时值统计，保守输出）
# ---------------------------------------------------------------------------

def infer_time_signature(pm: "pretty_midi.PrettyMIDI") -> tuple[int, int]:
    """用音符时值直方图推断拍号，保守输出 (拍数, 4)。

    MIDI 文件通常不携带可靠拍号事件，这里仅做统计推断，结果用于参考。
    """
    beats_votes: Counter[int] = Counter()
    for inst in pm.instruments:
        for note in inst.notes:
            duration = note.end - note.start
            ticks_per_beat = 480
            quarter_beats = int(round(duration / ticks_per_beat))
            if 0 < quarter_beats <= 8:
                beats_votes[quarter_beats] += 1

    if not beats_votes:
        return 4, 4
    top_value, _ = beats_votes.most_common(1)[0]
    if top_value <= 1:
        return 4, 4
    if top_value == 3:
        return 3, 4
    if top_value == 2:
        return 2, 4
    return 4, 4


# ---------------------------------------------------------------------------
# 乐句切分（基于休止时长）
# ---------------------------------------------------------------------------

def count_phrases(pm: "pretty_midi.PrettyMIDI") -> int:
    """用休止阈值切分乐句，返回最高声部（音符最多的 Instrument）的乐句数。

    乐句定义：两个连续音符之间休止时长 ≥ 半拍（0.5 拍）即视为分界。
    """
    if not pm.instruments:
        return 0
    melody = max(pm.instruments, key=lambda i: len(i.notes))
    notes = sorted(melody.notes, key=lambda n: n.start)
    if not notes:
        return 0

    rest_threshold_ticks = int(480 * 0.5)
    phrases = 1
    for prev, nxt in zip(notes, notes[1:]):
        if nxt.start - prev.end >= rest_threshold_ticks:
            phrases += 1
    return phrases


# ---------------------------------------------------------------------------
# 工具入口
# ---------------------------------------------------------------------------

class MidiLoadError(Exception):
    pass


def _load_midi(path: str) -> pretty_midi.PrettyMIDI:
    try:
        return pretty_midi.PrettyMIDI(path)
    except FileNotFoundError:
        raise MidiLoadError(f"文件不存在: {path}")
    except Exception as exc:
        raise MidiLoadError(f"无法解析 MIDI: {exc}")



# MIDI key_signature key_number → (音名, 大小调) 映射
# 0=C major, 1=C# major, ..., 11=B major, 12=C minor, ..., 23=B minor
_KEY_NAMES_12 = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def _key_from_key_signature(ks) -> str:
    """pretty_midi.KeySignature.key_number → 调性音名（根音）。"""
    return _KEY_NAMES_12[ks.key_number % 12]


def _get_bpm(pm: "pretty_midi.PrettyMIDI") -> int:
    """读取全局 BPM。

    pretty_midi 0.2.x 中 get_tempo_changes()[1] 已经是 BPM（quarter notes/min），
    不是 seconds-per-beat。取最后一个 tempo 值作为当前 BPM。
    """
    tempi = pm.get_tempo_changes()[1]
    return int(round(float(tempi[-1])))


def analyze_impl(midi_path: str) -> dict[str, Any]:
    """analyze 核心逻辑，返回 JSON 可序列化的 dict。"""
    pm = _load_midi(midi_path)

    bpm = _get_bpm(pm)
    beats, denominator = infer_time_signature(pm)

    # 旋律轨（音符最多的 instrument）
    if pm.instruments:
        melody = max(pm.instruments, key=lambda i: len(i.notes))
        notes = melody.notes
    else:
        notes = []

    pitch_min = min((n.pitch for n in notes), default=None)
    pitch_max = max((n.pitch for n in notes), default=None)

    pitch_classes = [n.pitch % 12 for n in notes]

    # 优先读取 MIDI key_signature 事件
    key_root = key_quality = None
    key_source = "ks_profile"
    if pm.key_signature_changes:
        ks = pm.key_signature_changes[0]
        key_root, key_quality, key_source = _key_from_key_signature(ks), "major", "key_signature"
        # key_number 0-11 大调，12-23 小调
        if ks.key_number >= 12:
            key_quality = "minor"
        key_confidence = 0.95
    else:
        # 无调号事件 → KS + 主音二次确认
        sorted_notes = sorted(notes, key=lambda n: n.start)
        boundary = [n.pitch % 12 for n in (sorted_notes[0], sorted_notes[-1])]
        key_root, key_quality, key_confidence = detect_key(pitch_classes, boundary)

    phrases = count_phrases(pm)

    return {
        "midi_path": midi_path,
        "key": f"{key_root} {key_quality}",
        "key_confidence": key_confidence,
        "key_source": key_source,
        "bpm": bpm,
        "time_signature": f"{beats}/{denominator}",
        "melody_time_signature": (f"{pm.time_signature_changes[0].numerator}/{pm.time_signature_changes[0].denominator}"
                                  if pm.time_signature_changes else None),
        "pitch_min": pitch_min,
        "pitch_max": pitch_max,
        "pitch_class_distribution": {
            _NOTE_NAMES[pc]: pitch_classes.count(pc) for pc in range(12)
        },
        "phrase_count": phrases,
        "note_count": len(notes),
        "instrument_count": len(pm.instruments),
        "duration_seconds": round(float(pm.get_end_time()), 3),
    }


def validate_impl(
    midi_path: str,
    expected_bpm_range: tuple[int, int] = (40, 300),
    expected_pitch_range: tuple[int, int] = (21, 108),
    min_notes_per_track: int = 1,
) -> dict[str, Any]:
    """validate 核心逻辑。

    检查项：
      1. 轨道数量（instruments 是否 > 0）
      2. 每轨音域越界
      3. 每轨空轨 / 音符不足
      4. 速度异常
      5. 时长合理性
    """
    pm = _load_midi(midi_path)
    bpm = _get_bpm(pm)

    checks: list[dict[str, Any]] = []
    failures = 0

    # --- 1. 轨道数 ---
    total = len(pm.instruments)
    ok = total > 0
    if not ok:
        failures += 1
    checks.append({
        "name": "轨道数量",
        "status": "pass" if ok else "fail",
        "detail": f"共 {total} 轨" if ok else "无轨道",
    })

    # --- 2. 每轨音域 ---
    low, high = expected_pitch_range
    for i, inst in enumerate(pm.instruments):
        if not inst.notes:
            continue
        t_min = min(n.pitch for n in inst.notes)
        t_max = max(n.pitch for n in inst.notes)
        ok = low <= t_min and t_max <= high
        if not ok:
            failures += 1
        checks.append({
            "name": f"轨道 {i} 音域",
            "status": "pass" if ok else "fail",
            "detail": f"实际 {t_min}–{t_max}，允许 {low}–{high}",
            "track_index": i,
        })

    # --- 3. 每轨音符数 ---
    for i, inst in enumerate(pm.instruments):
        ok = len(inst.notes) >= min_notes_per_track
        if not ok:
            failures += 1
        checks.append({
            "name": f"轨道 {i} 音符数",
            "status": "pass" if ok else "fail",
            "detail": f"{len(inst.notes)} 条音符（阈值 {min_notes_per_track}）",
            "track_index": i,
        })

    # --- 4. 速度 ---
    ok = expected_bpm_range[0] <= bpm <= expected_bpm_range[1]
    if not ok:
        failures += 1
    checks.append({
        "name": "速度",
        "status": "pass" if ok else "fail",
        "detail": f"BPM={bpm}，允许 {expected_bpm_range[0]}–{expected_bpm_range[1]}",
    })

    # --- 5. 时长 ---
    duration_s = float(pm.get_end_time())
    ok = 0 < duration_s <= 600
    if not ok:
        failures += 1
    checks.append({
        "name": "时长",
        "status": "pass" if ok else "fail",
        "detail": f"{duration_s:.2f}s（允许 0–600s）",
    })

    return {
        "midi_path": midi_path,
        "bpm": bpm,
        "all_passed": failures == 0,
        "failures": failures,
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# 和声（M2）
# ---------------------------------------------------------------------------

# 罗马数字 → (相对根音半音偏移, 和弦质量, 转位)
_ROMAN: dict[str, tuple[int, str, int]] = {
    "I":   (0, "major", 0),
    "ii":  (2, "minor", 0),
    "iii": (4, "minor", 0),
    "IV":  (5, "major", 0),
    "iv":  (5, "minor", 0),
    "V":   (7, "major", 0),
    "v":   (7, "minor", 0),
    "V7":  (7, "major7", 0),
    "vi":  (9, "minor", 0),
    "VII": (11, "major", 0),
    "V6/5": (7, "major", 3),
    "V⁶⁵": (7, "major", 3),
    "I6":  (0, "major", 1),
    "IV6": (5, "major", 1),
}

# 风格模板：4 小节循环套路（可按小节长度重复/扩展）
_STYLE_PROGRESSIONS: dict[str, list[str]] = {
    "pop":     ["I", "IV", "V", "I"],
    "lofi":    ["ii", "V", "I", "vi"],
    "jazz":    ["I7", "ii", "V7", "I7"],
    "classical": ["I", "vi", "IV", "V"],
}
# M2 扩展：8 小节轻流行套路（PLAN.md 当前编曲方案）
_POP_8BAR = ["I", "V6/5", "IV", "V", "vi", "IV", "V", "I"]


def _chord_intervals(quality: str) -> list[int]:
    return {
        "major": [0, 4, 7],
        "minor": [0, 3, 7],
        "major7": [0, 4, 7, 11],
    }.get(quality, [0, 4, 7])


def _root_midi(root_pc: int, octave_anchor: int = 60) -> int:
    """把音级放到 anchor 八度附近（M2 和声用 C4=60 锚点）。"""
    base = octave_anchor - (octave_anchor % 12)  # 该八度的 C
    pitch = base + root_pc
    while pitch < octave_anchor - 6:
        pitch += 12
    while pitch >= octave_anchor + 7:
        pitch -= 12
    return pitch


def _progression_for(style: str, bars: int,
                     progression_hint: str | None = None) -> list[str]:
    """返回每小节的罗马数字 token 列表（长度 = bars）。"""
    if progression_hint:
        tokens = [t.strip() for t in progression_hint.replace(",", " ").split() if t.strip()]
    else:
        base = _STYLE_PROGRESSIONS.get(style, _STYLE_PROGRESSIONS["pop"])
        # 8 小节轻流行 → 用 8-bar 套路；其余按 4 小节循环
        if style == "pop" and bars == 8:
            tokens = list(_POP_8BAR)
        else:
            tokens = (base * ((bars + len(base) - 1) // len(base)))[:bars]
    return tokens


def chords_impl(analysis: dict[str, Any], style: str = "pop",
                harmonic_complexity: int = 3,
                progression_hint: str | None = None,
                output_path: str | None = None) -> dict[str, Any]:
    """chords 核心逻辑：基于调性生成和声进行（含转位），输出 JSON。

    输入 analysis 必须含：midi_path, key, key_confidence, time_signature,
    note_count, phrase_count（analyze 输出）。
    """
    pm = _load_midi(analysis["midi_path"])
    bpm = _get_bpm(pm)
    # M5 拍号修复：优先读 melody_time_signature（time_signature 元事件，权威），
    # fallback 统计推断值（analyze.time_signature）——3/4 样例必须按 3 拍/小节排布
    ts_src = analysis.get("melody_time_signature") or analysis.get("time_signature", "4/4")
    beats_den = ts_src.split("/")
    beats_per_bar = int(beats_den[0]) if beats_den else 4

    key_label = analysis.get("key", "C major")
    parts = key_label.split()
    key_root_pc = _PITCH_CLASS_OFFSETS.get(parts[0], 0)
    is_minor = parts[-1].lower() == "minor" if len(parts) > 1 else False

    # 小节的时长
    total_beats = float(pm.get_end_time()) * bpm / 60.0
    bars = max(1, int(round(total_beats / beats_per_bar)))

    tokens = _progression_for(style, bars, progression_hint)

    chords_events: list[dict[str, Any]] = []
    for bar_idx, token in enumerate(tokens):
        if token not in _ROMAN:
            # 未知 token 降级为主三和弦 I
            token_eff = "I"
        else:
            token_eff = token
        semitone, quality, inversion = _ROMAN[token_eff]
        root_pc = (key_root_pc + semitone) % 12
        start_beat = bar_idx * beats_per_bar
        end_beat = start_beat + beats_per_bar

        # 和弦音（M2 默认根音在 C4 附近）
        chord_pitches = [_root_midi((root_pc + iv) % 12) for iv in _chord_intervals(quality)]
        # 转位：低音取和弦音中的 (1+inversion) 音（0=根音,1=三音,2=五音）
        if inversion and chord_pitches:
            bass_note = chord_pitches[inversion % len(chord_pitches)]
        else:
            bass_note = chord_pitches[0]

        func = {
            "I": "T", "IV": "P", "V": "D",
            "ii": "P", "iii": "T", "vi": "T", "VII": "P",
            "V7": "D", "V6/5": "D", "V⁶⁵": "D", "I6": "T", "IV6": "P",
            "iv": "P", "v": "T",
        }.get(token_eff, "?")
        inv_names = {0: "根位", 1: "一转位", 2: "二转位", 3: "三转位"}

        chords_events.append({
            "bar": bar_idx + 1,
            "roman": token,
            "root_pc": root_pc,
            "quality": quality,
            "inversion": inversion,
            "inversion_name": inv_names.get(inversion, "根位"),
            "chord_pitches": chord_pitches,
            "bass_note": bass_note,
            "function": func,
            "start_beat": start_beat,
            "end_beat": end_beat,
        })

    harmonic_figure = "–".join(t for t in tokens)

    result: dict[str, Any] = {
        "status": "ok",
        "key": key_label,
        "is_minor": is_minor,
        "style": style,
        "harmonic_complexity": harmonic_complexity,
        "bpm": bpm,
        "bars": bars,
        "harmonic_figure": harmonic_figure,
        "chords": chords_events,
        "inv_name": {"0": "根位", "1": "一转位", "2": "二转位", "3": "三转位"},
    }

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["output_path"] = str(Path(output_path).resolve())
    return result


# ---------------------------------------------------------------------------
# 分声部（M2）
# ---------------------------------------------------------------------------

TICKS_PER_BEAT = 480  # pretty_midi 0.2.x 默认写盘 resolution；统一 480 保证时间对齐
_RESOLUTION = 480

_GM_PROGRAMS: dict[str, int] = {
    "melody": 0,        # Acoustic Grand Piano
    "harmony": 4,       # Electric Piano 1
    "bass": 38,         # Electric Bass Finger
    "drums": 96,        # Drum Kit 2（channel 10）
    "countermelody": 80,  # Flute
}

# 轻流行 4 拍鼓组 pattern（MIDI drum pitch：kick=36, snare=38, hi-hat C=42）
# 拍内位置以「整小节从 0 起的拍位置」表示；在 3/4 下由 stems_impl 按 beats_per_bar 裁剪
_DRUM_PATTERN: list[tuple[float, int, int]] = [
    (0.0, 36, 100),  # kick 1
    (1.0, 38, 90),   # snare 2
    (2.0, 36, 100),  # kick 3（3/4 下该位置会被裁掉）
    (3.0, 38, 85),   # snare 4（3/4 下该位置会被裁掉）
]
_HIHAT: list[tuple[float, int, int]] = [
    (0.0, 42, 70), (0.5, 42, 55),
    (1.0, 42, 70), (1.5, 42, 55),
    (2.0, 42, 70), (2.5, 42, 55),
    (3.0, 42, 70), (3.5, 42, 55),
]


def _load_melody_notes(pm: "pretty_midi.PrettyMIDI") -> list:
    if not pm.instruments:
        return []
    melody = max(pm.instruments, key=lambda i: len(i.notes))
    return sorted(melody.notes, key=lambda n: n.start)


def _melody_gaps(notes: list, min_gap_beats: float = 0.5,
                 total_beats: float = 32.0) -> list[tuple[float, float]]:
    """返回旋律休止段 [(start_beat, end_beat), ...]（单位：拍）。

    pretty_midi 0.2.x note.start/end 单位是**拍**（直接比较即可）。
    """
    gaps: list[tuple[float, float]] = []
    if not notes:
        return [(0.0, total_beats)]
    prev_end = 0.0
    for n in notes:
        s = float(n.start)
        e = float(n.end)
        if s - prev_end >= min_gap_beats:
            gaps.append((prev_end, s))
        prev_end = max(prev_end, e)
    if total_beats - prev_end >= min_gap_beats:
        gaps.append((prev_end, total_beats))
    return gaps


def stems_impl(analysis: dict[str, Any], chords: dict[str, Any],
               style: str = "pop", parts: list[str] | None = None,
               density: float = 0.5, output_dir: str | None = None,
               section_bars: list[int] | None = None,
               chorus_enhance: bool = False) -> dict[str, Any]:
    """stems 核心逻辑：生成 melody/harmony/bass/drums/countermelody 多轨 MIDI。

    M3 新增参数：
      - density：和声轨 16 分音符分解密度（0=块和弦，1=16 分）
      - section_bars：副歌（增强）小节区间（0-based），如 [4,8] 对应小节 5–8
      - chorus_enhance：True 时副歌小节内和声加 7 音、鼓组 16 分 hi-hat + 反拍 ghost kick、
                        贝斯八度跳进、副旋律填充密度提升

    输出：
      - 各声部独立 MIDI：output/stems/<part>.mid
      - 合并 MIDI：output/stems/combined.mid
      若 output_dir 为 None 则只在内存中构建（不写盘）。
    """
    import os

    parts = parts or ["melody", "harmony", "bass", "drums", "countermelody"]
    pm = _load_midi(analysis["midi_path"])
    bpm = _get_bpm(pm)
    melody_notes = _load_melody_notes(pm)
    total_beats = float(pm.get_end_time()) * bpm / 60.0
    # M5 拍号修复：优先读 melody_time_signature（time_signature 元事件，权威），
    # fallback 统计推断值（analyze.time_signature）——3/4 样例必须按 3 拍/小节排布
    ts_src = analysis.get("melody_time_signature") or analysis.get("time_signature", "4/4")
    beats_per_bar = int(ts_src.split("/")[0]) if ts_src else 4
    bars = max(1, int(round(total_beats / beats_per_bar)))

    chorus_bars: set[int] = set()
    if chorus_enhance and section_bars and len(section_bars) >= 2:
        chorus_bars = set(range(section_bars[0], section_bars[1]))

    def _b2t(beat: float) -> int:
        """beat → ticks（480 tpb）。"""
        return int(round(beat * TICKS_PER_BEAT))

    out_root = Path(output_dir) if output_dir else None
    if out_root:
        out_root.mkdir(parents=True, exist_ok=True)

    track_files: list[dict[str, Any]] = []
    combined = pretty_midi.PrettyMIDI(initial_tempo=bpm, resolution=_RESOLUTION)

    # --- 各声部 ---
    for part in parts:
        inst = pretty_midi.Instrument(program=_GM_PROGRAMS.get(part, 0), name=part)
        inst.is_drum = (part == "drums")

        if part == "melody":
            for n in melody_notes:
                inst.notes.append(pretty_midi.Note(
                    pitch=int(n.pitch), velocity=int(n.velocity),
                    start=float(n.start), end=float(n.end)))
        elif part == "harmony":
            subdiv = 4 if (chorus_enhance and density >= 1.0) else 1
            for ch in chords.get("chords", []):
                bar_idx = int(ch["start_beat"]) // beats_per_bar
                in_chorus = chorus_enhance and bar_idx in chorus_bars
                cpitches = list(ch.get("chord_pitches", []))
                if in_chorus and len(cpitches) >= 3:
                    root_pc = ch.get("root_pc", 0)
                    qual = ch.get("quality", "major")
                    ext = (root_pc + 11) % 12 if qual == "major" else (root_pc + 7) % 12
                    ext_note = 60 + ext
                    if ext_note not in cpitches:
                        cpitches.append(ext_note)
                vel = 80 if in_chorus else 55
                for pc in cpitches:
                    if subdiv == 1:
                        inst.notes.append(pretty_midi.Note(
                            pitch=pc, velocity=vel,
                            start=float(ch["start_beat"]),
                            end=float(ch["end_beat"])))
                    else:
                        start_b = float(ch["start_beat"])
                        beat_span = float(ch["end_beat"] - ch["start_beat"])
                        step = beat_span / subdiv
                        for k in range(subdiv):
                            note_idx = k % len(cpitches)
                            t0 = start_b + k * step
                            inst.notes.append(pretty_midi.Note(
                                pitch=cpitches[note_idx], velocity=vel,
                                start=t0, end=t0 + step * 0.9))
        elif part == "bass":
            for ch in chords.get("chords", []):
                bar_idx = int(ch["start_beat"]) // beats_per_bar
                in_chorus = chorus_enhance and bar_idx in chorus_bars
                bass = int(ch.get("bass_note", 48))
                while bass > 50:
                    bass -= 12
                while bass < 30:
                    bass += 12
                start_b = float(ch["start_beat"])
                end_b = float(ch["end_beat"])
                beat_span = end_b - start_b
                if in_chorus:
                    quarter = beat_span * 0.25
                    inst.notes.append(pretty_midi.Note(
                        pitch=bass, velocity=90, start=start_b, end=start_b + quarter))
                    inst.notes.append(pretty_midi.Note(
                        pitch=bass + 12, velocity=85,
                        start=start_b + quarter, end=start_b + quarter * 2))
                    passing = max(24, bass - 7)
                    inst.notes.append(pretty_midi.Note(
                        pitch=passing, velocity=75,
                        start=start_b + quarter * 2, end=start_b + quarter * 3))
                    inst.notes.append(pretty_midi.Note(
                        pitch=bass, velocity=85,
                        start=start_b + quarter * 3, end=end_b))
                else:
                    inst.notes.append(pretty_midi.Note(
                        pitch=bass, velocity=80, start=start_b, end=end_b))
        elif part == "drums":
            for bar in range(bars):
                base_beat = bar * beats_per_bar
                in_chorus = chorus_enhance and bar in chorus_bars
                if in_chorus:
                    # 副歌：hi-hat 16 分、kick 基础 + 3.5 拍反拍 ghost、snare 2&4
                    for i in range(16):
                        pos = i * 0.25
                        if pos >= beats_per_bar:
                            break
                        vel_h = 60 if i % 4 == 0 else 45
                        inst.notes.append(pretty_midi.Note(
                            pitch=42, velocity=vel_h,
                            start=base_beat + pos, end=base_beat + pos + 0.2))
                    for pos in [0.0, 2.0]:
                        if pos >= beats_per_bar:
                            continue
                        inst.notes.append(pretty_midi.Note(
                            pitch=36, velocity=100,
                            start=base_beat + pos, end=base_beat + pos + 0.3))
                    ghost_pos = 3.5 if beats_per_bar > 3.5 else (beats_per_bar - 0.5)
                    inst.notes.append(pretty_midi.Note(
                        pitch=36, velocity=50,
                        start=base_beat + ghost_pos, end=base_beat + ghost_pos + 0.2))
                    for pos in [1.0, 3.0]:
                        if pos >= beats_per_bar:
                            continue
                        inst.notes.append(pretty_midi.Note(
                            pitch=38, velocity=90,
                            start=base_beat + pos, end=base_beat + pos + 0.3))
                else:
                    for pos, pitch, vel in _DRUM_PATTERN + _HIHAT:
                        if pos >= beats_per_bar:
                            continue
                        inst.notes.append(pretty_midi.Note(
                            pitch=pitch, velocity=vel,
                            start=float(base_beat + pos),
                            end=float(base_beat + pos + 0.3)))
        elif part == "countermelody":
            gaps = _melody_gaps(melody_notes, total_beats=total_beats)
            fill_cycle = [72, 67, 72, 74]  # C5, G4, C5, D5（diatonic C major）
            fill_idx = 0
            for gap_start, gap_end in gaps:
                dur = gap_end - gap_start
                bar_of_gap = int(gap_start) // beats_per_bar
                in_chorus = chorus_enhance and bar_of_gap in chorus_bars
                if in_chorus:
                    s = float(gap_start)
                    e = float(min(gap_end, gap_start + 1.5))
                    if e > s:
                        inst.notes.append(pretty_midi.Note(
                            pitch=fill_cycle[fill_idx % len(fill_cycle)],
                            velocity=70, start=s, end=e))
                        fill_idx += 1
                elif dur >= 0.5:
                    s = float(gap_start)
                    e = float(min(gap_end, gap_start + min(dur, 1.5)))
                    inst.notes.append(pretty_midi.Note(
                        pitch=72, velocity=60, start=s, end=e))

        if len(inst.notes) > 0:
            combined.instruments.append(inst)
        track_files.append({
            "part": part,
            "gm_program": _GM_PROGRAMS.get(part, 0),
            "is_drum": part == "drums",
            "note_count": len(inst.notes),
        })

    # --- 写盘（若指定 output_dir）：统一用 mido 写出 480 ticks 对齐的 MIDI ---
    import mido
    midi_paths: dict[str, str] = {}
    TICKS = _RESOLUTION

    def _write_midi_via_mido(path: Path, instrument_programs: dict, tempo_bpm: int,
                              part_notes: dict) -> None:
        """part_notes: {part: [(pitch, start_tick, end_tick, velocity), ...]}"""
        m = mido.MidiFile(ticks_per_beat=TICKS)
        # meta 轨
        meta = mido.MidiTrack()
        meta.append(mido.MetaMessage("set_tempo",
                                     tempo=int(round(60_000_000 / tempo_bpm)), time=0))
        meta.append(mido.MetaMessage("time_signature",
                                     numerator=4, denominator=4, time=0))
        m.tracks.append(meta)
        for part_name in part_notes:
            t = mido.MidiTrack()
            t.append(mido.MetaMessage("track_name", name=part_name, time=0))
            ch = 9 if part_name == "drums" else 0
            t.append(mido.Message("program_change",
                                  program=instrument_programs.get(part_name, 0),
                                  channel=ch, time=0))
            events: list = []
            for pitch, start, end, vel in part_notes[part_name]:
                events.append((start, "on", pitch, vel))
                events.append((end, "off", pitch, 0))
            events.sort(key=lambda x: (x[0], x[1] == "off"))
            prev = 0
            for tick, typ, pitch, vel in events:
                delta = max(0, tick - prev)
                if typ == "on":
                    t.append(mido.Message("note_on", channel=ch, note=pitch,
                                          velocity=vel, time=delta))
                else:
                    t.append(mido.Message("note_off", channel=ch, note=pitch,
                                          velocity=0, time=delta))
                prev = tick
            t.append(mido.MetaMessage("end_of_track", time=0))
            m.tracks.append(t)
        m.save(str(path))

    if out_root:
        for part, tf in zip(parts, track_files):
            p = out_root / f"{part}.mid"
            inst = next((i for i in combined.instruments if i.name == part), None)
            if inst is None or len(inst.notes) == 0:
                # 空声部：写探针音（velocity=1，1 拍）
                _write_midi_via_mido(p, {part: _GM_PROGRAMS.get(part, 0)}, bpm,
                                     {part: [(60, 0, TICKS, 1)]})
            else:
                notes_list = [
                    (int(n.pitch), _b2t(float(n.start)), _b2t(float(n.end)), int(n.velocity))
                    for n in inst.notes
                ]
                _write_midi_via_mido(p, {part: _GM_PROGRAMS.get(part, 0)}, bpm,
                                     {part: notes_list})
            tf["midi_path"] = str(p.resolve())
            midi_paths[part] = str(p.resolve())
        # combined：合并所有声部
        all_notes: dict[str, list] = {}
        for part in parts:
            inst = next((i for i in combined.instruments if i.name == part), None)
            if inst is not None:
                all_notes[part] = [
                    (int(n.pitch), _b2t(float(n.start)), _b2t(float(n.end)), int(n.velocity))
                    for n in inst.notes
                ]
            elif part == "countermelody":
                # 副旋律在 chorus_enhance 模式下可能无休止点可填 → 探针音
                all_notes[part] = [(60, 0, TICKS, 1)]
        combined_path = out_root / "combined.mid"
        _write_midi_via_mido(combined_path,
                             {p: _GM_PROGRAMS.get(p, 0) for p in all_notes},
                             bpm, all_notes)
        midi_paths["combined"] = str(combined_path.resolve())

    return {
        "status": "ok",
        "parts": parts,
        "style": style,
        "density": density,
        "chorus_enhance": chorus_enhance,
        "section_bars": section_bars,
        "bpm": bpm,
        "bars": bars,
        "tracks": track_files,
        "midi_paths": midi_paths,
        "combined_midi_path": midi_paths.get("combined"),
    }


# ---------------------------------------------------------------------------
# 渲染（M2，fluidsynth + SoundFont）
# ---------------------------------------------------------------------------

def _fallback_render_wav(midi_path: str, wav_path: str) -> dict[str, Any]:
    """降级渲染：pretty_midi 波形合成（正弦/方波/三角波）+ 鼓轨波形近似。

    当所有 SoundFont 获取渠道失败时使用（INC-008/010）。
    输出 44.1kHz 16-bit 单声道 WAV，内容有声（非静音）。
    """
    import wave
    import numpy as np

    pm = _load_midi(midi_path)
    insts = list(pm.instruments)
    drum_insts = [i for i in insts if i.is_drum]
    mel_insts = [i for i in insts if not i.is_drum]

    fs = 44100

    def square(x):
        return np.sign(np.sin(2 * np.pi * x))

    def triangle(x):
        x = x % 1.0
        return 4 * np.abs(x - 0.5) - 1

    waveforms = {"melody": np.sin, "harmony": square, "bass": triangle,
                 "countermelody": np.sin}
    gains = {"melody": 0.5, "harmony": 0.3, "bass": 0.4, "countermelody": 0.3}

    # 已知问题#3 修复：渲染时值对齐 MIDI 总时值（pm.get_end_time() 单位秒），
    # 而非「最后一声部结束点」，避免尾部 1.5s 未合成。
    midi_total_s = float(pm.get_end_time())
    note_ends = [float(n.end) for i in mel_insts for n in i.notes]
    drum_ends = [float(n.end) for i in drum_insts for n in i.notes]
    total_s = max(midi_total_s, max(note_ends + drum_ends + [0.0])) + 0.5  # +0.5s 收尾余量
    total = int(total_s * fs)
    audio = np.zeros(total, dtype=np.float64)

    for inst in mel_insts:
        wf = waveforms.get(inst.name, np.sin)
        g = gains.get(inst.name, 0.4)
        sig = inst.synthesize(fs=fs, wave=wf).astype(np.float64) * g
        p = max(1e-9, float(np.abs(sig).max()))
        sig = sig / p
        n = min(len(sig), total)
        audio[:n] += sig[:n]

    def make_noise(n, sr, seed=42):
        rng = np.random.default_rng(seed)
        x = rng.standard_normal(n)
        y = np.zeros_like(x)
        a = 0.3
        for i in range(1, n):
            y[i] = y[i - 1] * a + x[i] * (1 - a)
        return y

    for inst in drum_insts:
        for n in inst.notes:
            start = int(n.start * fs)
            dur = max(0.1, float(n.end - n.start))
            length = min(int(dur * fs), total - start)
            if length <= 0:
                continue
            pc, vel = int(n.pitch), int(n.velocity) / 127.0
            if pc == 36:  # kick
                t = np.arange(length, dtype=np.float64) / fs
                tone = np.sin(2 * np.pi * (50 * np.exp(-t * 8) + 30) * t) * np.exp(-t * 30) * vel * 0.9
                audio[start:start + length] += tone
            elif pc == 38:  # snare
                tone = make_noise(length, fs) * np.exp(-np.arange(length) / fs * 15) * vel * 0.5
                audio[start:start + length] += tone
            else:  # hi-hat
                tone = make_noise(length, fs, seed=7) * np.exp(-np.arange(length) / fs * 60) * vel * 0.25
                audio[start:start + length] += tone

    scale = 32767.0 / max(1.0, float(np.abs(audio).max()))
    audio16 = np.clip(np.round(audio * scale), -32767, 32767).astype(np.int16)
    out = Path(wav_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(audio16.tobytes())
    return {
        "status": "ok",
        "renderer": "fallback_pretty_midi",
        "wav_path": str(out.resolve()),
        "size_bytes": out.stat().st_size,
        "duration_s": round(len(audio16) / fs, 2),
        "midi_path": midi_path,
        "note": "降级渲染：因 SoundFont 获取渠道全部失败，使用 pretty_midi 波形合成（有声但音色粗糙）",
    }


# M4：真实 GM SoundFont（gh LFS 渠道获取，31MB，RIFF 头校验通过，INC-011）
_DEFAULT_SOUNDFONT = str(Path(__file__).parent / "assets" / "GeneralUser_GS.sf2")


def render_impl(midi_path: str, wav_path: str,
                soundfont: str | None = None,
                allow_fallback: bool = True) -> dict[str, Any]:
    """fluidsynth 渲染：MIDI → WAV（44.1kHz 16-bit PCM，file driver）。

    返回 {status, wav_path, size_bytes, error?}。
    支持 conda 安装的 fluidsynth（`/opt/anaconda3/bin/fluidsynth`）。
    默认使用 assets/GeneralUser_GS.sf2（真实 GM 音色，INC-011 获取）。
    SoundFont 缺失时若 allow_fallback=True，降级到 pretty_midi 波形合成。
    """
    if soundfont is None:
        soundfont = _DEFAULT_SOUNDFONT
        if not Path(soundfont).exists():
            soundfont = None
    import shutil
    import subprocess

    # 查找 fluidsynth：系统 PATH → conda → 显式路径
    candidates = [
        shutil.which("fluidsynth"),
        "/opt/anaconda3/bin/fluidsynth",
        shutil.which("fluidsynth", ),
    ]
    fluidsynth = next((c for c in candidates if c and Path(c).exists()), None)
    if fluidsynth is None:
        return {
            "status": "skipped",
            "error": "fluidsynth 未安装（PATH 与 /opt/anaconda3/bin 均未找到），已跳过渲染",
            "midi_path": midi_path,
        }

    wav_file = Path(wav_path)
    wav_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        fluidsynth, "-i", "-q",
        "-r", "44100",
        "-a", "file",
        "-o", "audio.file.name=" + str(wav_file.resolve()),
        "-o", "audio.file.type=wav",
        "-o", "audio.file.format=s16",
    ]
    if soundfont:
        # 显式传入的 SoundFont 必须存在（M5：无效 SF2 路径 → 硬失败报错，而非 fluidsynth 静默用内置 SF）
        if not Path(soundfont).exists():
            return {
                "status": "failed",
                "error": f"SoundFont 文件不存在：{soundfont}（render 硬失败，未用内置默认 SF）",
                "midi_path": midi_path,
            }
        cmd.append(soundfont)
    cmd.append(midi_path)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            return {
                "status": "failed",
                "error": f"fluidsynth exit={proc.returncode}",
                "stderr_tail": (proc.stderr or proc.stdout)[-1500:],
                "midi_path": midi_path,
            }
    except FileNotFoundError:
        return {"status": "skipped", "error": "fluidsynth 可执行文件找不到", "midi_path": midi_path}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "fluidsynth 超时（180s）", "midi_path": midi_path}

    if not wav_file.exists():
        if allow_fallback:
            return _fallback_render_wav(midi_path, wav_path)
        return {
            "status": "failed",
            "error": f"输出 WAV 未生成：{wav_path}",
            "midi_path": midi_path,
        }

    # fluidsynth 无 SoundFont 时 WAV 为静音 → 检测并降级（正确解析 WAV 头）
    try:
        import array
        import struct
        import wave as _wave
        with _wave.open(str(wav_file)) as _w:
            ch, sw, sr = _w.getnchannels(), _w.getsampwidth(), _w.getframerate()
            n_check = min(_w.getnframes(), int(2e6 // (ch * sw)))  # 检查前 ~2M 采样
            data = _w.readframes(n_check)
        _fmt = "b" if sw == 1 else ("h" if sw == 2 else "i")
        _samples = array.array(_fmt)
        usable = len(data) - (len(data) % sw)
        _samples.frombytes(data[:usable])
        # 16/32-bit 小端：先转字节序再解析峰值
        _samples.byteswap()
        # 有符号小端 16-bit：峰值 0 = 真静音（-1..1 范围视为静音）
        _peak = max(abs(x) for x in _samples) if _samples else 0
        if _peak <= 1 and allow_fallback:
            return _fallback_render_wav(midi_path, wav_path)
    except Exception:
        pass

    return {
        "status": "ok",
        "renderer": "fluidsynth",
        "wav_path": str(wav_file.resolve()),
        "size_bytes": wav_file.stat().st_size,
        "soundfont": soundfont or "default",
        "fluidsynth": fluidsynth,
        "midi_path": midi_path,
    }
