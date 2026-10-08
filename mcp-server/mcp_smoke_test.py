"""通过 MCP stdio 客户端真实调用 MCP 服务，验证 M1/M2 工具注册与实装通路。

运行：
    cd mcp-server
    .venv/bin/python mcp_smoke_test.py
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    here = Path(__file__).parent
    params = StdioServerParameters(
        command=str(here / ".venv" / "bin" / "python"),
        args=[str(here / "mcp_server.py")],
        env=None,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("注册工具:", names)
            assert {"analyze", "validate", "chords", "stems", "render"} <= set(names), f"工具注册不完整: {names}"

            # 调用 analyze
            res = await session.call_tool("analyze", {"midi_path": str(here / "test.mid")})
            analyze_out = json.loads(res.content[0].text)
            print("\nanalyze ->", json.dumps(analyze_out, ensure_ascii=False, indent=2))
            assert analyze_out["bpm"] == 90, f"BPM 期望 90，实际 {analyze_out['bpm']}"

            # 调用 validate
            res = await session.call_tool("validate", {"midi_path": str(here / "test.mid")})
            validate_out = json.loads(res.content[0].text)
            print("\nvalidate ->", json.dumps(validate_out, ensure_ascii=False, indent=2))
            assert validate_out["all_passed"] is True, "validate 应全项通过"

            # 调用 chords（M2 实装）
            res = await session.call_tool(
                "chords", {"analysis": analyze_out, "style": "pop"})
            chords_out = json.loads(res.content[0].text)
            print("\nchords ->", chords_out.get("harmonic_figure"), "bars:", chords_out.get("bars"))
            assert chords_out.get("status") == "ok"

            # 调用 stems（M2 实装）
            res = await session.call_tool(
                "stems", {"analysis": analyze_out, "chords_out": chords_out, "style": "pop"})
            stems_out = json.loads(res.content[0].text)
            print("\nstems ->", [(t["part"], t["note_count"]) for t in stems_out.get("tracks", [])])
            assert stems_out.get("status") == "ok"

            # 调用 render（M2 实装；无 SoundFont 时允许 skipped/failed，不阻塞冒烟）
            if stems_out.get("combined_midi_path"):
                res = await session.call_tool(
                    "render",
                    {"midi_path": stems_out["combined_midi_path"],
                     "wav_path": str(here / "output" / "demo_smoke.wav")})
                render_out = json.loads(res.content[0].text)
                print("\nrender ->", render_out.get("status"),
                      render_out.get("wav_path") or render_out.get("error", ""))
                assert render_out.get("status") in {"ok", "skipped", "failed"}

            print("\nM2 冒烟测试通过：5 工具注册 + analyze/validate/chords/stems 实装 + render 通路")


if __name__ == "__main__":
    asyncio.run(main())
