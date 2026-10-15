"""Review completed Saltelli designs without modifying or rerunning simulations.

Writes a standalone HTML report, Markdown, scientific figures and audit tables.
The stored metadata is authoritative; current scenario defaults are never used.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import importlib.metadata
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np
import pandas as pd
from SALib.analyze import sobol
from SALib.sample import sobol as sample_sobol

ORIGINAL = ["final_x", "final_temperature", "cumulative_emissions",
            "time_to_elimination_censored", "oscillation_amplitude",
            "oscillations_per_500_years", "damping_index"]
ALTERNATIVES = ["oscillation_occurrence", "log1p_oscillation_rate",
                "threshold_ever_reached", "threshold_at_end",
                "first_passage_capped_T", "first_passage_penalty_2T", "mean_mitigation"]
OUT_LABEL = {"final_x": "Mitigationsanteil am Ende", "final_temperature": "Endtemperatur",
              "cumulative_emissions": "Kumulierte Emissionen",
              "time_to_elimination_censored": "Erste Schwelle / Ersatz 11.200",
              "oscillation_amplitude": "Oszillationsamplitude",
              "oscillations_per_500_years": "Oszillationen pro 500 Jahre",
              "damping_index": "Dämpfungsindex",
              "oscillation_occurrence": "Mindestens eine Oszillation",
              "log1p_oscillation_rate": "log(1 + Oszillationshäufigkeit)",
              "threshold_ever_reached": "Schwelle jemals erreicht",
              "threshold_at_end": "Schwelle am Ende erreicht",
              "first_passage_capped_T": "Erste Schwelle, begrenzt auf T",
              "first_passage_penalty_2T": "Erste Schwelle / Ersatz 2T",
              "mean_mitigation": "Zeitmittel des Mitigationsanteils (0–1.200)"}
SHORT = {"baseline": "Baseline", "Dynamic social norm": "Dynamic",
         "Belief-based / intention motivation": "Belief-based",
         "Observation based / approval (punish only one behaviour)": "Approval",
         "Static injunctive": "Static injunctive",
         "Descriptive, injunctive, dynamic": "D/I/Dynamic",
         "Descriptive, injunctive, dynamic2": "D/I/Dynamic2",
         "Injunctive, dynamic2": "I/Dynamic2",
         "dynamic social norm2": "Dynamic2"}


def json_safe(value):
    if isinstance(value, dict): return {k:json_safe(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [json_safe(v) for v in value]
    if isinstance(value, np.generic): value=value.item()
    if isinstance(value,float) and not np.isfinite(value): return None
    return value


def boolean(values: pd.Series) -> np.ndarray:
    if pd.api.types.is_bool_dtype(values):
        return values.to_numpy(dtype=bool)
    parsed = values.astype(str).str.lower().map({"true": True, "false": False, "1": True, "0": False})
    if parsed.isna().any():
        raise ValueError(f"Invalid boolean values in {values.name}")
    return parsed.to_numpy(dtype=bool)


def derive_outputs(frame: pd.DataFrame, horizon: float) -> pd.DataFrame:
    """Keep every Saltelli row; alternative metrics define different estimands."""
    out = frame[ORIGINAL].copy()
    first = frame.time_to_elimination.to_numpy(dtype=float)
    reached = boolean(frame.threshold_reached)
    if not np.array_equal(np.isfinite(first), reached):
        raise ValueError("First-passage times and threshold_reached disagree")
    if np.any(first[reached] < 0) or np.any(first[reached] > horizon):
        raise ValueError("First-passage time outside simulation horizon")
    out["oscillation_occurrence"] = (frame.n_oscillations >= 1).astype(float)
    out["log1p_oscillation_rate"] = np.log1p(frame.oscillations_per_500_years)
    out["threshold_ever_reached"] = reached.astype(float)
    out["threshold_at_end"] = boolean(frame.elimination_success).astype(float)
    out["first_passage_capped_T"] = np.where(reached, first, horizon)
    out["first_passage_penalty_2T"] = np.where(reached, first, 2 * horizon)
    out["mean_mitigation"] = frame.x_area / horizon
    return out


def validate_design(samples, outputs, problem, base_n):
    d = problem["num_vars"]
    expected = base_n * (d + 2)
    for label, frame in [("samples", samples), ("outputs", outputs)]:
        if len(frame) != expected or not np.array_equal(frame.sample_index, np.arange(expected)):
            raise ValueError(f"{label}: rows are missing, duplicated or out of order")
    x = samples[problem["names"]].to_numpy(dtype=float)
    if not np.isfinite(x).all():
        raise ValueError("Non-finite input samples")
    block = x.reshape(base_n, d + 2, d)
    for j in range(d):
        expected_ab = block[:, 0, :].copy()
        expected_ab[:, j] = block[:, -1, j]
        if not np.array_equal(expected_ab, block[:, j + 1, :]):
            raise ValueError(f"Invalid A/AB/B Saltelli layout for parameter {j}")
    if not outputs.status.eq("completed").all():
        raise ValueError("Incomplete simulation design: refusing to remove rows")


def analyze(problem, values, seed=42, num_resamples=100):
    y = np.asarray(values, dtype=float)
    if not np.isfinite(y).all():
        raise ValueError("Non-finite response")
    if np.ptp(y) <= 1e-12:
        # Match the original pipeline, but flag constant outputs as uninformative.
        return {k: np.zeros(problem["num_vars"]) for k in ["S1", "ST", "S1_conf", "ST_conf"]}, "constant"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = sobol.analyze(problem, y, calc_second_order=False,
                               num_resamples=num_resamples, seed=seed)
    warning = " | ".join(sorted(set(str(x.message) for x in caught)))
    step = problem["num_vars"] + 2
    if np.ptp(np.r_[y[::step], y[step-1::step]]) == 0:
        warning = "A/B constant: indices undefined; SALib fallback shown | " + warning
    return result, warning


def bootstrap_diagnostics(values, d, seed=42, repetitions=2000):
    """Inspect A/B denominators; never silently discard degenerate resamples.

    Exact constant ranges identify true degeneracy even if floating-point
    variance returns a tiny positive value. Near-zero variance is reported
    separately using a declared relative threshold of 1e-12.
    """
    y = np.asarray(values, dtype=float)
    if np.ptp(y) <= 1e-12:
        return {"constant_output": True, "AB_variance": 0.0,
                "bootstrap_constant_fraction": 1.0, "bootstrap_nearzero_fraction": 1.0,
                "bootstrap100_constant_count": 100, "AB_unique": 1,
                "max_numerator_block_share": np.nan, "max_leave_one_block_ST_change": np.nan}
    z = (y - y.mean()) / y.std()
    blocks = z.reshape(-1, d + 2)
    a, b = blocks[:, 0], blocks[:, -1]
    ab = blocks[:, 1:-1]
    n = len(a)
    variance = np.var(np.r_[a, b])
    counts = {}
    for count in [100, repetitions]:
        indices = np.random.default_rng(seed).integers(n, size=(n, count))
        ar, br = a[indices], b[indices]
        spread = np.maximum(ar.max(axis=0), br.max(axis=0)) - np.minimum(ar.min(axis=0), br.min(axis=0))
        variances = np.var(np.concatenate([ar, br], axis=0), axis=0)
        counts[count] = (spread == 0, variances)
    constant, variances = counts[repetitions]
    numerator = 0.5 * (a[:, None] - ab) ** 2
    sums = numerator.sum(axis=0)
    shares = np.divide(numerator.max(axis=0), sums, out=np.zeros(d), where=sums > 0)
    # Removing a complete block is a stress diagnostic, not a new QMC design.
    loo_var = ((np.sum(a*a + b*b) - a*a - b*b) / (2*(n-1))
               - ((np.sum(a+b) - a-b) / (2*(n-1)))**2)
    with np.errstate(divide="ignore", invalid="ignore"):
        st = numerator.mean(axis=0) / variance
        loo_st = ((sums[None, :] - numerator)/(n-1)) / loo_var[:, None]
    loo_change = np.abs(loo_st - st[None, :])
    return {"constant_output": False, "AB_variance": variance,
            "AB_unique": len(np.unique(np.r_[a,b])),
            "bootstrap_constant_fraction": float(constant.mean()),
            "bootstrap_nearzero_fraction": float((variances <= 1e-12 * variance).mean()),
            "bootstrap100_constant_count": int(counts[100][0].sum()),
            "bootstrap_variance_ratio_min": float(variances.min()/variance) if variance > 0 else np.nan,
            "bootstrap_variance_ratio_p01": float(np.quantile(variances, .01)/variance) if variance > 0 else np.nan,
            "max_numerator_block_share": float(shares.max()),
            "max_leave_one_block_ST_change": float(np.nanmax(loo_change)) if np.isfinite(loo_change).any() else np.nan}


def format_number(value):
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value): return "nicht bestimmbar"
        if abs(value) >= 10000 or (0 < abs(value) < .001): return f"{value:.2e}"
        return f"{value:.3f}"
    return str(value)


def md_table(frame: pd.DataFrame) -> str:
    values = [[format_number(v).replace("|", "/") for v in row] for row in frame.itertuples(index=False, name=None)]
    lines = ["| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"]*len(frame.columns)) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in values)
    return "\n".join(lines)


def save_table(frame, destination, name):
    frame.to_csv(destination / f"{name}.csv", sep=";", index=False, encoding="utf-8-sig")


def collect(source: Path, destination: Path):
    all_indices, all_diagnostics, audits, checks, events, outliers = [], [], [], [], [], []
    sources, contexts, conditional = [], {}, []
    for folder in sorted(source.iterdir()):
        if not folder.is_dir() or not (folder / "metadata.json").exists(): continue
        metadata = json.loads((folder / "metadata.json").read_text())
        scenario = metadata["scenario"]
        print(f"Reviewing {scenario}", flush=True)
        problem = {k: metadata["problem"][k] for k in ["num_vars", "names", "bounds"]}
        n, seed = metadata["base_sample_size"], metadata["seed"]
        if n != 512: raise ValueError(f"Expected N=512, got {n} in {scenario}")
        samples = pd.read_csv(folder / "samples.csv", sep=";")
        values = pd.read_csv(folder / "simulation_outputs.csv", sep=";")
        stored = pd.read_csv(folder / "sobol_indices.csv", sep=";")
        validate_design(samples, values, problem, n)
        expected = sample_sobol.sample(problem.copy(), n, calc_second_order=False, seed=seed)
        if not np.allclose(expected, samples[problem["names"]].to_numpy(), rtol=0, atol=1e-12):
            raise ValueError("Saved samples do not match scrambled Sobol design")
        for fn in ["samples.csv", "simulation_outputs.csv", "metadata.json", "parameters.json", "analysis_status.json", "sobol_indices.csv", "zero_boundary_cases.csv"]:
            file = folder / fn
            sources.append({"file": str(file), "bytes": file.stat().st_size,
                            "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
        horizon = metadata["simulation_time"]
        response = derive_outputs(values, horizon)
        if not np.allclose(values.oscillations_per_500_years, values.n_oscillations*500/horizon, rtol=1e-12):
            raise ValueError("Oscillation rate not reproducible")
        expected_time = np.where(np.isfinite(values.time_to_elimination), values.time_to_elimination,
                                 horizon + metadata["elimination_censor_offset"])
        if not np.allclose(values.time_to_elimination_censored, expected_time):
            raise ValueError("Stored censoring convention differs from metadata")
        if not np.array_equal(boolean(values.elimination_success), values.final_x.to_numpy() >= .95):
            raise ValueError("Endpoint threshold differs from documented 0.95")
        boundary = pd.read_csv(folder / "zero_boundary_cases.csv", sep=";")
        status = json.loads((folder / "analysis_status.json").read_text())
        audits.append({"scenario": scenario, "base_samples": n, "simulations": len(values),
                       "status": status["status"], "boundary_runs": len(boundary),
                       "boundary_ok": int(boundary.status.eq("ok").sum()),
                       "x_bounds_valid": bool(boolean(values.x_bounds_valid).all()),
                       "finite_original_outputs": bool(np.isfinite(response[ORIGINAL]).all().all()),
                       "coupling_interval": metadata["coupling_interval"],
                       "simulation_time": horizon, "seed": seed,
                       "saved_design_verified": True})
        d = problem["num_vars"]
        for size in [128, 256, 512]:
            subset = response.iloc[:size*(d+2)]
            for metric in ORIGINAL + ALTERNATIVES:
                result, warning = analyze(problem, subset[metric].to_numpy(), seed)
                for j, name in enumerate(problem["names"]):
                    all_indices.append({"scenario": scenario, "output": metric, "N": size,
                                        "parameter": name, "alternative": metric in ALTERNATIVES,
                                        **{k: float(result[k][j]) for k in ["S1", "ST", "S1_conf", "ST_conf"]},
                                        "warning": warning, "point_estimate_defined": "constant" not in warning.lower()})
                all_diagnostics.append({"scenario": scenario, "output": metric, "N": size,
                                        **bootstrap_diagnostics(subset[metric], d, seed)})
                if size == 512 and metric in ORIGINAL:
                    old = stored[stored.output == metric].set_index("parameter").loc[problem["names"]]
                    for k in ["S1", "ST", "S1_conf", "ST_conf"]:
                        match = bool(np.allclose(old[k], result[k], rtol=1e-10, atol=1e-10, equal_nan=True))
                        checks.append({"scenario": scenario, "output": metric, "field": k,
                                       "stored_reproduced": match,
                                       "max_absolute_difference": float(np.max(np.abs(old[k].to_numpy()-result[k])))})
                        if not match: raise ValueError(f"Stored results not reproduced: {scenario} {metric} {k}")
        # Disjoint halves expose changes hidden by nested estimates; no claim of independence.
        for metric in ORIGINAL + ALTERNATIVES:
            result, warning = analyze(problem, response.iloc[256*(d+2):][metric], seed)
            for j, name in enumerate(problem["names"]):
                all_indices.append({"scenario": scenario, "output": metric, "N": 256,
                                    "parameter": name, "alternative": metric in ALTERNATIVES,
                                    "subset": "second_half",
                                    **{k: float(result[k][j]) for k in ["S1", "ST", "S1_conf", "ST_conf"]}, "warning": warning,
                                    "point_estimate_defined": "constant" not in warning.lower()})
        reached = boolean(values.threshold_reached)
        at_end = boolean(values.elimination_success)
        oscillating = (values.n_oscillations >= 1).to_numpy()
        a_b_rows = np.r_[np.arange(0,len(values),d+2), np.arange(d+1,len(values),d+2)]
        damping_defined = (np.isfinite(values.amplitude_initial) & np.isfinite(values.amplitude_final)
                           & (values.amplitude_initial > 1e-12) & (values.amplitude_final > 1e-12)).to_numpy()
        events.append({"scenario": scenario, "simulations": len(values), "AB_rows": len(a_b_rows),
                       "oscillating": int(oscillating.sum()), "oscillating_AB": int(oscillating[a_b_rows].sum()),
                       "oscillation_fraction": float(oscillating.mean()),
                       "threshold_ever": int(reached.sum()), "threshold_at_end": int(at_end.sum()),
                       "never_reached": int((~reached).sum()), "never_reached_AB": int((~reached[a_b_rows]).sum()),
                       "reached_but_below_at_end": int((reached & ~at_end).sum()),
                       "damping_defined": int(damping_defined.sum()),
                       "damping_zero_undefined": int((~damping_defined & values.damping_index.eq(0).to_numpy()).sum()),
                       "max_oscillations": float(values.n_oscillations.max()),
                       "max_rate": float(values.oscillations_per_500_years.max())})
        for metric, mask, label in [("oscillation_amplitude", oscillating, "at_least_one_full_cycle"),
                                     ("oscillations_per_500_years", oscillating, "at_least_one_full_cycle"),
                                     ("damping_index", damping_defined, "damping_defined"),
                                     ("time_to_elimination", reached, "ever_reached")]:
            series = values.loc[mask, metric]
            conditional.append({"scenario": scenario, "metric": metric, "condition": label,
                                "count": len(series), "median": series.median(), "p10": series.quantile(.1),
                                "p90": series.quantile(.9), "maximum": series.max()})
        # A review shortlist, preserving full model inputs for targeted future reruns.
        chosen: dict[int, list[str]] = {}
        for index in values.nlargest(2, "n_oscillations").index:
            chosen.setdefault(int(index), []).append("largest_oscillation_count")
        for index in values[~reached].head(2).index:
            chosen.setdefault(int(index), []).append("never_reaches_threshold")
        for metric in ["oscillations_per_500_years", "time_to_elimination_censored"]:
            b = response[metric].to_numpy().reshape(n, d+2)
            differences = (b[:,0,None] - b[:,1:-1])**2
            block, j = np.unravel_index(np.argmax(differences), differences.shape)
            chosen.setdefault(int(block*(d+2)+j+1), []).append("largest_ST_numerator_"+metric)
        base = json.loads((folder / "parameters.json").read_text())
        for index, reasons in chosen.items():
            row = values.iloc[index]
            inputs = dict(base)
            inputs.update({k: float(samples.iloc[index][k]) for k in problem["names"]})
            outliers.append({"scenario": scenario, "sample_index": index, "reason": "; ".join(reasons),
                             **{k: row[k] for k in ["n_oscillations", "median_period", "oscillation_amplitude", "time_to_elimination", "final_x"]},
                             "median_period_output_intervals": row.median_period * max(1, round(metadata["coupling_interval"]*metadata["output_points_per_year"])) / metadata["coupling_interval"],
                             "median_period_coupling_intervals": row.median_period/metadata["coupling_interval"],
                             "parameters": inputs})
        contexts[scenario] = {"folder": folder.name, "metadata": metadata}
    frames = {"indices": pd.DataFrame(all_indices), "bootstrap_diagnostics": pd.DataFrame(all_diagnostics),
              "audit": pd.DataFrame(audits), "reproduction_checks": pd.DataFrame(checks),
              "event_counts": pd.DataFrame(events), "conditional_descriptives": pd.DataFrame(conditional)}
    frames["indices"]["subset"] = frames["indices"]["subset"].fillna("prefix")
    for name, frame in frames.items(): save_table(frame, destination, name)
    (destination / "source_manifest.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    (destination / "targeted_review_samples.json").write_text(json.dumps(json_safe(outliers), indent=2, allow_nan=False), encoding="utf-8")
    save_table(pd.DataFrame([{k:v for k,v in x.items() if k != "parameters"} for x in outliers]), destination, "targeted_review_samples")
    return frames, contexts, sources


def maximum_index_change(left, right, field="ST"):
    """Undefined zero-variance estimates cannot establish convergence."""
    if not left.index.equals(right.index):
        right=right.reindex(left.index)
    if not left.point_estimate_defined.all() or not right.point_estimate_defined.eq(True).all():
        return np.nan
    return float((left[field]-right[field]).abs().max())


def summarize(frames, destination):
    indices = frames["indices"]
    prefix = indices[indices.subset.eq("prefix")]
    diagnostics = frames["bootstrap_diagnostics"].set_index(["scenario", "output", "N"])
    rows, rank_rows = [], []
    def top_label(part):
        if not part.point_estimate_defined.all(): return "nicht bestimmbar"
        return " = ".join(part.index[np.isclose(part.ST,part.ST.max(),rtol=0,atol=1e-10)])
    for (scenario, metric), group in prefix.groupby(["scenario", "output"], sort=False):
        part = {n: group[group.N.eq(n)].set_index("parameter") for n in [128,256,512]}
        halves = indices[indices.subset.eq("second_half") & indices.scenario.eq(scenario) & indices.output.eq(metric)].set_index("parameter")
        a, b, c = part[128], part[256], part[512]
        top = c.ST.nlargest(2)
        first, second = top.index[:2]
        row = {"scenario": scenario, "output": metric, "alternative": metric in ALTERNATIVES,
               "max_abs_ST_change_128_256": maximum_index_change(a,b),
               "max_abs_ST_change_256_512": maximum_index_change(b,c),
               "mean_abs_ST_change_256_512": float((b.ST-c.ST).abs().mean()),
               "max_abs_S1_change_256_512": maximum_index_change(b,c,"S1"),
               "max_abs_ST_change_halves": maximum_index_change(b,halves),
               "ST_rank_spearman_256_512": float(b.ST.rank().corr(c.ST.rank())) if b.ST.nunique()>1 and c.ST.nunique()>1 else np.nan,
               "top_128": top_label(a), "top_256": top_label(b), "top_512": top_label(c),
               "top2_same_256_512": set(b.ST.nlargest(2).index)==set(c.ST.nlargest(2).index),
               "max_ST_conf_512": float(c.ST_conf.max()), "max_S1_conf_512": float(c.S1_conf.max()),
               "max_ST_512": float(c.ST.max()), "top_ST_512": float(top.iloc[0]),
               "second_ST_512": float(top.iloc[1]), "top_gap": float(top.iloc[0]-top.iloc[1]),
               "top2_intervals_overlap": bool(c.loc[first,"ST"]-c.loc[first,"ST_conf"] <= c.loc[second,"ST"]+c.loc[second,"ST_conf"]),
               **diagnostics.loc[(scenario,metric,512)].to_dict()}
        rows.append(row)
    comparisons = pd.DataFrame(rows)
    for (scenario,n), g in prefix[~prefix.alternative].groupby(["scenario","N"], sort=False):
        for label, metrics in {"original_7": ORIGINAL, "without_frequency": [m for m in ORIGINAL if m!="oscillations_per_500_years"],
                               "climate_and_final_x": ORIGINAL[:3]}.items():
            score = g[g.output.isin(metrics)].groupby("parameter").ST.mean().sort_values(ascending=False)
            for rank,(parameter,value) in enumerate(score.items(),1):
                rank_rows.append({"scenario":scenario,"N":n,"score_definition":label,
                                  "parameter":parameter,"rank":rank,"score":value})
    rankings = pd.DataFrame(rank_rows)
    save_table(comparisons,destination,"convergence_summary")
    save_table(rankings,destination,"ranking_sensitivity")
    frames["convergence_summary"],frames["ranking_sensitivity"] = comparisons,rankings
    return frames


def detailed_influence(source, contexts, destination):
    rows=[]
    for scenario,ctx in contexts.items():
        meta=ctx["metadata"];d=meta["problem"]["num_vars"]
        raw=pd.read_csv(source/ctx["folder"]/"simulation_outputs.csv",sep=";")
        response=derive_outputs(raw,meta["simulation_time"])
        for metric in ORIGINAL+ALTERNATIVES:
            y=response[metric].to_numpy().reshape(-1,d+2)
            variance=np.var(np.r_[y[:,0],y[:,-1]])
            contributions=.5*(y[:,0,None]-y[:,1:-1])**2
            for j,name in enumerate(meta["problem"]["names"]):
                block=int(np.argmax(contributions[:,j]));total=contributions[:,j].sum()
                rows.append({"scenario":scenario,"output":metric,"parameter":name,
                             "ST":contributions[:,j].mean()/variance if variance>0 else np.nan,
                             "largest_block_numerator_share":contributions[block,j]/total if total>0 else 0.,
                             "base_block":block,"A_sample_index":block*(d+2),
                             "AB_sample_index":block*(d+2)+j+1,"B_sample_index":block*(d+2)+d+1,
                             "A_output":y[block,0],"AB_output":y[block,j+1],"B_output":y[block,-1]})
    frame=pd.DataFrame(rows);save_table(frame,destination,"individual_block_influence");return frame


def make_figures(frames, contexts, destination):
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,
                         "axes.spines.right":False,"axes.titleweight":"bold","savefig.facecolor":"white"})
    order=[s for s in SHORT if s in contexts]
    short_cols=["Endanteil x","Endtemperatur","Emissionen","Erste Schwelle\nErsatzwert","Amplitude","Häufigkeit","Dämpfung"]
    summary=frames["convergence_summary"]
    colors=["#eff6ff","#bfdbfe","#60a5fa","#fcd34d","#fb923c","#e76f51","#9b2226"]
    plots=[]
    for col,name,title,bounds,caption in [
        ("max_abs_ST_change_256_512","convergence","Änderung der Total-Order-Indizes von N=256 auf N=512",[0,.025,.05,.1,.2,.5,1,1e40],"Zellen: größte absolute Änderung über alle Parameter. Klassen dienen nur der Darstellung, nicht als Konvergenztest."),
        ("max_ST_conf_512","uncertainty","Unsicherheit bei N=512: größte 95%-Konfidenzhalbbreite",[0,.05,.1,.2,.5,1,10,1e40],"Originale SALib-Bootstrapintervalle (100 Resamples). Extrem große Werte sind unverändert ausgewiesen.")]:
        matrix=summary[~summary.alternative].pivot(index="scenario",columns="output",values=col).loc[order,ORIGINAL]
        fig,ax=plt.subplots(figsize=(13.4,7.8));ax.imshow(matrix.to_numpy(),cmap=ListedColormap(colors),norm=BoundaryNorm(bounds,len(colors)),aspect="auto")
        ax.set_xticks(range(7),short_cols);ax.set_yticks(range(len(order)),[SHORT[s] for s in order])
        for i in range(len(order)):
            for j in range(7):
                val=matrix.iloc[i,j];color="white" if val>=bounds[-2] else "#13283e"
                label=f"{val:.1e}" if val>=100 else f"{val:.3f}"
                ax.text(j,i,label,ha="center",va="center",color=color,fontsize=11)
        ax.set_title(title,pad=20,loc="left",fontsize=15)
        ax.tick_params(length=0,pad=10);fig.text(.02,.02,caption,fontsize=9,color="#334155")
        fig.subplots_adjust(left=.18,right=.98,bottom=.13,top=.89)
        fig.savefig(destination/f"{name}.png",dpi=170);plt.close(fig);plots.append(name)
    indices=frames["indices"];prefix=indices[indices.subset.eq("prefix")]
    for scenario in order:
        data=prefix[prefix.scenario.eq(scenario)&~prefix.alternative]
        parameters=contexts[scenario]["metadata"]["problem"]["names"]
        fig,axes=plt.subplots(2,4,figsize=(15.5,8.0));axes=axes.flatten()
        for j,metric in enumerate(ORIGINAL):
            ax=axes[j]
            for k,param in enumerate(parameters):
                points=data[data.output.eq(metric)&data.parameter.eq(param)].sort_values("N")
                ax.plot(points.N,points.ST,"o-",label=param,color=plt.get_cmap("tab10")(k),linewidth=1.8,markersize=4)
            ax.set_title(OUT_LABEL[metric],fontsize=10);ax.set_xticks([128,256,512]);ax.grid(alpha=.2)
            ax.axhline(1,color="#777777",linewidth=.6,linestyle=":")
            if j%4==0:ax.set_ylabel("Total-Order-Index ST")
            if j>=4:ax.set_xlabel("Basissamples N")
        axes[-1].axis("off");handles,labels=axes[0].get_legend_handles_labels()
        axes[-1].legend(handles,labels,loc="center left",frameon=False,fontsize=9)
        fig.suptitle(f"{scenario}\nVerschachtelte Stichproben: 128, 256 und 512 vollständige Sobol-Blöcke",fontsize=13,y=.99)
        fig.text(.015,.012,"Punktschätzer ohne Abschneiden bei 1. Unsicherheiten separat im Bericht. Gleicher Seed; keine unabhängigen Wiederholungen.",fontsize=9)
        fig.tight_layout(rect=(0,.04,1,.93));name="curves_"+contexts[scenario]["folder"]
        fig.savefig(destination/f"{name}.png",dpi=160);plt.close(fig);plots.append(name)
    fig,axes=plt.subplots(3,3,figsize=(16,12))
    metrics=["first_passage_capped_T","first_passage_penalty_2T","time_to_elimination_censored"]
    for ax,scenario in zip(axes.flatten(),order):
        data=prefix[prefix.scenario.eq(scenario)&prefix.N.eq(512)]
        pars=contexts[scenario]["metadata"]["problem"]["names"]
        for k,(metric,label,color) in enumerate(zip(metrics,["T=1.200","2T=2.400","T+10.000=11.200"],["#2563eb","#059669","#d97706"])):
            sub=data[data.output.eq(metric)].set_index("parameter").loc[pars]
            ax.plot(sub.ST,np.arange(len(pars))+(k-1)*.16,"o",label=label,color=color,markersize=5)
        ax.set_yticks(range(len(pars)),pars,fontsize=8);ax.invert_yaxis();ax.set_title(SHORT[scenario]);ax.grid(axis="x",alpha=.2)
        ax.set_xlabel("ST (Punktschätzer)")
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc="upper center",ncol=3,bbox_to_anchor=(.5,.947),frameon=False)
    fig.suptitle("Eliminationszeit: Einfluss des Ersatzwerts für nie erreichte Schwellen",fontsize=16,y=.987)
    fig.text(.02,.01,"Alternative Definitionen derselben Rohdaten. Kein Ersatzwert ist eine beobachtete Zeit; T ist die begrenzte erste Passagezeit.",fontsize=10)
    fig.tight_layout(rect=(.005,.035,.995,.92));fig.savefig(destination/"censoring_comparison.png",dpi=170);plt.close(fig);plots.append("censoring_comparison")
    return plots


def plot_numerical_probes(destination):
    directory=destination/"numerical_probes"
    if not (directory/"results.csv").exists(): return
    records=pd.read_csv(directory/"results.csv",sep=";")
    if not records.status.eq("completed").any(): return
    fig,axes=plt.subplots(2,3,figsize=(16,8.5))
    for row,(case,title) in enumerate([("inj1763","Injunctive, dynamic2 / Sample 1763"),("did267","Descriptive, injunctive, dynamic2 / Sample 267")]):
        for variant,color,label in [("reference","#2563eb","Referenz"),("dense","#059669","Dichte Historie/Ausgabe"),("refined","#d97706","Feineres Intervall + Toleranzen")]:
            file=directory/f"{case}_{variant}.npz"
            if not file.exists(): continue
            with np.load(file) as series:
                t,x,temp=series["t"],series["x"],series["T"]
                for col,(start,end) in enumerate([(217,260),(1100,1110)]):
                    selected=(t>=start)&(t<=end)
                    axes[row,col].plot(t[selected],x[selected],color=color,label=label,linewidth=1.05,alpha=.9)
                    axes[row,col].set_ylim(-.025,1.025);axes[row,col].set_ylabel("Mitigationsanteil x")
                axes[row,2].plot(t,temp,color=color,label=label,linewidth=1.4)
        for col in range(3):
            axes[row,col].grid(alpha=.2);axes[row,col].set_xlabel("Simulationsjahr")
            axes[row,col].set_title(["Beginn der sozialen Dynamik","Später Ausschnitt","Temperaturverlauf"][col],fontsize=10)
        axes[row,2].set_ylabel("Temperaturänderung (°C)")
        axes[row,0].text(0,1.15,title,transform=axes[row,0].transAxes,fontsize=12,fontweight="bold")
    legend={}
    for ax in axes.flat:
        handles,labels=ax.get_legend_handles_labels()
        legend.update(zip(labels,handles))
    fig.legend(legend.values(),legend.keys(),loc="upper center",ncol=3,bbox_to_anchor=(.5,.994),frameon=False)
    fig.text(.02,.015,"Phasenverschiebungen allein belegen keinen numerischen Fehler. Zyklenzahl, Amplitude und Klimagrößen werden separat verglichen.",fontsize=10)
    fig.tight_layout(rect=(0,.045,1,.95),h_pad=3.5)
    fig.savefig(destination/"numerical_probe_comparison.png",dpi=170);plt.close(fig)


def write_report(frames, contexts, destination, source, plots, influence):
    summary=frames["convergence_summary"];events=frames["event_counts"].set_index("scenario")
    indices=frames["indices"];full=indices[indices.N.eq(512)&indices.subset.eq("prefix")]
    original=summary[~summary.alternative]
    order=[s for s in SHORT if s in contexts]
    blocks=[]
    def heading(text,level=2):blocks.append(("heading",(text,level)))
    def paragraph(text):blocks.append(("paragraph",text))
    def table(df):blocks.append(("table",df))
    def figure(name,caption):blocks.append(("figure",(name,caption)))
    heading("Sensitivitätsanalyse: Konvergenz und Prüfung der Zielgrößen",1)
    paragraph(f"Auswertung von {sum(frames['audit'].simulations):,} vorhandenen Simulationen aus neun Normszenarien. "
              "512 Basissamples, 1.200 Jahre, Seed 42. Die statistische Neuauswertung verwendet ausschließlich vorhandene Daten und verändert keine Quelldateien. "
              "Zusätzliche, getrennt gespeicherte numerische Gegenprüfungen zweier Extremfälle werden weiter unten ausgewiesen. "
              "Die Ergebnisse beziehen sich auf die in diesem Lauf gespeicherten Parameterbereiche und die gleichförmige, unabhängige Eingangsverteilung.")
    heading("Ergebnis und unmittelbare Konsequenz")
    paragraph("Die Simulationen sind technisch vollständig. Eine pauschale Aussage, dass alle Sensitivitätsindizes konvergiert sind, ist jedoch nicht gerechtfertigt. "
              "Für Klima- und Mitigationsgrößen sind die Ergebnisse der injunktiven Modelle deutlich stabiler als die von Belief-based und Approval. "
              "Bei seltenen Oszillationen entstehen unzuverlässige Varianzschätzungen; bei der ersten Schwellenüberschreitung verstärkt der Ersatzwert 11.200 die Wirkung seltener Fälle. "
              "Das ursprüngliche Mittel über alle sieben Zielgrößen sollte deshalb nicht als zentrale Parameterrangfolge dienen.")
    judgments={
        "baseline":"Klima/Endanteil relativ stabil; social_norm_factor und delta liegen nahe beieinander. Oszillations- und Dämpfungsindizes nicht belastbar.",
        "Dynamic social norm":"Führende Parameter über 256→512 stabil; Amplitude verändert sich noch. Zielgröße für erfolgreiche Mitigation präzisieren.",
        "Belief-based / intention motivation":"Klima/Endanteil und erste Passage nicht stabil; gezielte Stichprobenerweiterung hat hohe Priorität.",
        "Observation based / approval (punish only one behaviour)":"Klima/Endanteil und erste Passage nicht stabil; gezielte Stichprobenerweiterung hat hohe Priorität.",
        "Static injunctive":"x_target für Klima/Endanteil stabil; Häufigkeit und Dämpfung bleiben unsicher.",
        "Descriptive, injunctive, dynamic":"x_target für Klima/Endanteil stabil; Oszillationshäufigkeit und daraus abgeleitetes Gesamtranking instabil.",
        "Descriptive, injunctive, dynamic2":"x_target für Klima/Endanteil stabil; Amplitude, Häufigkeit und Dämpfung noch unsicher.",
        "Injunctive, dynamic2":"x_target für Klima/Endanteil statistisch stabil; Endwerte schneller Dauerschwingungen zusätzlich auf Phasenempfindlichkeit prüfen.",
        "dynamic social norm2":"Führende Parameter stabil; final_x und Dämpfung zeigen noch erkennbare Änderungen."}
    rows=[]
    for scenario in order:
        s=original[original.scenario.eq(scenario)]
        core=s[s.output.isin(ORIGINAL[:3])]
        dynamics=s[s.output.isin(ORIGINAL[4:])]
        rows.append({"Norm":SHORT[scenario],"max ΔST Klima/x":core.max_abs_ST_change_256_512.max(),
                     "max ΔST Dynamik":dynamics.max_abs_ST_change_256_512.max(),"Bewertung":judgments[scenario]})
    table(pd.DataFrame(rows))
    paragraph("ΔST bezeichnet die absolute Änderung zwischen 256 und 512 Basissamples. Die Tabelle ist eine diagnostische Einordnung, kein formaler Konvergenztest. "
              "Auch kleine Änderungen beweisen keine Genauigkeit gegenüber dem unbekannten Grenzwert. Alle Normen außer dem weiterhin ausgeschlossenen Agentenmodell sind enthalten.")
    figure("convergence","Größte Änderung je Norm und Zielgröße. Alle Parameter werden berücksichtigt.")
    figure("uncertainty","Größte originale 95%-Konfidenzhalbbreite bei 512 Basissamples. Sehr große Werte werden nicht abgeschnitten.")
    heading("Technische und methodische Prüfung")
    a=frames["audit"].copy();a["scenario"]=a.scenario.map(SHORT)
    table(a[["scenario","simulations","boundary_runs","boundary_ok","x_bounds_valid","saved_design_verified"]].rename(columns={
        "scenario":"Norm","simulations":"Simulationen","boundary_runs":"Randfälle","boundary_ok":"davon erfolgreich",
        "x_bounds_valid":"x innerhalb Grenzen","saved_design_verified":"Sobol-Design verifiziert"}))
    paragraph(f"Alle {len(frames['reproduction_checks'])} Vergleiche der gespeicherten S1-, ST- und Konfidenzwerte wurden mit SALib 1.5.2 reproduziert "
              "(Toleranz rtol=atol=1e-10). Die vollständige Stichprobe wurde aus den gespeicherten Grenzen und dem Seed rekonstruiert. "
              "Sample-Indizes, A/AB/B-Blockstruktur, Status, Schwellenindikatoren und algebraische Kennzahlbeziehungen wurden geprüft. "
              "Die gültigen Zustandsgrenzen und ein erfolgreicher Solverabschluss beweisen noch keine numerische Konvergenz der Zeitverläufe.")
    paragraph("Die 128er-, 256er- und 512er-Auswertungen verwenden ausschließlich vollständige Präfixblöcke desselben aktuellen Designs. "
              "Es werden keine Zeilen aufgrund ihrer Ergebniswerte entfernt. Zusätzlich wird die zweite Hälfte mit 256 Blöcken gesondert ausgewertet. "
              "Die Hälften und Präfixe gehören zur gleichen gescrambelten Sequenz; ihre Differenzen sind keine unabhängigen Replikationstests. "
              "Potenzen von zwei erhalten die Balancierung der Sobol-Sequenz. Die dokumentierten Intervalle stammen wie im Original aus 100 Bootstrap-Resamples bei 95%. "
              "Eine ergänzende Diagnose mit 2.000 Resamples und Seed 42 zählt konstante bzw. beinahe varianzlose A/B-Resamples (relative Grenze 1e-12). "
              "Diese Diagnose ersetzt die Konfidenzintervalle nicht und schließt keine Resamples stillschweigend aus.")
    paragraph("Quellen zur Methode: SALib-Sobol-Dokumentation https://salib.readthedocs.io/en/latest/api/SALib.analyze.html#SALib.analyze.sobol.analyze "
              "und SciPy-Sobol-Dokumentation https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html. "
              "Für die tatsächliche Reproduktion wurde zusätzlich der lokal installierte SALib-1.5.2-Quellcode geprüft. "
              "Alle folgenden Befunde und Empfehlungen ergeben sich aus den lokalen Daten, nicht aus diesen Dokumentationen.")
    paragraph("Der aktuelle Lauf verwendet ein Kopplungsintervall von 0,1 Jahren. Die dynamic2-Modelle haben eine theta-Untergrenze von 0,1. "
              "Ergebnisse älterer Läufe mit anderen Einstellungen wurden nicht als reine Stichproben-Konvergenzvergleiche vermischt. "
              "Metadaten enthalten keinen vollständigen archivierten Quellcode- oder Solverstand; die statistische Reproduktion ist daher stärker abgesichert als eine spätere exakte Wiederholung der ODE-Läufe.")
    heading("Seltene Oszillationen und Bootstrap-Degeneration")
    b=events.loc["baseline"]
    dg=summary[summary.scenario.eq("baseline")&summary.output.eq("oscillations_per_500_years")].iloc[0]
    paragraph(f"Baseline: {int(b.oscillating)} von {int(b.simulations)} Läufen zeigen mindestens eine vollständige, nach dem aktuellen Detektor prominente Oszillation. "
              f"In den A/B-Basismatrizen sind es nur {int(b.oscillating_AB)} von {int(b.AB_rows)} Werten. "
              f"{int(dg.bootstrap100_constant_count)} der 100 ursprünglichen Bootstrap-Resamples enthalten dort keine Variation; "
              f"in der 2.000er-Diagnose sind es {100*dg.bootstrap_constant_fraction:.2f}%. "
              "Die SALib-Implementierung prüft die Spannweite der gesamten Resample-Matrix, nicht jede Resample-Spalte einzeln. "
              "Dadurch können konstante Spalten durch eine rundungsbedingt winzige positive Varianz dividiert werden. "
              "Die enormen Halbbreiten sind somit ein konkretes Diagnoseproblem der Unsicherheitsschätzung bei seltenen Ereignissen und kein physikalischer Effekt der Größenordnung 10³¹. "
              "Ein bloßes Herausfiltern dieser Bootstrap-Spalten wäre kein Nachweis verlässlicher Unsicherheit.")
    ef=events.loc[order].reset_index();ef["scenario"]=ef.scenario.map(SHORT)
    table(ef[["scenario","oscillating","simulations","oscillating_AB","damping_defined"]].rename(columns={
        "scenario":"Norm","oscillating":"mit vollständiger Oszillation","simulations":"alle Läufe",
        "oscillating_AB":"davon A/B-Werte","damping_defined":"Dämpfung definiert"}))
    paragraph("Die gespeicherte Amplitude kann bereits aus einem prominenten Halbzyklus stammen. Der Dämpfungsindex wird bei fehlender ausreichender Information auf 0 gesetzt. "
              "Dieser Wert kann also sowohl fehlende auswertbare Dynamik als auch tatsächlich gleichbleibende Amplituden bedeuten. "
              "Die Datei conditional_descriptives.csv beschreibt daher Amplituden nur bei mindestens einer vollständigen Oszillation sowie Dämpfung nur bei definierten Amplituden. "
              "Diese bedingten Beschreibungen sind keine Sobol-Indizes: Das nachträgliche Entfernen von Zeilen würde das Design zerstören. "
              "Anteile beziehen sich auf dieses abhängige Simulationsdesign und sind keine beobachteten Wahrscheinlichkeiten realer Bevölkerungen.")
    od=summary[summary.output.isin(["oscillations_per_500_years","oscillation_occurrence","log1p_oscillation_rate"])].copy()
    od["scenario"]=od.scenario.map(SHORT);od["output"]=od.output.map(OUT_LABEL)
    table(od[["scenario","output","max_abs_ST_change_256_512","max_ST_conf_512"]].rename(columns={
        "scenario":"Norm","output":"Definition","max_abs_ST_change_256_512":"max ΔST 256→512","max_ST_conf_512":"max CI-Halbbreite"}))
    paragraph("Die binäre Kennzahl (mindestens eine vollständige Oszillation) und log(1+Häufigkeit) beantworten andere Fragen als die rohe Häufigkeit. "
              "Sie wurden als Robustheitsdiagnose ergänzt, nicht als nachträglicher Ersatz gewählt, um günstigere Resultate zu erhalten. "
              "Bei der Baseline helfen beide Transformationen nicht: Die Seltenheit bleibt. "
              "Bei den kombinierten Normen sinkt insbesondere für das Auftreten die Unsicherheit, die Stärke bzw. Häufigkeit einzelner Fälle bleibt separat zu prüfen.")
    paragraph("Wenn bereits die A/B-Werte eines gesamten Teil-Designs konstant sind, ist der Sobol-Schätzer nicht identifizierbar, selbst wenn einzelne Hybrid-Samples abweichen. "
              "SALib kann dann Nullwerte als Rückfallwert ausgeben. indices.csv erhält dafür ausdrücklich point_estimate_defined=False und eine Warnung; "
              "eine solche Null ist kein Beleg für fehlenden Einfluss. Dies betrifft beispielsweise die Oszillationshäufigkeit der Baseline in der zweiten 256er-Hälfte. "
              "Exakt gebundene Spitzenwerte werden mit einem Gleichheitszeichen dargestellt; bei vollständig gebundenen Rängen ist die Rangkorrelation nicht definiert.")
    heading("Elimination: erste Passage, Nichterreichen und Endzustand")
    paragraph("Die aktuelle Schwelle ist x ≥ 0,95. time_to_elimination misst deren erste Überschreitung; elimination_success prüft ausschließlich den Endwert. "
              "Keines davon beweist dauerhafte Elimination. Für eine Aussage über dauerhaftes Erreichen wäre eine eigene Definition samt Zeitverlauf nötig. "
              "Bei nie erreichter Schwelle ersetzt die ursprüngliche Auswertung die fehlende Zeit durch T+10.000=11.200. "
              "Zusätzlich wurden T=1.200 und 2T=2.400 als Ersatzwerte untersucht. T entspricht min(erste Passage, T), ist also eine begrenzte Zielgröße, keine unverzerrte Schätzung der unbekannten Ereigniszeit.")
    e=events.loc[order].reset_index();e["scenario"]=e.scenario.map(SHORT)
    table(e[["scenario","threshold_ever","threshold_at_end","reached_but_below_at_end","never_reached"]].rename(columns={
        "scenario":"Norm","threshold_ever":"jemals erreicht","threshold_at_end":"am Ende erreicht",
        "reached_but_below_at_end":"erreicht, am Ende darunter","never_reached":"nie erreicht"}))
    paragraph("Besonders relevant sind die Rückgänge unter die Schwelle bei den dynamischen Normen. Ein Zeit-bis-zum-ersten-Erreichen-Ranking darf nicht als Ranking dauerhafter Mitigation interpretiert werden. "
              "Die zusätzlichen Indizes threshold_ever_reached und threshold_at_end halten diese Fragen auseinander.")
    times=summary[summary.output.isin(["time_to_elimination_censored","first_passage_capped_T","first_passage_penalty_2T"])].copy()
    time_rows=[]
    for s in order:
        g=times[times.scenario.eq(s)].set_index("output")
        orig=full[full.scenario.eq(s)&full.output.eq("time_to_elimination_censored")].set_index("parameter")
        cap=full[full.scenario.eq(s)&full.output.eq("first_passage_capped_T")].set_index("parameter")
        time_rows.append({"Norm":SHORT[s],"CI bei Ersatz T":g.loc["first_passage_capped_T","max_ST_conf_512"],
                          "CI bei Ersatz 2T":g.loc["first_passage_penalty_2T","max_ST_conf_512"],
                          "CI bei Ersatz 11.200":g.loc["time_to_elimination_censored","max_ST_conf_512"],
                          "max ST-Änderung T vs 11.200":float((orig.ST-cap.ST).abs().max())})
    table(pd.DataFrame(time_rows));figure("censoring_comparison","Punktschätzer für drei explizite Ersatzwert-Konventionen; Unsicherheit steht in der Tabelle.")
    paragraph("Bei Belief-based und Approval senkt die Begrenzung auf T die extremen Unsicherheiten stark, beseitigt die Stichprobenempfindlichkeit aber nicht. "
              "Auch der binäre Indikator 'jemals erreicht' ist dort wegen der wenigen Nichtereignisse instabil. "
              "Der Indikator 'am Ende erreicht' ist besser besetzt, misst jedoch eine andere wissenschaftliche Frage. "
              "Die Wahl muss aus der Forschungsfrage folgen; Ergebnisse werden nicht aufgrund kleinerer Fehlerbalken umdefiniert.")
    heading("Endwert und zeitlicher Mitigationsanteil")
    paragraph("Zusätzlich wird mean_mitigation = x_area / 1.200 aus den gespeicherten Rohkennzahlen ausgewertet. "
              "Dies misst den Mittelwert über die gesamte simulierte Zeit, einschließlich der anfänglichen Phase mit festem Mitigationsanteil. "
              "Es ist kein Nachweis dauerhaft hoher Mitigation und keine Aussage ausschließlich über die späte Dynamik. "
              "Der Vergleich prüft, ob eine vom Moment der letzten Schwingung abhängige Endpunkt-Kennzahl die Sensitivitätsinterpretation verändert.")
    mean_rows=[]
    for s in order:
        g=summary[summary.scenario.eq(s)].set_index("output")
        mean_rows.append({"Norm":SHORT[s],"max ΔST Endwert":g.loc["final_x","max_abs_ST_change_256_512"],
                          "max ΔST Zeitmittel":g.loc["mean_mitigation","max_abs_ST_change_256_512"],
                          "max CI Endwert":g.loc["final_x","max_ST_conf_512"],
                          "max CI Zeitmittel":g.loc["mean_mitigation","max_ST_conf_512"],
                          "führend beim Zeitmittel":g.loc["mean_mitigation","top_512"]})
    table(pd.DataFrame(mean_rows))
    heading("Einzelne Extremfälle und konkrete Nachprüfungen")
    shortlist=pd.read_csv(destination/"targeted_review_samples.csv",sep=";")
    high=shortlist.sort_values("n_oscillations",ascending=False).drop_duplicates(["scenario","sample_index"]).head(6).copy()
    high["scenario"]=high.scenario.map(SHORT)
    table(high[["scenario","sample_index","n_oscillations","median_period","oscillation_amplitude","median_period_output_intervals","median_period_coupling_intervals"]].rename(columns={
        "scenario":"Norm","sample_index":"Sample","n_oscillations":"vollständige Zyklen","median_period":"Medianperiode (Jahre)",
        "oscillation_amplitude":"Amplitude","median_period_output_intervals":"Ausgabeintervalle/Periode","median_period_coupling_intervals":"Kopplungsintervalle/Periode"}))
    paragraph("Für Injunctive, dynamic2 / Sample 1763 wurden 1.636 Zyklen bei einer Medianperiode von 0,6 Jahren und einer Amplitude von etwa 0,489 gespeichert. "
              "Das sind nur sechs Kopplungsintervalle pro Medianperiode. Die Amplitude ist groß, sodass es kein bloßes winziges Rundungsrauschen sein muss. "
              "Die ursprünglichen Ergebnisdateien enthalten Kennzahlen, aber keine vollständigen Zeitreihen. Allein daraus lässt sich nicht entscheiden, ob der schnelle Verlauf Modelldynamik oder ein numerischer Effekt ist. "
              "targeted_review_samples.json enthält die vollständigen rekonstruierbaren Parameter; individual_block_influence.csv ordnet große ST-Zählerbeiträge ihren A-, AB- und B-Samples zu.")
    influential=influence[influence.output.eq("oscillations_per_500_years") & influence.scenario.isin(["Descriptive, injunctive, dynamic","Descriptive, injunctive, dynamic2","Injunctive, dynamic2"])].copy()
    influential=influential[influential.ST>=.2].sort_values("largest_block_numerator_share",ascending=False).head(7)
    influential["scenario"]=influential.scenario.map(SHORT)
    table(influential[["scenario","parameter","ST","largest_block_numerator_share","AB_sample_index"]].rename(columns={
        "scenario":"Norm","parameter":"Parameter","largest_block_numerator_share":"größter Blockanteil am ST-Zähler","AB_sample_index":"zugehöriges AB-Sample"}))
    paragraph("Der größte Blockanteil beschreibt Einfluss auf den Schätzer, nicht die Fehlerhaftigkeit einer Simulation. "
              "Gültige Extremfälle dürfen nicht allein wegen ihres Einflusses entfernt werden. Das zusätzlich berechnete Weglassen jeweils eines ganzen Blocks ist nur ein Stresstest; "
              "diese verkleinerten Stichproben werden nicht als neue balancierte Sobol-Designs ausgegeben.")
    paragraph("Auflösungsdetail aus der Implementierung: 24 angeforderte Ausgabepunkte pro Jahr ergeben bei einem Kopplungsintervall von 0,1 Jahren "
              "durch die Rundung pro Intervall tatsächlich 20 Ausgabeintervalle pro Jahr (Abstand 0,05 Jahre). "
              "Bei den verzögerten Modellen werden diese Ausgabewerte zugleich zur Interpolation der Historie verwendet. "
              "Eine dichtere Ausgabe ist deshalb nicht nur eine nachträgliche Verbesserung der Oszillationserkennung, sondern kann die simulierte Dynamik selbst beeinflussen.")
    probe_file=destination/"numerical_probes"/"results.csv"
    if probe_file.exists():
        heading("Numerische Gegenprüfungen der beiden Extremfälle",3)
        probes=pd.read_csv(probe_file,sep=";")
        paragraph("Je Fall werden drei vollständige 1.200-Jahre-Läufe verglichen: Referenz mit Kopplungsintervall 0,1 und angeforderter Ausgabedichte 24; "
                  "dichte Ausgabe mit unverändertem Kopplungsintervall 0,1 und Ausgabedichte 100; verfeinert mit Kopplungsintervall 0,05, Ausgabedichte 100, "
                  "rtol=1e-9, atol=1e-11 und maximalem BDF-Schritt 0,01 statt der regulären rtol=1e-7/atol=1e-9. "
                  "Die letzte Variante ändert Kopplungsintervall und Toleranzen gemeinsam; ihre einzelnen Beiträge werden damit nicht getrennt identifiziert. "
                  "Alle Änderungen erfolgen nur in den Prüfprozessen. Es werden keine Simulationsdefaults oder Quelldaten überschrieben.")
        complete=probes[probes.status.eq("completed")].sort_values(["case","variant"])
        if len(complete):
            for idx,row in complete.iterrows():
                with np.load(destination/"numerical_probes"/f"{row['case']}_{row['variant']}.npz") as series:
                    inside=(series["t"]>1100)&(series["t"]<1200)
                    tail_times=np.r_[1100,series["t"][inside],1200]
                    tail_x=np.interp(tail_times,series["t"],series["x"])
                    complete.loc[idx,"mean_x_last100"]=np.trapezoid(tail_x,tail_times)/100
                    complete.loc[idx,"mean_x_full"]=np.trapezoid(series["x"],series["t"])/1200
            comparisons=[]
            for case,group in complete.groupby("case"):
                reference=group[group.variant.eq("reference")]
                if reference.empty: continue
                reference=reference.iloc[0]
                for _,row in group.iterrows():
                    record={"case":case,"variant":row.variant}
                    for metric in ["n_oscillations","median_period","oscillation_amplitude","final_x",
                                   "mean_x_full","mean_x_last100","final_temperature","cumulative_emissions"]:
                        record[metric]=row[metric]
                        record[f"{metric}_difference_to_reference"]=row[metric]-reference[metric]
                    comparisons.append(record)
            save_table(pd.DataFrame(comparisons),destination/"numerical_probes","metric_comparison")
            table(complete[["case","variant","n_oscillations","median_period","oscillation_amplitude","final_temperature","final_x","cycles_resampled_reference_grid"]].rename(columns={
                "case":"Fall","variant":"Variante","n_oscillations":"Zyklen","median_period":"Medianperiode",
                "oscillation_amplitude":"Amplitude","final_temperature":"Endtemperatur","final_x":"Endanteil x",
                "cycles_resampled_reference_grid":"Zyklen bei 0,05-Ausgaberaster"}))
            table(complete[["case","variant","final_x","mean_x_full","mean_x_last100","cumulative_emissions"]].rename(columns={
                "case":"Fall","variant":"Variante","final_x":"x am Ende","mean_x_full":"mittleres x über 1.200 Jahre",
                "mean_x_last100":"mittleres x in den letzten 100 Jahren","cumulative_emissions":"kumulierte Emissionen"}))
        failed=probes[~probes.status.eq("completed")]
        if len(failed):table(failed[["case","variant","status","error"]])
        paragraph("Die Spalte 'Zyklen bei 0,05-Ausgaberaster' nimmt jeweils denselben berechneten Verlauf und wertet ihn auf dem ursprünglichen 0,05-Jahre-Raster erneut aus. "
                  "Das isoliert den Einfluss der Kennzahlerkennung bei festem Verlauf; die dichte Simulation selbst verwendet weiterhin eine dichtere Verzögerungshistorie. "
                  "Originalvergleich, Laufzeiten, Quellcode-Prüfsummen und komprimierte Zeitreihen stehen unter numerical_probes. "
                  "Diese zwei Fallprüfungen validieren nicht sämtliche 33.280 Simulationen.")
        notes=destination/"numerical_probes"/"interpretation.txt"
        if notes.exists():paragraph(notes.read_text(encoding="utf-8"))
        if (destination/"numerical_probe_comparison.png").exists():figure("numerical_probe_comparison","Direkter Vergleich der numerischen Varianten für zwei auffällige Parametersätze.")
    heading("Detaillierte Konvergenz je Norm")
    for s in order:
        heading(s,3)
        paragraph(judgments[s])
        sub=original[original.scenario.eq(s)].set_index("output").loc[ORIGINAL].reset_index()
        sub["output"]=sub.output.map(OUT_LABEL)
        table(sub[["output","max_abs_ST_change_128_256","max_abs_ST_change_256_512","max_abs_ST_change_halves","top_256","top_512","max_ST_conf_512"]].rename(columns={
            "output":"Zielgröße","max_abs_ST_change_128_256":"max Δ 128→256","max_abs_ST_change_256_512":"max Δ 256→512",
            "max_abs_ST_change_halves":"max Δ erste/zweite Hälfte","top_256":"führend 256","top_512":"führend 512","max_ST_conf_512":"max CI-Halbbreite"}))
        figure("curves_"+contexts[s]["folder"],"Verlauf der ST-Punktschätzer; unterschiedliche Achsenskalierungen je Zielgröße.")
    heading("Prioritäten für die weitere Arbeit")
    paragraph("1. Ergebnisdarstellung nach Zielgröße: Klimagrößen sowie mittleren und finalen Mitigationsanteil getrennt berichten; S1 und ST samt Unsicherheit zeigen. "
              "Für Dauerschwingungen die Phasenempfindlichkeit des Endwerts erläutern. "
              "Bei den drei injunktiven Kombinationen bzw. Static injunctive ist x_target konsistent führend. "
              "Bei den dynamischen Einzelmodellen führt für Klima häufig temperature_factor, für Dynamik dagegen tau_STref bzw. tau/c_dyn. "
              "Bei der Baseline social_norm_factor und delta als führende Gruppe behandeln, nicht ihre knappe Reihenfolge überinterpretieren.")
    paragraph("2. Die numerischen Gegenprüfungen für I/Dynamic2 / Sample 1763 und D/I/Dynamic2 / Sample 267 sind oben dokumentiert. "
              "Für eine breitere Absicherung wären als Nächstes I/Dynamic2 / Sample 3697, D/I/Dynamic2 / Sample 1653 und die einflussreichen "
              "D/I/Dynamic-Fälle aus der beigefügten Tabelle zu prüfen. Dabei Zeitverläufe speichern und Kopplungsintervall, Ausgabedichte und Toleranzen "
              "systematisch variieren. Die erneute Kennzahlerkennung auf demselben Verlauf von einer Änderung der Verzögerungshistorie unterscheiden.")
    paragraph("3. Zusätzliche globale Stichproben zuerst für Belief-based und Approval einplanen, sofern deren Klima-/Mitigationsrangfolgen benötigt werden. "
              "Eine Erweiterung desselben Designs auf N=1.024 kann die vorhandenen 512 Blöcke wiederverwenden; ergänzend wäre eine unabhängig gescrambelte Sequenz hilfreich. "
              "Für diese beiden Modelle mit jeweils drei variierenden Parametern wären bei Wiederverwendung insgesamt 5.120 zusätzliche Simulationen nötig. "
              "Die derzeitige Standard-CLI bietet dafür keine hier implementierte Wiederverwendung der Ergebnisse; ein unveränderter Neustart würde auch die ersten 512 neu simulieren. "
              "Bei seltenen Oszillationen ist bloßes Verdoppeln keine garantierte Lösung. Eine gezielte Bereichsstudie kann deren Mechanismus untersuchen, beantwortet aber eine lokale statt der bisherigen globalen Fragestellung.")
    paragraph("4. Für die Masterarbeit die Eliminationsfrage festlegen: erste Überschreitung, Zustand am Ende oder dauerhaftes Erreichen. "
              "Die hier ergänzten Definitionen transparent nebeneinander zeigen. Keine erfolgreiche Teilmenge nachträglich als vollständiges Sobol-Design auswerten. "
              "Ein neuer gemittelter Gesamtscore wird nicht stillschweigend als Ersatz eingeführt; ranking_sensitivity.csv zeigt lediglich, wie stark die Wahl der einbezogenen Zielgrößen die Reihenfolge verändert.")
    heading("Dateien und Reproduzierbarkeit")
    paragraph(f"Quelle: {source}. Quell-Dateien samt SHA-256-Prüfsummen stehen in source_manifest.json. "
              "indices.csv enthält alle S1/ST-Indizes und originalgetreuen Konfidenzhalbbreiten für 128/256/512 sowie die zweite 256er-Hälfte. "
              "convergence_summary.csv bündelt Differenzen und Rangfolgen; bootstrap_diagnostics.csv dokumentiert degenerierte Resamples und Einflussdiagnosen. "
              "Weitere Tabellen: audit.csv, reproduction_checks.csv, event_counts.csv, conditional_descriptives.csv, ranking_sensitivity.csv und individual_block_influence.csv. "
              "Die Begriffe 'constant' bzw. 'nicht bestimmbar' dürfen nicht als Beweis eines irrelevanten Parameters verstanden werden. "
              "Der Auswertungscode sensitivity_review.py liegt im Projekt; test_sensitivity_review.py prüft zentrale Design- und Analyseannahmen.")
    paragraph("Nicht geprüft: unabhängige Zufalls-Seeds, größere Stichproben als 512, Sensitivität gegen andere Parameterbereiche, "
              "numerische Konvergenz aller übrigen Zeitverläufe und das ausgeschlossene Agentenmodell. "
              "Die Resultate erlauben Aussagen zur Parameterempfindlichkeit innerhalb eines Normmodells; wegen unterschiedlicher Parameter und Bereiche sind Gesamtscores kein Leistungsranking der Normen.")
    md=[];body=[]
    for kind,value in blocks:
        if kind=="heading":
            text,level=value;md.append("#"*level+" "+text);body.append(f"<h{level}>{html.escape(text)}</h{level}>")
        elif kind=="paragraph":
            md.append(value);body.append("<p>"+html.escape(value)+"</p>")
        elif kind=="table":
            md.append(md_table(value));display=value.copy()
            for col in display:display[col]=display[col].map(format_number)
            body.append('<div class="table-wrap">'+display.to_html(index=False,escape=True,border=0)+'</div>')
        elif kind=="figure":
            name,caption=value;md.append(f"![{caption}]({name}.png)")
            encoded=base64.b64encode((destination/f"{name}.png").read_bytes()).decode()
            body.append(f'<figure><img src="data:image/png;base64,{encoded}" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>')
    (destination/"Bericht.md").write_text("\n\n".join(md)+"\n",encoding="utf-8")
    css="""body{font:16px/1.65 system-ui,Segoe UI,sans-serif;color:#172b42;background:#edf2f6;margin:0}main{max-width:1240px;margin:32px auto;background:white;padding:36px 44px;border-radius:8px}h1{font-size:32px;line-height:1.25;color:#12395a}h2{margin-top:48px;padding-top:20px;border-top:2px solid #dce6ee;font-size:24px}h3{margin-top:36px;color:#155e75}p{max-width:1060px}.table-wrap{overflow-x:auto;margin:22px 0}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.45}th{background:#153a56;color:white;text-align:left;padding:11px}td{padding:10px;border-bottom:1px solid #dce6ee;vertical-align:top}tr:nth-child(even){background:#f3f7fa}figure{margin:28px 0}img{max-width:100%;height:auto}figcaption{font-size:13px;color:#475569} @media print{body{background:white}main{margin:0;padding:0}h2,h3{break-after:avoid}figure,tr{break-inside:avoid}}"""
    document='<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Sensitivitätsanalyse – Konvergenzprüfung</title><style>'+css+'</style></head><body><main>'+"\n".join(body)+'</main></body></html>'
    (destination/"Bericht.html").write_text(document,encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--reuse-analysis",action="store_true",help="Reuse saved audit tables, checking source hashes first")
    args=parser.parse_args();source=args.source.resolve();destination=args.output.resolve()
    if destination==source or source in destination.parents:
        raise ValueError("Review output must be separate from the source run")
    destination.mkdir(parents=True,exist_ok=True)
    if args.reuse_analysis:
        sources=json.loads((destination/"source_manifest.json").read_text())
        for item in sources:
            path=Path(item["file"])
            if source not in path.resolve().parents:raise ValueError("Cache belongs to another source")
            if hashlib.sha256(path.read_bytes()).hexdigest()!=item["sha256"]:raise ValueError("Source changed")
        contexts=json.loads((destination/"contexts.json").read_text())
        frames={name:pd.read_csv(destination/f"{name}.csv",sep=";") for name in ["indices","bootstrap_diagnostics","audit","reproduction_checks","event_counts","conditional_descriptives"]}
    else:
        frames,contexts,sources=collect(source,destination)
        (destination/"contexts.json").write_text(json.dumps(contexts,indent=2),encoding="utf-8")
    frames=summarize(frames,destination)
    influence=detailed_influence(source,contexts,destination)
    plots=make_figures(frames,contexts,destination)
    plot_numerical_probes(destination)
    write_report(frames,contexts,destination,source,plots,influence)
    provenance={"created_utc":datetime.now(timezone.utc).isoformat(),"source":str(source),
                "versions":{lib:importlib.metadata.version(lib) for lib in ["SALib","numpy","scipy","pandas","matplotlib"]},
                "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "N_values":[128,256,512],"original_bootstrap_resamples":100,"diagnostic_bootstrap_resamples":2000,
                "bootstrap_seed":42,"nearzero_variance_relative_threshold":1e-12,"new_global_design_simulations":0,
                "numerical_probe_runs":len(pd.read_csv(destination/"numerical_probes"/"results.csv",sep=";")) if (destination/"numerical_probes"/"results.csv").exists() else 0}
    (destination/"review_provenance.json").write_text(json.dumps(provenance,indent=2),encoding="utf-8")
    print(f"Review complete: {destination/'Bericht.html'}",flush=True)


if __name__=="__main__":main()
