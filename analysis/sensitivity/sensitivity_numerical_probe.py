"""Bounded numerical checks of two preselected extreme sensitivity samples."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from time import monotonic

import numpy as np
import pandas as pd

from utils.bounded_process_map import bounded_map
from utils.paths import PROJECT_ROOT


def json_safe(value):
    if isinstance(value, dict): return {k:json_safe(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [json_safe(v) for v in value]
    if isinstance(value, np.generic): value=value.item()
    if isinstance(value,float) and not np.isfinite(value): return None
    return value


def run_probe(task):
    import model.model_equations as model_equations
    import model.solvers as solvers
    from scipy.integrate import solve_ivp
    from analysis.simulation_metrics import compute_run_metrics, compute_oscillation_metrics
    original = solvers.SOLVERS["BDF"]
    if task["strict"]:
        def precise(fun,t_span,y0,t_eval,**kwargs):
            return solve_ivp(fun,t_span,y0,method="BDF",t_eval=t_eval,
                             rtol=1e-9,atol=1e-11,max_step=min(.01,t_span[1]-t_span[0]))
        solvers.SOLVERS["BDF"] = precise
    start=monotonic()
    try:
        result=model_equations.simulate(extension=task["parameters"],simulation_time=1200,seed=42,
                                       coupling_interval=task["coupling"],output_points_per_year=task["density"],
                                       solver="BDF",verbose=False)
        metrics=compute_run_metrics(result,task["parameters"])
        sim=result["simulation"]
        times=np.asarray(sim.t);x=np.asarray(sim.x)
        # Pure detection comparison: same dense trajectory, sampled at the
        # reference's actual 0.05-year grid. Delay integration is not repeated.
        reference_times=np.linspace(0,1200,24001)
        resampled=compute_oscillation_metrics(reference_times,np.interp(reference_times,times,x))
        file=Path(task["output"])/f"{task['case']}_{task['variant']}.npz"
        np.savez_compressed(file,t=times,x=x,T=np.asarray(sim.T))
        return {"case":task["case"],"scenario":task["scenario"],"sample_index":task["sample_index"],
                "variant":task["variant"],"coupling":task["coupling"],"density_requested":task["density"],
                "strict":task["strict"],"elapsed_seconds":monotonic()-start,
                "actual_output_intervals_per_year":1/np.median(np.diff(times)),
                **{k:metrics[k] for k in ["n_oscillations","median_period","oscillation_amplitude","damping_index","final_x","final_temperature","cumulative_emissions"]},
                "cycles_resampled_reference_grid":resampled["n_oscillations"],
                "amplitude_resampled_reference_grid":resampled["oscillation_amplitude"]}
    finally:
        solvers.SOLVERS["BDF"] = original


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review",type=Path,required=True)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--only-case",choices=["inj1763","did267"])
    parser.add_argument("--only-variant",choices=["reference","dense","refined"])
    parser.add_argument("--timeout-minutes",type=float,default=15)
    parser.add_argument("--workers",type=int,default=3)
    args=parser.parse_args()
    output=args.review.resolve()/"numerical_probes";output.mkdir(exist_ok=True)
    selected=json.loads((args.review/"targeted_review_samples.json").read_text())
    cases=[("Injunctive, dynamic2",1763,"inj1763"),("Descriptive, injunctive, dynamic2",267,"did267")]
    tasks=[]
    for scenario,index,case in cases:
        row=next(r for r in selected if r["scenario"]==scenario and r["sample_index"]==index)
        for variant,coupling,density,strict in [("reference",.1,24,False),("dense",.1,100,False),("refined",.05,100,True)]:
            tasks.append(dict(case=case,scenario=scenario,sample_index=index,parameters=row["parameters"],
                              variant=variant,coupling=coupling,density=density,strict=strict,output=str(output)))
    source_paths = {
        "model_equations.py": PROJECT_ROOT / "model" / "model_equations.py",
        "simulation_metrics.py": PROJECT_ROOT / "analysis" / "simulation_metrics.py",
        "solvers.py": PROJECT_ROOT / "model" / "solvers.py",
        "sensitivity_numerical_probe.py": Path(__file__),
    }
    hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in source_paths.items()}
    previous_hashes=output/"code_hashes.json"
    if previous_hashes.exists():
        previous=json.loads(previous_hashes.read_text())
        for name in ["model_equations.py","simulation_metrics.py","solvers.py"]:
            if previous[name]!=hashes[name]:raise ValueError(f"Model code changed since original probes: {name}")
    else:
        previous_hashes.write_text(json.dumps(hashes,indent=2),encoding="utf-8")
    selected_tasks=[t for t in tasks if (not args.only_case or t["case"]==args.only_case)
                    and (not args.only_variant or t["variant"]==args.only_variant)]
    if not (output/"tasks.json").exists():
        (output/"tasks.json").write_text(json.dumps(tasks,indent=2),encoding="utf-8")
    rows=pd.read_csv(output/"results.csv",sep=";").to_dict("records") if (output/"results.csv").exists() else []
    run_record={"tasks":selected_tasks,"timeout_minutes":args.timeout_minutes,"workers":args.workers,"code_hashes":hashes}
    with (output/"execution_history.jsonl").open("a",encoding="utf-8") as handle:
        handle.write(json.dumps(run_record)+"\n")
    for index,outcome in bounded_map(run_probe,selected_tasks,workers=args.workers,timeout_seconds=args.timeout_minutes*60):
        task=selected_tasks[index]
        label={k:task[k] for k in ["case","scenario","sample_index","variant"]}
        if outcome["status"]=="completed":row={**label,**outcome["result"],"status":"completed"}
        else:row={**label,"status":outcome["status"],"error":outcome.get("error_message","")}
        prior=[r for r in rows if r["case"]==row["case"] and r["variant"]==row["variant"]]
        with (output/"attempt_history.jsonl").open("a",encoding="utf-8") as handle:
            handle.write(json.dumps(json_safe({"previous":prior,"new":row}),allow_nan=False)+"\n")
        rows=[r for r in rows if not (r["case"]==row["case"] and r["variant"]==row["variant"])]
        rows.append(row)
        pd.DataFrame(rows).to_csv(output/"results.csv",sep=";",index=False)
        print(json.dumps(row),flush=True)
    for scenario,index,case in cases:
        folder=scenario.replace("/","_").replace(" ","_")
        stored=pd.read_csv(args.source/folder/"simulation_outputs.csv",sep=";").set_index("sample_index").loc[index]
        references=[r for r in rows if r["case"]==case and r["variant"]=="reference" and r["status"]=="completed"]
        if references:
            ref=references[0]
            comparison={k:{"stored":float(stored[k]),"rerun":float(ref[k]),"difference":float(ref[k]-stored[k])}
                        for k in ["n_oscillations","median_period","oscillation_amplitude","final_x","final_temperature","cumulative_emissions"]}
            (output/f"{case}_reference_comparison.json").write_text(json.dumps(comparison,indent=2),encoding="utf-8")


if __name__=="__main__":main()
