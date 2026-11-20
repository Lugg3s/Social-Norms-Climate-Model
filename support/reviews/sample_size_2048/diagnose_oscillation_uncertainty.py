"""Historical investigation of the saved N=2048 run; no simulation or source edits.

Run from the repository root with:
python -m support.reviews.sample_size_2048.diagnose_oscillation_uncertainty
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(r"E:\Masterarbeit\Sensitivity\job-3311884_samplsize2048\job-3311884\2026-11-19_04-50-55")
DEST = Path(__file__).parent / "oscillation_diagnosis"


def indices(y, d):
    block = np.asarray(y).reshape(-1, d + 2)
    a, b, ab = block[:, 0], block[:, -1], block[:, 1:-1]
    variance = np.var(np.r_[a, b])
    numerator = .5 * (a[:, None] - ab) ** 2
    return numerator.mean(axis=0) / variance, variance, numerator, block


def main():
    DEST.mkdir(exist_ok=True)
    summaries, contributions, influential, stress, phase_bounds, denominators, bootstrap_groups = [], [], [], [], [], [], []
    for path in sorted(ROOT.glob("*/simulation_outputs.csv")):
        folder = path.parent
        meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        frame = pd.read_csv(path, sep=";")
        samples = pd.read_csv(folder / "samples.csv", sep=";")
        d = meta["problem"]["num_vars"]
        assert len(frame) == meta["base_sample_size"] * (d + 2)
        assert frame.status.eq("completed").all()
        assert np.array_equal(frame.sample_index, np.arange(len(frame)))
        counts = frame.n_oscillations.to_numpy()
        scale = 500 / meta["simulation_time"]
        y = frame.oscillations_per_500_years.to_numpy()
        np.testing.assert_allclose(y, np.where(counts >= 2, counts * scale, 0))
        summary = dict(scenario=meta["scenario"], rows=len(frame), oscillatory_rows=int((counts >= 2).sum()),
                       exactly_one_cycle=int((counts == 1).sum()), exactly_two_cycles=int((counts == 2).sum()),
                       max_cycles=counts.max(), max_rate=y.max(),
                       rate_q99=np.quantile(y, .99), rate_q999=np.quantile(y, .999),
                       mean_rate=y.mean(), median_nonzero_rate=np.median(y[y > 0]) if (y > 0).any() else 0)
        summaries.append(summary)
        if np.ptp(y) == 0:
            continue
        st, variance, numerator, blocks = indices(y, d)
        bootstrap = np.random.default_rng(42).integers(len(blocks), size=(len(blocks), 500))
        boot_a, boot_b = blocks[bootstrap, 0], blocks[bootstrap, -1]
        boot_variance = np.var(np.concatenate([boot_a, boot_b]), axis=0)
        ab_values = np.r_[blocks[:, 0], blocks[:, -1]]
        squared = (ab_values - ab_values.mean())**2
        ordered = np.sort(squared)[::-1]
        denominators.append(dict(scenario=meta["scenario"], AB_rows=len(ab_values),
                                 AB_nonzero=int((ab_values > 0).sum()),
                                 AB_top1_variance_share=ordered[0] / squared.sum(),
                                 AB_top5_variance_share=ordered[:5].sum() / squared.sum(),
                                 AB_top10_variance_share=ordered[:10].sum() / squared.sum(),
                                 all_rows_cycles_ge_20=int((counts >= 20).sum())))
        sigma = np.sqrt(variance)
        for j, parameter in enumerate(meta["problem"]["names"]):
            total = numerator[:, j].sum()
            order = np.argsort(-numerator[:, j])
            boot_index = .5 * np.mean((boot_a - blocks[bootstrap, j + 1])**2, axis=0) / boot_variance
            multiplicity = np.sum(bootstrap == order[0], axis=0)
            for label, mask in (("omitted", multiplicity == 0), ("once", multiplicity == 1),
                                ("twice_or_more", multiplicity >= 2)):
                bootstrap_groups.append(dict(scenario=meta["scenario"], parameter=parameter,
                                             largest_numerator_block=int(order[0]), category=label,
                                             replicates=int(mask.sum()),
                                             mean_ST=float(np.mean(boot_index[mask])),
                                             mean_AB_variance=float(np.mean(boot_variance[mask]))))
            loo_vars = ((np.sum(blocks[:, 0]**2 + blocks[:, -1]**2)
                         - blocks[:, 0]**2 - blocks[:, -1]**2) / (2 * (len(blocks) - 1))
                        - ((np.sum(blocks[:, 0] + blocks[:, -1]) - blocks[:, 0] - blocks[:, -1])
                           / (2 * (len(blocks) - 1)))**2)
            loo = ((total - numerator[:, j]) / (len(blocks) - 1)) / loo_vars
            first_st, first_var, first_num, _ = indices(y[:1024 * (d + 2)], d)
            contributions.append(dict(scenario=meta["scenario"], parameter=parameter, ST=st[j],
                                      ST_1024=first_st[j], AB_variance=variance, AB_variance_1024=first_var,
                                      numerator_mean=numerator[:, j].mean(),
                                      numerator_mean_1024=first_num[:, j].mean(),
                                      top1_numerator_share=numerator[order[0], j] / total if total else 0,
                                      top5_numerator_share=numerator[order[:5], j].sum() / total if total else 0,
                                      max_leave_one_block_ST_change=np.max(np.abs(loo - st[j]))))
            for rank, k in enumerate(order[:3]):
                for role, offset in (("A", 0), ("AB", j + 1), ("B", d + 1)):
                    index = int(k * (d + 2) + offset)
                    influential.append(dict(scenario=meta["scenario"], folder=folder.name,
                                            parameter=parameter, block=int(k), block_rank=rank + 1,
                                            numerator_share=numerator[k, j] / total if total else 0,
                                            role=role, sample_index=index, rate=y[index], cycles=counts[index],
                                            median_period=frame.iloc[index].median_period,
                                            oscillation_amplitude=frame.iloc[index].oscillation_amplitude,
                                            classification_cycles=frame.iloc[index].classification_complete_cycles,
                                            **{name: samples.iloc[index][name] for name in meta["problem"]["names"]}))
            # Conservative analytic bound for arbitrary bounded response perturbations.
            # It covers all row signs jointly, unlike random phase jitter.
            for name, c in (("one_cycle", scale), ("one_cycle_plus_two_cycle_gate", 2 * scale)):
                rms = np.sqrt(2 * numerator[:, j].mean())
                low = .5 * (max(rms - 2 * c, 0) / (sigma + c))**2
                high = .5 * ((rms + 2 * c) / (sigma - c))**2 if sigma > c else np.inf
                phase_bounds.append(dict(scenario=meta["scenario"], parameter=parameter,
                                         perturbation=name, max_row_change=c,
                                         ST=st[j], minimum_ST_bound=low, maximum_ST_bound=high))
        for name, values in (("without_two_cycle_gate", counts * scale),
                             ("log1p_rate", np.log1p(y)),
                             ("classification_detector_same_denominator", np.where(
                                 frame.classification_complete_cycles.to_numpy() >= 2,
                                 frame.classification_complete_cycles.to_numpy() * scale, 0)),
                             ("capped_at_99th_percentile", np.minimum(y, np.quantile(y, .99)))):
            if np.ptp(values) == 0:
                continue
            alt, _, _, _ = indices(values, d)
            smaller, _, _, _ = indices(values[:1024 * (d + 2)], d)
            for j, parameter in enumerate(meta["problem"]["names"]):
                stress.append(dict(scenario=meta["scenario"], variant=name,
                                   parameter=parameter, ST=alt[j], ST_1024=smaller[j],
                                   change=alt[j] - smaller[j]))
        print(meta["scenario"], summary["oscillatory_rows"], "max cycles", summary["max_cycles"], flush=True)
    for name, rows in (("distribution", summaries), ("contributions", contributions),
                       ("influential_rows", influential), ("response_stress", stress),
                       ("phase_bounds", phase_bounds), ("denominator_concentration", denominators),
                       ("bootstrap_groups", bootstrap_groups)):
        pd.DataFrame(rows).to_csv(DEST / (name + ".csv"), sep=";", index=False)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    source = ROOT / "Descriptive,_injunctive,_dynamic2" / "simulation_outputs.csv"
    values = pd.read_csv(source, sep=";").n_oscillations
    frequencies = values.value_counts().sort_index()
    axes[0].bar(frequencies.index, frequencies.values, color="#4c78a8")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Saved complete cycles per 600-year run")
    axes[0].set_ylabel("Number of model runs (log scale)")
    axes[0].set_title("Most runs have few cycles; a small tail has many")
    contribution = pd.DataFrame(influential)
    selected = contribution[(contribution.scenario == "Descriptive, injunctive, dynamic2")
                            & (contribution.parameter == "tau") & (contribution.role == "A")]
    axes[1].bar(["Largest block", "2nd largest", "3rd largest"], selected.numerator_share * 100,
                color="#e07b39")
    axes[1].set_ylabel("Share of the ST numerator for tau (%)")
    axes[1].set_title("A few Sobol blocks dominate the squared differences")
    fig.suptitle("Descriptive, injunctive, dynamic2 | saved N=2048 design")
    fig.tight_layout()
    fig.savefig(DEST / "tail_and_influence.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
