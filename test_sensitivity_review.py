"""Scientific safeguards for the read-only sensitivity reanalysis."""
import numpy as np
import pandas as pd
import pytest
from SALib.sample import sobol as sampler

from sensitivity_review import (ORIGINAL, analyze, bootstrap_diagnostics,
                                derive_outputs, maximum_index_change, validate_design)


def test_additive_model_recovers_known_variance_shares():
    problem = {"num_vars": 2, "names": ["a", "b"], "bounds": [[0,1],[0,1]]}
    samples = sampler.sample(problem, 4096, calc_second_order=False, seed=42)
    result, _ = analyze(problem, samples[:,0] + 2*samples[:,1])
    assert np.allclose(result["ST"], [.2,.8], atol=.002)
    assert np.allclose(result["S1"], [.2,.8], atol=.002)


def test_prefix_selection_preserves_complete_blocks_and_rejects_reordering():
    problem = {"num_vars": 2, "names": ["a", "b"], "bounds": [[0,1],[0,1]]}
    samples = pd.DataFrame(sampler.sample(problem, 512, calc_second_order=False, seed=42), columns=["a","b"])
    samples.insert(0,"sample_index",np.arange(len(samples)))
    outputs = pd.DataFrame({"sample_index":np.arange(len(samples)),"status":"completed"})
    validate_design(samples.iloc[:128*4],outputs.iloc[:128*4],problem,128)
    bad = samples.copy()
    bad.loc[1,"b"] = .999
    with pytest.raises(ValueError,match="layout"):
        validate_design(bad,outputs,problem,512)
    with pytest.raises(ValueError,match="out of order"):
        validate_design(samples,outputs.iloc[::-1],problem,512)
    outputs.loc[4,"status"] = "failed"
    with pytest.raises(ValueError,match="Incomplete"):
        validate_design(samples,outputs,problem,512)


def test_endpoint_and_first_passage_are_distinct_without_dropping_rows():
    frame = pd.DataFrame({name:[0.,0.,0.] for name in ORIGINAL})
    frame["time_to_elimination"] = [200.,500.,np.nan]
    frame["threshold_reached"] = [True,True,False]
    frame["elimination_success"] = [False,True,False]
    frame["n_oscillations"] = [0.,2.,1.]
    frame["x_area"] = [360.,600.,240.]
    frame["oscillations_per_500_years"] = [0.,2*500/1200,500/1200]
    out = derive_outputs(frame,1200)
    assert len(out)==3
    assert out.threshold_ever_reached.tolist()==[1.,1.,0.]
    assert out.threshold_at_end.tolist()==[0.,1.,0.]
    assert out.first_passage_capped_T.tolist()==[200.,500.,1200.]
    assert out.first_passage_penalty_2T.tolist()==[200.,500.,2400.]
    assert out.oscillation_occurrence.tolist()==[0.,1.,1.]
    assert out.mean_mitigation.tolist()==[.3,.5,.2]


def test_rare_event_bootstrap_detects_constant_resamples():
    blocks=np.zeros((64,3))
    blocks[0,0]=1
    blocks[1,1]=1
    diag=bootstrap_diagnostics(blocks.ravel(),1,repetitions=4000)
    # Probability the only nonzero A/B block is missed: (63/64)**64.
    assert abs(diag["bootstrap_constant_fraction"]-(63/64)**64)<.04
    assert diag["bootstrap100_constant_count"]>0
    assert diag["bootstrap_nearzero_fraction"]>=diag["bootstrap_constant_fraction"]


def test_constant_response_is_flagged_as_uninformative():
    problem={"num_vars":1,"names":["x"],"bounds":[[0,1]]}
    result, flag=analyze(problem,np.full(128*3,5.))
    assert flag=="constant"
    assert result["ST"].tolist()==[0.]
    assert bootstrap_diagnostics(np.full(128*3,5.),1)["constant_output"]


def test_variable_hybrid_with_constant_baselines_is_not_declared_zero_effect():
    problem={"num_vars":1,"names":["x"],"bounds":[[0,1]]}
    blocks=np.zeros((128,3))
    blocks[0,1]=1.
    _,warning=analyze(problem,blocks.ravel())
    assert "A/B constant" in warning


def test_undefined_half_does_not_produce_a_convergence_difference():
    first=pd.DataFrame({"ST":[.2,.8],"point_estimate_defined":[True,True]},index=["a","b"])
    second=pd.DataFrame({"ST":[0.,0.],"point_estimate_defined":[False,False]},index=["a","b"])
    assert np.isnan(maximum_index_change(first,second))
    second=pd.DataFrame({"ST":[.7,.3],"point_estimate_defined":[True,True]},index=["b","a"])
    assert np.isclose(maximum_index_change(first,second),.1)
