"""生成 test.mid：C 大调、90 BPM、4/4、8 小节简短旋律。

旋律设计（C 大调，C4=60）：
  小节 1–2：C D E F  G F E D   （拱形上行）
  小节 3–4：E F G A  G F E D   （围绕 IV 级）
  小节 5–6：D E F G  F E D C   （下行回归）
  小节 7–8：C C E G  C5 E C   （主→属→主收尾）

meta 事件（用 mido 写入）：
  - set_tempo 90 BPM
  - time_signature 4/4
  - key_signature C major（0 升降号）

轨 0：旋律（program 0）
轨 1：EmptyProbe 探针轨（1 条 velocity=1 的静音符，验证 validate 空轨检查）
"""
from __future__ import annotations

import sys

import mido

BPM = 90
TICKS_PER_BEAT = 480

_NAME_TO_MIDI = {
    "C4": 60, "D4": 62, "E4": 64, "F4": 65, "G4": 67, "A4": 69, "C5": 72,
}

# (小节, 小节内起点拍, 时值拍, 音名, velocity)
_MELDY: list[tuple[int, float, float, str, int]] = [
    # 小节 1
    (0, 0, 1, "C4", 80), (0, 1, 1, "D4", 80), (0, 2, 1, "E4", 90), (0, 3, 1, "F4", 80),
    # 小节 2
    (1, 0, 1, "G4", 90), (1, 1, 1, "F4", 80), (1, 2, 1, "E4", 70), (1, 3, 1, "D4", 70),
    # 小节 3
    (2, 0, 1, "E4", 80), (2, 1, 1, "F4", 80), (2, 2, 1, "G4", 90), (2, 3, 1, "A4", 80),
    # 小节 4
    (3, 0, 1, "G4", 80), (3, 1, 1, "F4", 70), (3, 2, 1, "E4", 70), (3, 3, 1, "D4", 60),
    # 小节 5
    (4, 0, 0.5, "D4", 80), (4, 0.5, 0.5, "E4", 80), (4, 1, 1, "F4", 90),
    (4, 2, 1, "G4", 90), (4, 3, 1, "F4", 80),
    # 小节 6
    (5, 0, 1, "E4", 80), (5, 1, 1, "D4", 70), (5, 2, 1, "C4", 60), (5, 3, 1, "C4", 50),
    # 小节 7
    (6, 0, 1, "C4", 70), (6, 1, 1, "C4", 70), (6, 2, 1, "E4", 80), (6, 3, 1, "G4", 90),
    # 小节 8
    (7, 0, 1, "C5", 90), (7, 1, 1, "C5", 80), (7, 2, 1, "E4", 70), (7, 3, 1, "C4", 60),
]


def _note_list() -> list[tuple[int, int, int, int]]:
    """返回 [(pitch, start_tick, end_tick, velocity), ...]。"""
    out: list[tuple[int, int, int, int]] = []
    for bar, start_in_bar, dur, name, vel in _MELDY:
        pitch = _NAME_TO_MIDI[name]
        start_tick = int((bar * 4 + start_in_bar) * TICKS_PER_BEAT)
        end_tick = start_tick + int(dur * TICKS_PER_BEAT)
        out.append((pitch, start_tick, end_tick, vel))
    return out


def generate_test_midi(output_path: str = "test.mid") -> None:
    m = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)

    # meta 轨：tempo / time signature / key signature（C major，0 升降号）
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("set_tempo", tempo=int(round(60_000_000 / BPM)), time=0))
    meta.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    meta.append(mido.MetaMessage("key_signature", key="C", time=0))
    m.tracks.append(meta)

    # 旋律轨
    t = mido.MidiTrack()
    t.append(mido.MetaMessage("track_name", name="Melody", time=0))
    t.append(mido.Message("program_change", program=0, channel=0, time=0))
    prev_tick = 0
    for pitch, start_tick, end_tick, vel in _note_list():
        t.append(mido.Message("note_on", channel=0, note=pitch,
                              velocity=vel, time=max(0, start_tick - prev_tick)))
        hold = end_tick - start_tick
        if hold > 0:
            t.append(mido.Message("note_off", channel=0, note=pitch,
                                  velocity=0, time=hold))
        prev_tick = end_tick
    t.append(mido.MetaMessage("end_of_track", time=0))
    m.tracks.append(t)

    # 探针轨：1 条 velocity=1（实际静音效果）的长音符，供 validate 空轨检查
    p = mido.MidiTrack()
    p.append(mido.MetaMessage("track_name", name="EmptyProbe", time=0))
    p.append(mido.Message("program_change", program=40, channel=0, time=0))
    p.append(mido.Message("note_on", channel=0, note=60, velocity=1, time=0))
    p.append(mido.Message("note_off", channel=0, note=60, velocity=0, time=32 * TICKS_PER_BEAT))
    p.append(mido.MetaMessage("end_of_track", time=0))
    m.tracks.append(p)

    m.save(output_path)
    print(f"test.mid 已生成：{output_path}，共 {len(_MELDY)} 条旋律音，BPM={BPM}，"
          f"含 C major key_signature meta")


# 参数化：默认 C 大调 4/4（M2 兼容），3/4 走 write-path 复测
_BARS_34 = 4  # 3/4 下共 4 小节 = 12 拍

def generate_34_midi(output_path: str = "test-34.mid", bpm: int = 90,
                      bars: int = _BARS_34) -> None:
    """生成 3/4 拍 C 大调样例（写路径复测用）：时值 3 拍/小节。

    与 generate_test_midi 的区别：time_signature 元事件写 3/4，旋律每小节 3 拍。
    """
    m = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("set_tempo", tempo=int(round(60_000_000 / bpm)), time=0))
    meta.append(mido.MetaMessage("time_signature", numerator=3, denominator=4, time=0))
    meta.append(mido.MetaMessage("key_signature", key="C", time=0))
    m.tracks.append(meta)

    names = ["C4", "D4", "E4", "F4", "G4", "A4"]
    t = mido.MidiTrack()
    t.append(mido.MetaMessage("track_name", name="Melody", time=0))
    t.append(mido.Message("program_change", program=0, channel=0, time=0))
    prev_tick = 0
    for bar in range(bars):
        for i in range(3):
            pitch = _NAME_TO_MIDI[names[(bar * 3 + i) % len(names)]]
            start_tick = int((bar * 3 + i) * TICKS_PER_BEAT)
            end_tick = start_tick + TICKS_PER_BEAT
            t.append(mido.Message("note_on", channel=0, note=pitch,
                                  velocity=80, time=max(0, start_tick - prev_tick)))
            t.append(mido.Message("note_off", channel=0, note=pitch,
                                  velocity=0, time=TICKS_PER_BEAT))
            prev_tick = end_tick
    t.append(mido.MetaMessage("end_of_track", time=0))
    m.tracks.append(t)

    m.save(output_path)
    print(f"3/4 样例已生成：{output_path}，{bars} 小节 × 3 拍，BPM={bpm}，含 3/4 time_signature meta")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "test.mid"
    if out.endswith("34.mid") or out.endswith("-34.mid"):
        generate_34_midi(out)
    else:
        generate_test_midi(out)
