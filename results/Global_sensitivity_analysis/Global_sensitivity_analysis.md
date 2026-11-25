Note: In this file i want to store all relevant informations that can be extracted from the given analysis method. The goal is not only to answer the researchquestions, but to note everything that might be interesting for the thesis that is related to the given method. Any sources (images/videos/logs) can be stored in results/material and should be referenced here using its path.

# Interesting findings and Results

## No social norm
### Parameter

- kappa has least influence
- qualitatively same distribution over all goal-variables

![Parameter ranking by group](<No_social_norm/ranking_balken_gruppen_gesamt.png>)

![Parameter ranking by output](<No_social_norm/ranking_balken_zielvariablen.png>)

### Classifications

- no damped/persistent oscillations
- 56.2% approach to 1
- 10.9% collapse to 0
- 32.8% transitional / unresolved

![Behavioural classifications](<No_social_norm/behaviour_class_frequencies.png>)

## Baseline
### Parameter

- temperature_factor dominates all categories. 
- Kappa has almost no influence
-> This differs from the bury-paper where kappa was more influential than beta. Why is that? in the bury paper they used the same exact norm? (but a local sensi)
- beta and social_norm_factor are almost same influential
- results of the sensitivity are almost the same for all goal-variables

![Parameter ranking by group](<baseline/ranking_balken_gruppen_gesamt.png>)

![Parameter ranking by output](<baseline/ranking_balken_zielvariablen.png>)

### Classifications

- in 89.9% the maximum annual slope is steeper than the reference without a norm implementation
- in 78% of all cases where x reaches <= 5%, it's reached earlier than the reference
- in 73.3% of all cases where x reaches >= 95%, it's reached later than the reference
-> faster fall, but slower rise, even though the maximum annual slope is steeper in most cases 
-guess: maybe there are more cases where x reaches <=5%??
-> actually 75.2% of all runs are classified as approach to 1, only in 22% of the cases x collapses to 0 
- 0.13% are stable intermediate? I guess thats an error in the classification
- no damped/persistent osicllations
- Only 2.7% are transitional/unresolved.
    - Reason: The norm-equation of baseline promotes trajectories towards 0/1. Therefore there are less runs where x is still transitional

![Behavioural classifications](<baseline/behaviour_class_frequencies.png>)

![Comparison with no-norm reference](<baseline/without_norm_comparison_frequencies.png>)

## Belief-based / intention motivation
### Parameter

- kappa is least influential (that differs to the bury paper)
- temperature-factor dominates
- beta and N have almost the same values
- social_norm_factor is second last place
- results do not change qualitatively between the different goal-variables

![Parameter ranking by group](<Belief-based___intention_motivation/ranking_balken_gruppen_gesamt.png>)

![Parameter ranking by output](<Belief-based___intention_motivation/ranking_balken_zielvariablen.png>)

### Classifications

- similar classifications to the no-norm reference
    - 30% of all runs are transitional/unresolved
    - 58.6% approaches to 1
    - 11.7% collapse to 0
- timing and slope are pretty even. Seems like they do change depending on N. Due to the fact that N is evenly distributed between -1 an 1, thats the  that i expected
- no damped/persistent oscilaations

![Behavioural classifications](<Belief-based___intention_motivation/behaviour_class_frequencies.png>)

![Comparison with no-norm reference](<Belief-based___intention_motivation/without_norm_comparison_frequencies.png>)

## Observation-based___intention_motivation_(agents)
### Parameter

- TODO: eta wird in neuen simulationen durch social_norm_factor ersetzt und erhält neuen Wertebereich.
- Daher muss diese Norm nochmal neu analysiert werden


- temperature_factor and beta dominate mitigation
- climate is dominated by the temperature_factor
- dynamics are dominated by beta
- network_size has a value of 0 in mean x, peak temperature anomaly and cumulative emissions. However, it has little influence on if x ever reaches >=95% and oscillations

![Parameter ranking by group](<Observation-based___intention_motivation_(agents)/ranking_balken_gruppen_gesamt.png>)

![Parameter ranking by output](<Observation-based___intention_motivation_(agents)/ranking_balken_zielvariablen.png>)

### Classifications

- ...

![Behavioural classifications](<Observation-based___intention_motivation_(agents)/behaviour_class_frequencies.png>)

![Comparison with no-norm reference](<Observation-based___intention_motivation_(agents)/without_norm_comparison_frequencies.png>)

## Observation_based___approval_(punish_only_one_behaviour)
### Parameter

