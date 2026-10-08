"""M2 全链路证据收集：analyze → chords → stems → render → validate，
按顺序记录每步入参/出参到 evidence/call-chains/02-full-chain.json。

运行：
    cd mcp-server
    .venv/bin/python evidence_runner.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core import (  # noqa: E402
    analyze_impl,
    chords_impl,
    render_impl,
    stems_impl,
    validate_impl,
)

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "evidence" / "call-chains" / "02-full-chain.json"
MIDI = HERE / "test.mid"


def _step(name: str, fn, *args, **kwargs) -> dict:
    t0 = time.time()
    try:
        out = fn(*args, **kwargs)
        return {
            "step": name,
            "status": "ok",
            "elapsed_ms": int((time.time() - t0) * 1000),
            "input": {k: _jsonable(v) for k, v in _input_kwargs(name, args, kwargs).items()},
            "output": _jsonable(out),
        }
    except Exception as exc:
        return {
            "step": name,
            "status": "error",
            "error": str(exc),
            "elapsed_ms": int((time.time() - t0) * 1000),
        }


def _jsonable(obj):
    import numpy as np
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, Path):
        return str(obj)
    return obj


def _input_kwargs(step, args, kwargs):
    if step == "analyze":
        return {"midi_path": str(HERE / "test.mid")}
    if step == "chords":
        return kwargs
    if step == "stems":
        return {"style": kwargs.get("style", "pop"), "parts": kwargs.get("parts"),
                "output_dir": kwargs.get("output_dir")}
    if step == "render":
        return {"midi_path": kwargs.get("midi_path"), "wav_path": kwargs.get("wav_path")}
    if step == "validate":
        return {"midi_paths": [Path(p).name for p in kwargs.get("midi_paths", [])]}
    return kwargs


def main() -> None:
    # 清理旧的
    for f in [HERE / "output" / "chords.json", HERE / "output" / "stems_result.json"]:
        if f.exists():
            f.unlink()
    stems_dir = HERE / "output" / "stems"
    if stems_dir.exists():
        for f in stems_dir.glob("*.mid"):
            f.unlink()

    steps: list[dict] = []

    # 1. analyze
    s1 = _step("analyze", analyze_impl, str(MIDI))
    steps.append(s1)
    if s1["status"] != "ok":
        _write(steps, "analyze 失败，中止")
        return
    analysis = s1["output"]

    # 2. chords
    s2 = _step("chords", chords_impl, analysis, style="pop",
               output_path=str(HERE / "output" / "chords.json"))
    steps.append(s2)
    if s2["status"] != "ok":
        _write(steps, "chords 失败，中止")
        return
    chords_out = s2["output"]

    # 3. stems
    s3 = _step("stems", stems_impl, analysis, chords_out, style="pop",
               output_dir=str(HERE / "output" / "stems"))
    steps.append(s3)
    if s3["status"] != "ok":
        _write(steps, "stems 失败，中止")
        return
    stems_out = s3["output"]

    # 4. render（允许 skipped/failed）
    combined = stems_out.get("combined_midi_path")
    if combined:
        s4 = _step("render", render_impl, combined, str(HERE / "output" / "demo.wav"))
    else:
        s4 = {"step": "render", "status": "skipped",
              "reason": "stems 未生成 combined_midi_path（output_dir 未指定）",
              "elapsed_ms": 0}
    steps.append(s4)

    # 5. validate（全部生成物 + 源文件）
    midi_files = [str(MIDI)]
    for part in ["melody", "harmony", "bass", "drums", "countermelody", "combined"]:
        p = stems_out.get("midi_paths", {}).get(part)
        if p:
            midi_files.append(p)
    s5 = _step("validate", _validate_all, midi_files)
    steps.append(s5)

    _write(steps, "M2 全链路完成")
    print(f"已写入 {OUT}")
    for s in steps:
        print(f"  [{s['step']}] {s.get('status')} ({s.get('elapsed_ms', 0)}ms)")


def _validate_all(midi_paths: list[str]) -> dict:
    results = {}
    all_passed = True
    for p in midi_paths:
        r = validate_impl(p)
        rel = Path(p).name
        results[rel] = {
            "all_passed": r.get("all_passed"),
            "failures": r.get("failures"),
            "checks": [
                {"name": c["name"], "status": c["status"], "detail": c["detail"]}
                for c in r.get("checks", [])
            ],
        }
        if not r.get("all_passed"):
            all_passed = False
    return {"all_passed": all_passed, "files": results}


def _write(steps: list[dict], note: str) -> None:
    record = {
        "call_id": "02-full-chain",
        "milestone": "M2",
        "note": note,
        "steps": steps,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    for s in steps:
        print(f"  [{s.get('step')}] {s.get('status')} ({s.get('elapsed_ms', 0)}ms)")


if __name__ == "__main__":
    main()
