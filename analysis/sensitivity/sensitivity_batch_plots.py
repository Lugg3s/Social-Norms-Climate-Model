"""Render batch figures and videos from saved sensitivity NPZs without simulating."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
import json
from pathlib import Path

import pandas as pd

import simulation.batch_runner as batch
from simulation.time_series import load_time_series
from analysis.trajectory_classification import classify_trajectory, classification_definition
from visualization.make_plot_videos import make_mp4, normalize_frames


def _render_one(task):
    archive, scenario, features, scenario_output = task
    frame, metadata = load_time_series(archive)
    context, params = metadata["context"], metadata["parameters"]
    phase = context["phase"]
    if phase not in {"sample", "boundary"}:
        raise ValueError(f"Unknown trajectory phase: {phase}")
    name = f"{phase}_{int(context['sample_index']):06d}"
    run_dir = scenario_output / name
    run_dir.mkdir(exist_ok=True)
    label = f"{scenario} | {name}"
    classification = classify_trajectory(
        frame["t"], frame["x"],
        stepwise=params.get("agent_decision_model") == "annual_intention_threshold")
    batch.save_run_plots(frame, run_dir, label, params, features)
    batch.save_json(run_dir / "parameters.json", params)
    batch.save_json(run_dir / "metadata.json", {**metadata, "source_time_series": str(archive), "run_label": label,
                                               "derived_classification": classification})
    return {**metadata["metrics"], **classification, **{feature: params[feature] for feature in features},
            "sample_index": context["sample_index"], "phase": phase, "status": "ok",
            "scenario": scenario, "group": scenario, "run_name": name,
            "run_dir": str(run_dir), "time_series_file": str(archive)}


def _sources(input_root, scenarios, sample_indices, max_samples, include_boundaries):
    folders = ([input_root] if (input_root / "time_series.json").exists()
               else sorted(path.parent for path in input_root.glob("*/time_series.json")))
    if not folders:
        raise FileNotFoundError("No saved sensitivity time series found. Earlier runs without NPZs require "
                                "new simulations; this script never runs the model.")
    sources = []
    matched = set()
    for folder in folders:
        info = json.loads((folder / "time_series.json").read_text(encoding="utf-8"))
        scenario = info["scenario"]
        requested = {name for name in scenarios or [] if name in {scenario, folder.name}}
        if scenarios and not requested:
            continue
        matched.update(requested)
        if not info["enabled"]:
            raise FileNotFoundError(f"Time-series saving was disabled for {scenario}")
        archive_dir = (folder / info["directory"]).resolve()
        if not archive_dir.is_relative_to(folder.resolve()):
            raise ValueError(f"Invalid archive directory: {archive_dir}")
        available = {int(path.stem.removeprefix("sample_")): path for path in archive_dir.glob("sample_*.npz")}
        status_path = folder / "simulation_outputs.csv"
        if status_path.exists():
            statuses = pd.read_csv(status_path, sep=";", usecols=["sample_index", "status"])
            completed = set(statuses.loc[statuses["status"].eq("completed"), "sample_index"].astype(int))
        else:
            # An interrupted/in-progress attempt can still contain complete atomic archives.
            completed = set(available)
        selected = sorted(completed if sample_indices is None else set(map(int, sample_indices)))
        if max_samples is not None:
            selected = selected[:max_samples]
        missing = set(selected) - (set(available) & completed)
        if missing:
            raise FileNotFoundError(f"Missing saved samples for {scenario}: {sorted(missing)}")
        paths = [available[index] for index in selected]
        if include_boundaries:
            boundary_paths = sorted(archive_dir.glob("boundary_*.npz"))
            boundary_status = folder / "zero_boundary_cases.csv"
            if boundary_status.exists():
                boundaries = pd.read_csv(boundary_status, sep=";")
                boundary_paths = [path for path in boundary_paths
                                  if boundaries.iloc[int(path.stem.removeprefix("boundary_"))]["status"] == "ok"]
            paths += boundary_paths
        if not paths:
            raise FileNotFoundError(f"No complete trajectories saved yet for {scenario}: {archive_dir}")
        features = [name for name in pd.read_csv(folder / "samples.csv", sep=";", nrows=0).columns
                    if name != "sample_index"]
        sources.append((folder, scenario, features, paths))
    missing_scenarios = set(scenarios or []) - matched
    if missing_scenarios:
        raise ValueError(f"Scenarios not found: {sorted(missing_scenarios)}")
    return sources


def render_saved_sensitivity(input_root: Path, output_root: Path | None = None, *, scenarios=None,
                             sample_indices=None, max_samples=None, workers=1, videos=True,
                             plots_3d=True, parameter_pairs=None, max_video_frames=240,
                             video_fps=2, animation_fps=12, include_boundaries=False):
    """All calculations here are plotting/postprocessing of immutable saved runs."""
    input_root = Path(input_root).resolve()
    if workers < 1 or max_video_frames < 1 or video_fps <= 0 or animation_fps <= 0:
        raise ValueError("Workers, frame count and frame rates must be positive")
    if max_samples is not None and max_samples < 1:
        raise ValueError("max-samples must be positive")
    if parameter_pairs and any(len(pair) != 2 or pair[0] == pair[1] for pair in parameter_pairs):
        raise ValueError("Each parameter pair must contain two different parameter names")
    sources = _sources(input_root, scenarios, sample_indices, max_samples, include_boundaries)
    if parameter_pairs and not any(set(pair).issubset(features) for pair in parameter_pairs
                                   for _, _, features, _ in sources):
        raise ValueError("None of the requested parameter pairs exists in the selected norms")
    if videos:
        import imageio_ffmpeg
        batch.matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
    base = Path(output_root).resolve() if output_root is not None else input_root / "batch_plots"
    output = base / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"input_root": str(input_root), "source": "saved aggregate trajectories; no simulation",
                "behaviour_classification": classification_definition(),
                "classification_source": "Recomputed from each archived trajectory using the recorded current definition; source archive metadata preserved.",
                "videos": videos, "plots_3d": plots_3d,
                "parameter_projection": "Individual sampled runs; other sampled parameters vary. No fitted surface.",
                "scenarios": []}
    batch.save_json(output / "manifest.json", manifest)
    all_summaries = []
    for source_folder, scenario, features, archives in sources:
        destination = output / source_folder.name
        destination.mkdir()
        print(f"{scenario}: rendering {len(archives)} saved runs -> {destination}", flush=True)
        tasks = [(archive, scenario, features, destination) for archive in archives]
        if workers == 1:
            records = list(map(_render_one, tasks))
        else:
            with ProcessPoolExecutor(max_workers=workers) as executor:
                records = list(executor.map(_render_one, tasks))
        summary = pd.DataFrame(records)
        all_summaries.append(summary)
        group = batch.ExperimentGroup(scenario, [scenario],
                                      {name: sorted(summary[name].unique()) for name in features})
        batch.save_group_comparison_plots(summary, destination, group, parameter_maps=False, legend_parameters=[])
        batch.save_approach_comparison_plot(summary, destination, scenario)
        pairs = parameter_pairs if parameter_pairs else [features[:2]]
        projections = []
        for pair_index, pair in enumerate(pairs, start=1):
            if len(pair) != 2 or pair[0] == pair[1] or not set(pair).issubset(features):
                if parameter_pairs:
                    print(f"  Skipping unavailable parameter pair {pair} for {scenario}", flush=True)
                continue
            pair_dir = destination / "parameter_pairs" / f"pair_{pair_index:02d}"
            pair_dir.mkdir(parents=True)
            batch.save_json(pair_dir / "parameters.json", {"x": pair[0], "y": pair[1],
                                                           "other_sampled_parameters_vary": True})
            batch.save_phase_map_for_two_parameters(summary, pair_dir, *pair, scatter=True,
                                                     output_name="phase_map.png")
            for metric in batch.KEY_METRICS:
                if metric in summary:
                    batch.save_heatmap_for_two_parameters(summary, pair_dir, metric, *pair, scatter=True,
                                                         output_name=f"{metric}.png")
            if plots_3d:
                projections.append(batch.save_x_parameter_surface_animation(
                    summary, pair_dir, *pair, scenario, max_frames=max_video_frames,
                    scatter=True, make_video=videos, fps=animation_fps, strict_video_errors=True,
                    output_stem="x_3d"))
        if videos:
            video_dir = destination / "videos"
            video_dir.mkdir()
            plot_names = sorted({image.name for record in records for image in Path(record["run_dir"]).glob("*.png")})
            for plot in plot_names:
                frames = [Path(record["run_dir"]) / plot for record in records
                          if (Path(record["run_dir"]) / plot).exists()]
                make_mp4(normalize_frames(frames), video_dir / f"{Path(plot).stem}.mp4", fps=video_fps)
        manifest["scenarios"].append({"scenario": scenario, "sample_count": len(records),
                                      "source_archives": [str(path) for path in archives],
                                      "output_directory": str(destination), "projections": projections})
        batch.save_json(output / "manifest.json", manifest)
    combined = pd.concat(all_summaries, ignore_index=True)
    combined.to_csv(output / "all_runs.csv", sep=";", index=False)
    batch.save_overall_comparison_plots(combined, output)
    comparison = batch.build_scenario_comparison_table(combined)
    comparison.to_csv(output / "scenario_comparison.csv", sep=";", index=False)
    batch.save_scenario_comparison_bar_charts(comparison, output)
    print(f"Saved batch plots and videos: {output}", flush=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path, help="Sensitivity run or individual norm folder")
    parser.add_argument("--output-root", type=Path, help="Default: <input-root>/batch_plots/<timestamp>")
    parser.add_argument("--scenarios", nargs="+")
    parser.add_argument("--sample-indices", type=int, nargs="+")
    parser.add_argument("--max-samples", type=int, help="Optional limit per norm; default: all saved samples")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--no-videos", action="store_true")
    parser.add_argument("--no-3d", action="store_true")
    parser.add_argument("--parameter-pair", nargs=2, action="append", metavar=("X", "Y"),
                        help="Repeat for additional pairs; default: first two sampled parameters per norm")
    parser.add_argument("--max-video-frames", type=int, default=240, help="Frames per 3D time animation")
    parser.add_argument("--video-fps", type=float, default=2)
    parser.add_argument("--animation-fps", type=float, default=12)
    parser.add_argument("--include-boundary-cases", action="store_true")
    args = parser.parse_args()
    render_saved_sensitivity(args.input_root, args.output_root, scenarios=args.scenarios,
                             sample_indices=args.sample_indices, max_samples=args.max_samples,
                             workers=args.workers, videos=not args.no_videos, plots_3d=not args.no_3d,
                             parameter_pairs=args.parameter_pair, max_video_frames=args.max_video_frames,
                             video_fps=args.video_fps, animation_fps=args.animation_fps,
                             include_boundaries=args.include_boundary_cases)


if __name__ == "__main__":
    main()
