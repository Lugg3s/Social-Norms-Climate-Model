#!/usr/bin/env python3
"""Generate animated GIFs from matching plot PNGs under a runs directory.

Usage examples:
  python make_plot_gifs.py E:/Masterarbeit/Runs --pattern temperature_and_x.png --scenario Dynamic_social_norm
  python make_plot_gifs.py E:/Masterarbeit/Runs --pattern temperature_and_x.png

The script groups matching files by scenario folder (assumes structure .../<group>/<scenario>/<run>/file.png).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List

from PIL import Image


def collect_images(root: Path, pattern: str, scenario: str | None = None) -> List[Path]:
    files = list(root.rglob(pattern))
    if scenario:
        files = [p for p in files if scenario in p.parts]
    return sorted(files, key=lambda p: p.stat().st_mtime)


def natural_sort_key(s: str):
    # simple numeric-aware key for filenames
    import re

    parts = re.split(r"(\d+)", s)
    key = []
    for p in parts:
        if p.isdigit():
            key.append(int(p))
        else:
            key.append(p.lower())
    return key


def normalize_frames(paths: Iterable[Path], background=(255, 255, 255, 255)) -> List[Image.Image]:
    imgs = [Image.open(p).convert("RGBA") for p in paths]
    if not imgs:
        return []
    max_w = max(i.width for i in imgs)
    max_h = max(i.height for i in imgs)
    frames: List[Image.Image] = []
    for im in imgs:
        canvas = Image.new("RGBA", (max_w, max_h), background)
        x = (max_w - im.width) // 2
        y = (max_h - im.height) // 2
        canvas.paste(im, (x, y), im)
        frames.append(canvas.convert("P", palette=Image.ADAPTIVE))
    return frames


def make_gif(frames: List[Image.Image], out_path: Path, fps: float = 2.0, loop: int = 0) -> None:
    if not frames:
        print(f"No frames to save for {out_path}", file=sys.stderr)
        return
    duration = int(1000 / max(1e-3, fps))
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=loop,
        optimize=False,
    )


def group_by_scenario(matches: List[Path]) -> dict[str, List[Path]]:
    groups: dict[str, List[Path]] = {}
    for p in matches:
        # Expect .../<group>/<scenario>/<run>/file.png
        try:
            scenario_name = p.parent.parent.name
        except Exception:
            scenario_name = p.parent.name
        groups.setdefault(scenario_name, []).append(p)
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate GIFs from matching plot PNGs under a runs directory.")
    parser.add_argument("root", type=Path, help="Root folder to search (e.g., E:/Masterarbeit/Runs)")
    parser.add_argument("--pattern", default="temperature_and_x.png", help="Filename pattern to look for")
    parser.add_argument("--scenario", default=None, help="Optional scenario folder name to limit to (e.g., Dynamic_social_norm)")
    parser.add_argument("--output", type=Path, default=None, help="Output folder for GIFs (default: <root>/gifs)")
    parser.add_argument("--fps", type=float, default=2.0, help="Frames per second for GIF")
    parser.add_argument("--loop", type=int, default=0, help="Number of loops for GIF (0=infinite)")
    parser.add_argument("--sort-by", choices=["mtime", "name"], default="mtime", help="How to sort frames before GIFing")
    args = parser.parse_args()

    root = args.root
    if not root.exists():
        print("Root path does not exist:", root, file=sys.stderr)
        sys.exit(2)

    out_root = args.output or (root / "gifs")
    out_root.mkdir(parents=True, exist_ok=True)

    matches = collect_images(root, args.pattern, args.scenario)
    if not matches:
        print("No matching images found.")
        return

    if args.scenario:
        frames_src = matches
        if args.sort_by == "name":
            frames_src = sorted(frames_src, key=lambda p: natural_sort_key(p.name))
        frames = normalize_frames(frames_src)
        out_name = f"{args.scenario}__{args.pattern}.gif"
        make_gif(frames, out_root / out_name, fps=args.fps, loop=args.loop)
        print("Saved GIF:", out_root / out_name)
        return

    groups = group_by_scenario(matches)
    for scenario_name, paths in groups.items():
        if args.sort_by == "name":
            paths = sorted(paths, key=lambda p: natural_sort_key(p.name))
        else:
            paths = sorted(paths, key=lambda p: p.stat().st_mtime)
        frames = normalize_frames(paths)
        out_name = f"{scenario_name}__{args.pattern}.gif"
        make_gif(frames, out_root / out_name, fps=args.fps, loop=args.loop)
        print("Saved GIF:", out_root / out_name)


if __name__ == "__main__":
    main()
