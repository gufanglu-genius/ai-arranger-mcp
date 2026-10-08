#!/usr/bin/env python3
"""Part 0 · 拍号写入路径复测（M5）：make_test_midi.generate_34_midi → 完整 analyze→chords→stems→render→validate 闭环。

验证 time_signature 元事件 3/4 从「写入 → 读回 → 工具链」全链路正确（不经统计推断绕开）。
产物落盘 evidence/tests/normal/time34-write-path/，结果存 result.json。
"""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent  # 项目根 (AI黑客松 编曲)
sys.path.insert(0, str(ROOT / "mcp-server"))
from core import analyze_impl, chords_impl, stems_impl, render_impl, validate_impl
from make_test_midi import generate_34_midi
import pretty_midi

CASE = ROOT / "evidence/tests/normal/time34-write-path"
CASE.mkdir(parents=True, exist_ok=True)
INP = CASE / "input.mid"

def main():
    t0 = time.time()
    steps = []
    # 1. 生成 3/4 样例（make_test_midi 正式生成器）
    generate_34_midi(str(INP))
    # 独立读回（不经 core）
    pm = pretty_midi.PrettyMIDI(str(INP))
    ts_events = [(int(x.numerator), int(x.denominator)) for x in pm.time_signature_changes]
    n_notes = sum(len(i.notes) for i in pm.instruments)
    steps.append({"step": "make_test_midi(3/4)", "ok": True,
                  "detail": {"ts_events": ts_events, "note_count": n_notes}})
    ts_ok = (ts_events == [(3, 4)])

    # 2. analyze
    a = analyze_impl(str(INP))
    ev_ts = a.get("melody_time_signature")
    stat_ts = a.get("time_signature")
    steps.append({"step": "analyze", "ok": True,
                  "detail": {"key": a.get("key"), "key_confidence": a.get("key_confidence"),
                              "melody_time_signature(event)": ev_ts, "time_signature(stat)": stat_ts,
                              "bpm": a.get("bpm"), "note_count": a.get("note_count")}})
    analyze_ts_ok = (ev_ts == "3/4")

    # 3. chords（M5 拍号修复：按 melody_time_signature=3/4 排布 3 拍/小节）
    c = chords_impl(a, style="pop", output_path=str(CASE / "chords.json"))
    c_ok = (c.get("bars", 0) == 4 and c.get("status") == "ok")
    steps.append({"step": "chords", "ok": c_ok,
                  "detail": {"harmonic_figure": c.get("harmonic_figure"), "bars": c.get("bars"),
                             "first_start_beat": c["chords"][0]["start_beat"] if c.get("chords") else None}})

    # 4. stems（M5：drums 按 3 拍/小节排布，3/4 下共 4 小节 = 12 beats）
    s = stems_impl(a, c, style="pop", output_dir=str(CASE / "stems"))
    drum_notes = next((t["note_count"] for t in s.get("tracks", []) if t["part"] == "drums"), 0)
    # 3/4 非副歌：_DRUM_PATTERN(kick0/snare1/kick2, snare3裁掉)=3 + _HIHAT(6个八分, 3.0/3.5裁掉)=6 → 9音/小节 × 4小节 = 36
    s_ok = (drum_notes == 36)
    steps.append({"step": "stems", "ok": s_ok,
                  "detail": {"tracks": [(t["part"], t["note_count"]) for t in s.get("tracks", [])],
                             "drum_notes_expected": 36, "drum_notes_actual": drum_notes,
                             "combined": s.get("combined_midi_path")}})

    # 5. render
    r = render_impl(s["combined_midi_path"], str(CASE / "demo.wav"))
    steps.append({"step": "render", "ok": r.get("status") == "ok",
                  "detail": {"status": r.get("status"), "renderer": r.get("renderer"),
                             "size_bytes": r.get("size_bytes")}})

    # 6. validate
    vr = {k: validate_impl(p)["all_passed"] for k, p in s.get("midi_paths", {}).items()}
    steps.append({"step": "validate", "ok": all(vr.values()), "detail": vr})

    verdict = "PASS" if (ts_ok and analyze_ts_ok and c_ok and s_ok and all(vr.values())) else "FAIL"
    record = {
        "test_name": "time34-write-path", "subdir": "normal/time34-write-path",
        "input": "make_test_midi.generate_34_midi（正式生成器）",
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_s": round(time.time() - t0, 2),
        "checks": {
            "write_ts_event_3of4": ts_ok,
            "analyze_reads_event_ts": analyze_ts_ok,
            "chords_bars_3per_bar": c_ok,
            "stems_drums_3per_bar": s_ok,
            "validate_all_passed": all(vr.values()),
        },
        "steps": steps, "verdict": verdict,
        "note": ("3/4 拍号写入→读回→chords/stems 全链路正确" if verdict == "PASS"
                 else f"FAIL：write={ts_ok} analyze={analyze_ts_ok} chords={c_ok} stems={s_ok} validate={all(vr.values())}"),
    }
    (CASE / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{verdict}] time34-write-path: write_ts={ts_ok} analyze_event_ts={analyze_ts_ok} validate_all={all(vr.values())}")
    return record

if __name__ == "__main__":
    main()