- dominated by temperature_factor
- beta has second highest impact

![Parameter ranking by group](<Observation_based___approval_(punish_only_one_behaviour)/ranking_balken_gruppen_gesamt.png>)

![Parameter ranking by output](<Observation_based___approval_(punish_only_one_behaviour)/ranking_balken_zielvariablen.png>)

### Classifications

- 86.5% of all runs end at x>=95%
- no damped/persistent oscillations
- 88% of those runs that end at x>=95% are faster (makes sense because only mitigators benefit from this norm)
- 70% of those runs that end at x<=5% are slower (makes sense because non-mitigators likely are punished by the norm and can never benefit from it)
- 63.6% of all runs have a higher max annual change: runs where x->1
- 31.1% are flatter: runs where x->0

![Behavioural classifications](<Observation_based___approval_(punish_only_one_behaviour)/behaviour_class_frequencies.png>)

![Comparison with no-norm reference](<Observation_based___approval_(punish_only_one_behaviour)/without_norm_comparison_frequencies.png>)

## Static injunctive
### Parameter

- social_norm_factor has high impact on the dynamics (first x>=95% & oscillations), but low impact on the climate (cumulative emissions & finaltemperature)
    - it has low impact on the actual outcome after 600 years, but high impact on fluctuations

![Parameter ranking by group](<Static_injunctive/ranking_balken_gruppen_gesamt.png>)

![Parameter ranking by output](<Static_injunctive/ranking_balken_zielvariablen.png>)

### Classifications

- 16% stable intermediate level (no oscillation)
- 24.5% damped oscillations
- 0% persistent oscillations
- pretty high amount of transitional / unresolved (35%)
- 47.6% of all runs reach x<=5% later compared to the no-norm reference (10.6% are earlier)
- 43.5% of all runs reach x<=95% earlier compared to the no-norm reference (25.6% are earlier)
-> faster if x->1, slower if x->0 (only cases where both reach x>=95% or x<=5% are considered here)
- most runs (54.2%) are flatter comapred to the no-norm reference
- 29.4% are not comaprable
    - TODO: This will be fixed in new simulations

![Behavioural classifications](<Static_injunctive/behaviour_class_frequencies.png>)

![Comparison with no-norm reference](<Static_injunctive/without_norm_comparison_frequencies.png>)

## Dynamic_social_norm
### Parameter

- dominated by temperature_factor, beta has second highest impact
- tau_xp has lowest impact (0.002)


![Parameter ranking by group](<Dynamic_social_norm/ranking_balken_gruppen_gesamt.png>)

![Parameter ranking by output](<Dynamic_social_norm/ranking_balken_zielvariablen.png>)

### Classifications

- no damped/persistent oscilations
- 71.7% approach to 1
- 78% of all runs reach x<=5% earlier compared to the no-norm reference (0% are later)
    - so if x<=5 is reached with this norm, then its always reached earlier>
- 59.4% of all runs reach x<=95% later compared to the no-norm reference (26.1% are earlier)
- obviously most runs are steeper than the no-norm-reference (94.8%)
- only 1.4% are flatter

![Behavioural classifications](<Dynamic_social_norm/behaviour_class_frequencies.png>)

![Comparison with no-norm reference](<Dynamic_social_norm/without_norm_comparison_frequencies.png>)

## Dynamic_social_norm 2
### Parameter

- interesting: here the norm-specific parameter all have 0.001 Mean ST. (extreme low impact)
- dominated by temperature_factor, second highest is beta, kappa has low impact

![Parameter ranking by group](<dynamic_social_norm2/ranking_balken_gruppen_gesamt.png>)

![Parameter ranking by output](<dynamic_social_norm2/ranking_balken_zielvariablen.png>)

### Classifications

- no damped/persistent oscilations
- 63.5% approach to 1
- 43.8% of all runs reach x<=5% equally(!) fast compared to the no-norm reference (34.2% are earlier) (0% are later)
    - so if x<=5 is reached with this norm, then its always reached earlier (similar to the other dynamic norm)
- 59.8% of all runs reach x<=95% earlier compared to the no-norm reference (28.1% are earlier) 
- In 67% of the runs the largest annual change is steeper than the no-norm reference (16.8% flatter)

![Behavioural classifications](<dynamic_social_norm2/behaviour_class_frequencies.png>)

![Comparison with no-norm reference](<dynamic_social_norm2/without_norm_comparison_frequencies.png>)

## Descriptive,_injunctive,_dynamic
### Parameter

