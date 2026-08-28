#!/usr/bin/env python3
"""Generate animated videos from matching plot PNGs under a runs directory.

Usage examples:
  python make_plot_videos.py E:/Masterarbeit/Runs --plot temperature_and_x.png --scenario Dynamic_social_norm
  python make_plot_videos.py E:/Masterarbeit/Runs --plot temperature_and_x.png

The script groups matching files by scenario folder (assumes structure .../<group>/<scenario>/<run>/file.png).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Iterator, List

from PIL import Image
import imageio
import numpy as np


def collect_images(root: Path, plot: str, scenario: str | None = None) -> List[Path]:
    if not plot.endswith(".png"):
        plot += ".png"
    files = list(root.rglob(plot))
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


def normalize_frames(
    paths: Iterable[Path],
    background=(255, 255, 255),
) -> Iterator[Image.Image]:
    """Yield normalized RGB frames without retaining all source images in memory."""
    path_list = list(paths)
    if not path_list:
        return

    dimensions = []
    for path in path_list:
        with Image.open(path) as source:
            dimensions.append(source.size)

    max_w = max(width for width, _ in dimensions)
    max_h = max(height for _, height in dimensions)
    # Avoid implicit FFmpeg resizing by using H.264-compatible dimensions.
    max_w = ((max_w + 15) // 16) * 16
    max_h = ((max_h + 15) // 16) * 16

    for path in path_list:
        with Image.open(path) as source:
            image = source.convert("RGBA")
        canvas = Image.new("RGB", (max_w, max_h), background)
        x = (max_w - image.width) // 2
        y = (max_h - image.height) // 2
        canvas.paste(image, (x, y), image)
        image.close()
        yield canvas


def make_mp4(frames: Iterable[Image.Image], out_path: Path, fps: float = 2.0) -> None:
    with imageio.get_writer(
        out_path,
        fps=fps,
        codec="libx264",
        pixelformat="yuv420p",
    ) as writer:
        for frame in frames:
            try:
                writer.append_data(np.asarray(frame))
            finally:
                frame.close()


def make_gif(frames: List[Image.Image], out_path: Path, fps: float = 2.0) -> None:
    if not frames:
        print(f"No frames to save for {out_path}", file=sys.stderr)
        return

    duration = int(1000 / max(1e-3, fps))

    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
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
    parser = argparse.ArgumentParser(description="Generate videos from matching plot PNGs under a runs directory.")
    parser.add_argument("root", type=Path, help="Root folder to search (e.g., E:/Masterarbeit/Runs)")
    parser.add_argument("--plot", help="Filename plot to look for")
    # parser.add_argument("--scenario", default=None, help="Optional scenario folder name to limit to (e.g., Dynamic_social_norm)")
    # parser.add_argument("--output", type=Path, default=None, help="Output folder for videos (default: <root>/videos)")
    # parser.add_argument("--fps", type=float, default=2.0, help="Frames per second for video")
    args = parser.parse_args()

    root = args.root
    if not root.exists():
        print("Root path does not exist:", root, file=sys.stderr)
        sys.exit(2)

    for scenario_group_dir in root.iterdir():
        if not scenario_group_dir.is_dir():
            continue
        for norm_approach in scenario_group_dir.iterdir():
            if not norm_approach.is_dir():
                continue
            print(f"Processing norm approach: {norm_approach}")
            #  get all plot name (png) from the dir norm_approach
            if not args.plot:
                plot_names = set()
                for child_dir in norm_approach.iterdir():
                    if not child_dir.is_dir():
                        continue
                    for image in child_dir.glob("*.png"):
                        plot_names.add(image.stem)
            else:
                plot_names = [args.plot]
            print(f"found plot_names: {plot_names}")
            for plot_name in plot_names:
                matches = collect_images(norm_approach, plot_name, scenario=None)
                if matches:
                    frames = normalize_frames(matches)
                    out_name = f"{plot_name}.mp4"
                    make_mp4(frames, norm_approach / out_name, fps=2.0)
                    print("Saved MP4:", norm_approach / out_name)
                else:
                    print("No matching images found.")

    # groups = group_by_scenario(matches)
    # for scenario_name, paths in groups.items():
    #     paths = sorted(paths, key=lambda p: p.stat().st_mtime)
    #     frames = normalize_frames(paths)
    #     out_name = f"{scenario_name}__{args.plot}.mp4"
    #     make_mp4(frames, out_root / out_name, fps=args.fps)
    #     print("Saved MP4:", out_root / out_name)

if __name__ == "__main__":
    main()
