#!/usr/bin/env python3
"""Render a WeChat HTML at mobile width and split the screenshot into chunks.

Usage:
  python3 preview.py html/article.html --prefix /tmp/opencode/article
  python3 preview.py html/article.html --width 390 --chunk 1600

Requires Chrome/Chromium headless and Pillow. Chrome path:
  ARCHIFY_CHROME=$HOME/.cache/archify-chrome/.../chrome-headless-shell
"""
import argparse
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageChops


def find_chrome() -> str:
    for key in ("ARCHIFY_CHROME", "CHROME", "CHROME_PATH"):
        val = os.environ.get(key)
        if val:
            return val
    for name in ("chrome-headless-shell", "google-chrome", "chromium", "chromium-browser"):
        p = shutil.which(name)
        if p:
            return p
    cached = Path.home() / ".cache/archify-chrome/chrome-headless-shell-linux64/chrome-headless-shell"
    if cached.exists():
        return str(cached)
    raise SystemExit("Chrome not found; set ARCHIFY_CHROME or CHROME")


def main():
    ap = argparse.ArgumentParser(description="Mobile preview + chunking")
    ap.add_argument("html")
    ap.add_argument("--prefix", default=None, help="output prefix; default: <stem>")
    ap.add_argument("--width", type=int, default=390)
    ap.add_argument("--height", type=int, default=12000)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--chunk", type=int, default=1600, help="chunk height in device px")
    ap.add_argument("--overlap", type=int, default=60)
    args = ap.parse_args()

    html = Path(args.html).resolve()
    prefix = Path(args.prefix) if args.prefix else html.with_suffix("")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    full = Path(str(prefix) + ".png")

    cmd = [
        find_chrome(),
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--force-device-scale-factor={args.scale}",
        f"--window-size={args.width},{args.height}",
        "--virtual-time-budget=1500",
        f"--screenshot={full}",
        html.as_uri(),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    im = Image.open(full).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    bbox = ImageChops.difference(im, bg).getbbox()
    if bbox:
        im = im.crop((0, 0, im.width, min(im.height, bbox[3] + 20)))
    im.save(full)

    n, y = 0, 0
    while y < im.height:
        chunk = im.crop((0, y, im.width, min(y + args.chunk, im.height)))
        out = Path(f"{prefix}-{n + 1:02d}.png")
        chunk.save(out)
        print(out)
        n += 1
        y += args.chunk - args.overlap
    print(f"full: {full} ({im.width}x{im.height}), chunks: {n}")


if __name__ == "__main__":
    main()