- x_target has higher impact than temperature_factor.
- norm with most evenly distribted parameters so far.
- 

![Parameter ranking by group](<Descriptive,_injunctive,_dynamic/ranking_balken_gruppen_gesamt.png>)

![Parameter ranking by output](<Descriptive,_injunctive,_dynamic/ranking_balken_zielvariablen.png>)

### Classifications

- mixed classifications
- 16% stable intermediate level
- only 5.2% damped oscillations 
- only 1 run (0%) with persistent oscillations
- approx. 30% differ in whether theyve reached x<=5% or x>=95% at all
    - 8.8% of simulations with the no-norm-reference (with same parameters) didnt reach x<=5% at all, even though the norm-version reached it
    - 21.1% of simulations with this norm didnt reach x<=5% even though the no-norm-reference reached it
    - 26.1% of simulations with this norm didnt reach x>=95% even though the no-norm-reference reached it
- this norm is faster than the no-norm-reference, for those runs where x reaches x<=5%
- it's obviously steeper, due to the dynamic influence

-> using this may lead to completely different behaviour
    

![Behavioural classifications](<Descriptive,_injunctive,_dynamic/behaviour_class_frequencies.png>)

![Comparison with no-norm reference](<Descriptive,_injunctive,_dynamic/without_norm_comparison_frequencies.png>)

## Descriptive,_injunctive,_dynamic 2
### Parameter

- here temperature_factor has slightly higher value than x_target
- temperature_factor has low impact on Oscillations per 500 years. tau has pretty high impact here.


![Parameter ranking by group](<Descriptive,_injunctive,_dynamic2/ranking_balken_gruppen_gesamt.png>)

![Parameter ranking by output](<Descriptive,_injunctive,_dynamic2/ranking_balken_zielvariablen.png>)

### Classifications

- lots of stable intermediate runs (37.3%)
- lots of transitional / unresolved runs
- only 0.2% persistent oscillations
- 8.7% damped oscillations

- approximately equally fast as no-norm-reference
- 38.1% of simulations with this norm didnt reach x<=5% even though the no-norm-reference reached it
- 48.3 of simulations with this norm didnt reach x>=95% even though the no-norm-reference reached it
-> using this may lead to completely different behaviour


![Behavioural classifications](<Descriptive,_injunctive,_dynamic2/behaviour_class_frequencies.png>)

![Comparison with no-norm reference](<Descriptive,_injunctive,_dynamic2/without_norm_comparison_frequencies.png>)


## Comparing the norms
...


## Main results
- If a simple dynamic norm (not combined with any other norms) is used and x reaches <=5% then the norm implementation always reaches this point faster or equally fast compared to the no-norm reference. 
- The impact of kappa is far smaller than one would've expected after reading the bury paper?????????





# Research-questions

## Which parameters have the most impact on the mitigation share?

## Which parameters have the most impact on qualitatively different trajectories compared between the norms?

## Which parameters lead to stronger oscillations?

## Which parameters have the most impact on climate change and emissions?

# Additional findings by Codex:

## Sample-size assessment (19 November 2026)

The completed N=2048 run was assessed using nested N=256/512/1024/2048 prefixes, without rerunning simulations. Broad ST rankings are largely stable (unchanged top-three parameter sets in 56/58 nonconstant norm-output pairs), but oscillation frequency for the combined dynamic norms remains uncertain. N=2048 is not demonstrably excessive. Nested prefixes are dependent and do not replace independent scrambling replications.

See the [full assessment and reproducible tables](../../support/reviews/sample_size_2048/README.md) for precision goals, confidence half-widths and limitations.

## Cause of oscillation-frequency uncertainty (20 November 2026)

The principal identified source is the high leverage of a few rapidly oscillating parameter combinations in the squared-difference Sobol estimator. For the combined dynamic2 norm, five of 2048 blocks supply about 70% of the tau numerator; five of 4096 A/B values supply about 70% of the estimated denominator variance. A matched pair differing only in tau produces 102 versus zero cycles. Targeted numerical refinements preserve the large cycle counts in the two influential dynamic2 cases (102 and 78); shifted 100-year windows retain 26 and 20 cycles despite large changes in endpoint x. One-cycle boundary and numerical effects exist, but do not explain the large differences in these checked cases. This is a targeted diagnosis, not a numerical-convergence proof for every sample or a complete investigation of binary oscillation occurrence.

See the [dated investigation, figures, tables and limitations](../../support/reviews/sample_size_2048/README.md#cause-investigation-20-november-2026).
