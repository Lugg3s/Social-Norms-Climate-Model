"""Copy four saved sensitivity PNGs per norm into the thesis results folders."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile

from utils.paths import PROJECT_ROOT


PLOT_FILENAMES = (
    "behaviour_class_frequencies.png",
    "without_norm_comparison_frequencies.png",
    "ranking_balken_gruppen_gesamt.png",
    "ranking_balken_zielvariablen.png",
)
COMPARISON_FILENAME = "without_norm_comparison_frequencies.png"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "Global_sensitivity_analysis"


@dataclass
class CopyReport:
    copied: list[Path]
    skipped_comparisons: list[str]


def copy_result_plots(
    input_root: Path,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    *,
    scenarios: list[str] | None = None,
) -> CopyReport:
    """Validate the selection, then replace only its named destination PNGs.

    A missing comparison for ``No social norm`` is expected and is not copied.
    Other missing files are errors, detected before any destination is changed.
    No simulation or plot generation is performed.
    """
    source_root = Path(input_root).resolve()
    destination_root = Path(output_root).resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Sensitivity input folder not found: {source_root}")
    if destination_root.is_relative_to(source_root):
        raise ValueError("The output folder must be outside the input folder to preserve source files.")

    folders = ([source_root] if (source_root / "metadata.json").is_file() else
               sorted(path.parent for path in source_root.glob("*/metadata.json")))
    selected, matched, skipped = [], set(), []
    for folder in folders:
        metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        scenario = metadata.get("scenario")
        if not isinstance(scenario, str) or not scenario.strip():
            raise ValueError(f"Missing scenario name in {folder / 'metadata.json'}")
        matches = set(scenarios or []) & {scenario, folder.name}
        if scenarios and not matches:
            continue
        matched.update(matches)
        for filename in PLOT_FILENAMES:
            if scenario == "No social norm" and filename == COMPARISON_FILENAME:
                skipped.append(scenario)
                continue
            source = folder / filename
            target = destination_root / folder.name / filename
            if target.resolve().is_relative_to(source_root):
                raise ValueError(f"Destination would change an input file: {target}")
            selected.append((source, target))

    if set(scenarios or []) - matched:
        raise ValueError(f"Scenarios not found: {sorted(set(scenarios) - matched)}")
    if not selected:
        raise FileNotFoundError(f"No sensitivity scenario folders found in {source_root}")
    missing = [str(source) for source, _ in selected if not source.is_file()]
    if missing:
        raise FileNotFoundError("Required saved plots are missing:\n" + "\n".join(missing))

    copied = []
    for source, target in selected:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Replacing a temporary copy also protects sources if a destination is a link.
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
        try:
            shutil.copy2(source, temporary)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        copied.append(target)
    return CopyReport(copied=copied, skipped_comparisons=skipped)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True,
                        help="Completed sensitivity run or single scenario folder; read only.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT,
                        help=f"Default: {DEFAULT_OUTPUT_ROOT}. Existing named PNGs are overwritten.")
    parser.add_argument("--scenarios", nargs="+", default=None,
                        help="Scenario names or source folder names. Default: all available scenarios.")
    report = copy_result_plots(**vars(parser.parse_args(argv)))
    for path in report.copied:
        print(path)
    for scenario in report.skipped_comparisons:
        print(f"Skipped {COMPARISON_FILENAME} for {scenario}: no reference comparison is applicable.")
    print(f"Copied {len(report.copied)} PNGs.")
    return report


if __name__ == "__main__":
    main()
