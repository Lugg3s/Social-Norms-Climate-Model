import json
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
import pytest
from SALib.sample import sobol

from analysis.sensitivity.sample_size_review import review_sample_sizes


def make_run(root):
    problem = dict(num_vars=2, names=["a", "b"], bounds=[[0, 1], [0, 1]])
    x = sobol.sample(problem, 256, calc_second_order=False, seed=42)
    folder = root / "norm"
    folder.mkdir()
    (folder / "metadata.json").write_text(json.dumps(dict(
        scenario="Example norm", base_sample_size=256, problem=problem,
        outputs_for_ranking=["additive", "constant"])), encoding="utf-8")
    pd.DataFrame({"sample_index": np.arange(len(x)), "a": x[:, 0], "b": x[:, 1]}).to_csv(
        folder / "samples.csv", sep=";", index=False)
    pd.DataFrame({"sample_index": np.arange(len(x)), "status": "completed",
                  "additive": x[:, 0] + 2 * x[:, 1], "constant": 0.}).to_csv(
        folder / "simulation_outputs.csv", sep=";", index=False)
    return folder


def test_additive_indices_and_constant_outputs_preserve_sources():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        folder = make_run(root)
        originals = {p: p.read_bytes() for p in folder.iterdir()}
        summary = review_sample_sizes(root, sizes=[128, 256], num_resamples=20)
        assert set(summary.status) == {"estimated", "constant"}
        constants = summary[summary.output == "constant"]
        assert constants.max_ST_95_halfwidth.isna().all()
        table = pd.read_csv(root / "sample_size_review/indices_by_sample_size.csv", sep=";")
        final = table[table.base_sample_size == 256].set_index("parameter")
        np.testing.assert_allclose(final.loc[["a", "b"], "ST"], [.2, .8], atol=.03)
        assert summary[summary.base_sample_size == 256].iloc[0].previous_size == 128
        for path, content in originals.items():
            assert path.read_bytes() == content


def test_failures_are_not_filtered_and_invalid_layout_rejected():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        folder = make_run(root)
        outputs = pd.read_csv(folder / "simulation_outputs.csv", sep=";")
        outputs.loc[0, "status"] = "failed"
        outputs.to_csv(folder / "simulation_outputs.csv", sep=";", index=False)
        table = review_sample_sizes(root, sizes=[128, 256], num_resamples=2)
        assert table.status.eq("incomplete").all()
        assert table.precision_check.eq("Not assessable").all()
        samples = pd.read_csv(folder / "samples.csv", sep=";")
        samples.loc[1, "b"] += .1
        samples.to_csv(folder / "samples.csv", sep=";", index=False)
        with pytest.raises(ValueError, match="layout"):
            review_sample_sizes(root, sizes=[128], num_resamples=2)


def test_sizes_must_be_powers_of_two():
    with pytest.raises(ValueError, match="powers of two"):
        review_sample_sizes(".", sizes=[56])
