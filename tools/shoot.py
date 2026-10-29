"""Screenshot pages of the site with the system Chrome (dev tool). Serve docs/ first:
    cd docs && python3 -m http.server 8642

    uv run python tools/shoot.py OUTDIR [path ...] [--w 1440 --h 1000 --dark --full]
Paths are hash routes and may carry actions after '|': '#/search?q=wolf|wait:4000|hover:.result'
"""
import argparse
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--base", default="http://127.0.0.1:8642")
    ap.add_argument("--w", type=int, default=1440)
    ap.add_argument("--h", type=int, default=1000)
    ap.add_argument("--dark", action="store_true")
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx = await b.new_context(viewport={"width": a.w, "height": a.h}, device_scale_factor=1,
                                  color_scheme="dark" if a.dark else "light")
        page = await ctx.new_page()
        page.on("console", lambda m: m.type in ("error", "warning") and print("console:", m.type, m.text))
        page.on("pageerror", lambda e: print("pageerror:", e))
        for i, spec in enumerate(a.paths):
            path, *acts = spec.split("|")
            await page.goto(a.base + "/" + path.lstrip("/"), wait_until="networkidle")
            await page.wait_for_timeout(600)
            for act in acts:
                kind, _, arg = act.partition(":")
                if kind == "wait":
                    await page.wait_for_timeout(int(arg))
                elif kind == "hover":
                    await page.hover(arg)
                elif kind == "click":
                    await page.click(arg)
                elif kind == "type":
                    sel, _, txt = arg.partition("=")
                    await page.fill(sel, txt)
                elif kind == "key":
                    await page.keyboard.press(arg)
                elif kind == "scroll":
                    await page.mouse.wheel(0, int(arg))
                    await page.wait_for_timeout(400)
                await page.wait_for_timeout(300)
            name = f"{i:02d}_" + (path.strip("/#").replace("/", "_").replace("?", "_").replace("=", "-")[:40] or "home") + ".png"
            await page.screenshot(path=str(out / name), full_page=a.full)
            print(out / name)
        await b.close()


asyncio.run(main())
