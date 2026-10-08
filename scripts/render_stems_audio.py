#!/usr/bin/env python3
"""scripts/render_stems_audio.py — 把 mcp-server/output/stems/ 下 6 轨 MIDI 渲染为 WAV。

- 音色统一用 mcp-server/assets/GeneralUser_GS.sf2（真实 GM SoundFont，INC-011）。
- 输出到 docs/assets/stems/{melody,harmony,bass,drums,countermelody,combined}.wav。
- 可复跑、幂等：每次重跑先删旧产物再重新渲染；fluidsynth 缺失时如实报错不静默。
- 优先用 .venv 内 python + 系统/conda fluidsynth（与 core.render_impl 同口径）。

用法：
    cd <repo-root>
    python3 scripts/render_stems_audio.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEMS_SRC = ROOT / "mcp-server" / "output" / "stems"
SF2 = ROOT / "mcp-server" / "assets" / "GeneralUser_GS.sf2"
OUT_DIR = ROOT / "docs" / "assets" / "stems"
PARTS = ["melody", "harmony", "bass", "drums", "countermelody", "combined"]


def find_fluidsynth() -> str | None:
    cands = [shutil.which("fluidsynth"), "/opt/anaconda3/bin/fluidsynth"]
    for c in cands:
        if c and Path(c).exists():
            return c
    return None


def render_one(fs: str, src: Path, dst: Path) -> dict:
    cmd = [
        fs, "-i", "-q",
        "-r", "44100", "-a", "file",
        "-o", "audio.file.name=" + str(dst.resolve()),
        "-o", "audio.file.type=wav",
        "-o", "audio.file.format=s16",
        str(SF2.resolve()), str(src.resolve()),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    ok = proc.returncode == 0 and dst.exists() and dst.stat().st_size > 0
    return {
        "part": src.stem,
        "src": str(src.relative_to(ROOT)),
        "out": str(dst.relative_to(ROOT)),
        "returncode": proc.returncode,
        "ok": ok,
        "size_bytes": dst.stat().st_size if dst.exists() else 0,
        "stderr_tail": (proc.stderr or "")[-300:] if not ok else "",
    }


def main() -> int:
    fs = find_fluidsynth()
    if fs is None:
        print("[ERROR] fluidsynth 未找到（PATH 与 /opt/anaconda3/bin 均无）。"
              "安装：conda install -c conda-forge fluidsynth", file=sys.stderr)
        return 1
    if not SF2.exists():
        print(f"[ERROR] SoundFont 缺失：{SF2}（见 evidence/validation/incidents.md INC-011）",
              file=sys.stderr)
        return 1
    if not STEMS_SRC.exists():
        print(f"[ERROR] stems 源目录缺失：{STEMS_SRC}（先跑 README 端到端最快路径生成 output/stems/）",
              file=sys.stderr)
        return 1

    # 幂等：先清空旧产物
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.wav"):
        old.unlink()

    results = [render_one(fs, STEMS_SRC / f"{p}.mid", OUT_DIR / f"{p}.wav") for p in PARTS]
    summary = {"fluidsynth": fs, "soundfont": str(SF2.relative_to(ROOT)), "results": results}
    (OUT_DIR.parent / "stems-render-manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = [r for r in results if not r["ok"]]
    for r in results:
        flag = "OK " if r["ok"] else "ERR"
        print(f"[{flag}] {r['part']:<13} -> {r['out']}  ({r['size_bytes']} B)")
        if not r["ok"]:
            print(f"      stderr: {r['stderr_tail']}")
    print(f"\n渲染完成：{len(results) - len(failed)}/{len(results)} 成功")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
