"""Copy only selected saved PNGs, preserving all source files and other results."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from analysis.sensitivity.copy_result_plots import (
    COMPARISON_FILENAME, DEFAULT_OUTPUT_ROOT, PLOT_FILENAMES, copy_result_plots, main,
)


class CopyResultPlotsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "completed_run"
        self.source.mkdir()
        self.destination = self.root / "results"

    def norm(self, folder_name, scenario, *, comparison=True):
        folder = self.source / folder_name
        folder.mkdir()
        (folder / "metadata.json").write_text(json.dumps({"scenario": scenario}), encoding="utf-8")
        for filename in PLOT_FILENAMES:
            if not comparison and filename == COMPARISON_FILENAME:
                continue
            (folder / filename).write_bytes(b"\x89PNG\r\n\x1a\n" + (folder_name + filename).encode())
        (folder / "unrelated.png").write_bytes(b"not selected")
        return folder

    def test_overwrites_four_pngs_only_and_preserves_sources(self):
        norm = self.norm("baseline", "baseline")
        target = self.destination / norm.name
        target.mkdir(parents=True)
        for filename in PLOT_FILENAMES:
            (target / filename).write_bytes(b"old")
        note = target / "notes.md"
        note.write_text("User content", encoding="utf-8")
        originals = {path: path.read_bytes() for path in norm.iterdir()}
        report = copy_result_plots(self.source, self.destination)
        self.assertEqual(len(report.copied), 4)
        self.assertEqual(report.skipped_comparisons, [])
        for filename in PLOT_FILENAMES:
            self.assertEqual((target / filename).read_bytes(), originals[norm / filename])
        self.assertEqual(note.read_text(encoding="utf-8"), "User content")
        self.assertFalse((target / "unrelated.png").exists())
        self.assertEqual({path: path.read_bytes() for path in norm.iterdir()}, originals)

    def test_filters_by_display_name_or_folder_and_supports_single_norm(self):
        selected = self.norm("Static_injunctive", "Static injunctive")
        self.norm("baseline", "baseline")
        for selection in ("Static injunctive", "Static_injunctive"):
            with self.subTest(selection=selection):
                report = copy_result_plots(self.source, self.destination, scenarios=[selection])
                self.assertEqual(len(report.copied), 4)
                self.assertTrue(all(path.parent.name == selected.name for path in report.copied))
                self.assertFalse((self.destination / "baseline").exists())
        self.assertEqual(len(copy_result_plots(selected, self.destination).copied), 4)

    def test_no_norm_intentionally_omits_comparison_even_if_obsolete_source_exists(self):
        folder = self.norm("No_social_norm", "No social norm", comparison=False)
        report = copy_result_plots(self.source, self.destination)
        self.assertEqual(len(report.copied), 3)
        self.assertEqual(report.skipped_comparisons, ["No social norm"])
        (folder / COMPARISON_FILENAME).write_bytes(b"obsolete reference comparison")
        report = copy_result_plots(self.source, self.destination)
        self.assertEqual(len(report.copied), 3)
        self.assertFalse((self.destination / folder.name / COMPARISON_FILENAME).exists())

    def test_missing_plot_or_unknown_selection_does_not_partially_write(self):
        first = self.norm("first", "First")
        second = self.norm("second", "Second")
        (second / COMPARISON_FILENAME).unlink()
        existing = self.destination / first.name / PLOT_FILENAMES[0]
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"keep until validation succeeds")
        with self.assertRaisesRegex(FileNotFoundError, COMPARISON_FILENAME):
            copy_result_plots(self.source, self.destination)
        self.assertEqual(existing.read_bytes(), b"keep until validation succeeds")
        self.assertEqual(len(list(self.destination.rglob("*.png"))), 1)
        with self.assertRaisesRegex(ValueError, "Scenarios not found"):
            copy_result_plots(self.source, self.destination, scenarios=["First", "Typo"])
        self.assertEqual(existing.read_bytes(), b"keep until validation succeeds")

    def test_rejects_writes_inside_source_and_empty_or_missing_input(self):
        norm = self.norm("baseline", "baseline")
        with self.assertRaisesRegex(ValueError, "outside the input"):
            copy_result_plots(self.source, self.source / "derived")
        with self.assertRaisesRegex(ValueError, "change an input file"):
            copy_result_plots(norm, self.source)
        with self.assertRaises(FileNotFoundError):
            copy_result_plots(self.root / "missing", self.destination)
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(FileNotFoundError, "No sensitivity"):
            copy_result_plots(empty, self.destination)

    def test_cli_default_destination_and_selection(self):
        with patch("analysis.sensitivity.copy_result_plots.copy_result_plots") as copier:
            copier.return_value.copied = []
            copier.return_value.skipped_comparisons = []
            main(["--input-root", str(self.source), "--scenarios", "Static injunctive"])
        copier.assert_called_once_with(input_root=self.source, output_root=DEFAULT_OUTPUT_ROOT,
                                       scenarios=["Static injunctive"])


if __name__ == "__main__":
    unittest.main()
