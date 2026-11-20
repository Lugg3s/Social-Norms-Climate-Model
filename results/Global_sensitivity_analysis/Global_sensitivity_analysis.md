Note: In this file i want to store all relevant informations that can be extracted from the given analysis method. The goal is not only to answer the researchquestions, but to note everything that might be interesting for the thesis that is related to the given method. Any sources (images/videos/logs) can be stored in results/material and should be referenced here using its path.

# Interesting findings and Results

## No social norm
### Parameter
- kappa has least influence
- qualitatively same distribution over all goal-variables


### Classifications
- no damped/persistent oscillations
- 56.2% approach to 1
- 10.9% collapse to 0
- 32.8% transitional / unresolved
- 22% of all cases never reached x<=5%
- 12% of all cases never reached x>=95%

## Baseline
### Parameter
- temperature_factor dominates all categories. 
- Kappa has almost no influence
-> This differs from the bury-paper where kappa was more influential than beta. Why is that? in the bury paper they used the same exact norm? The plot for Endtemperatur should be exactly the same as in the bury model (some parameters might vary)
- beta and social_norm_factor are almost same influential
- results of the sensitivity are almost the same for all goal-variables

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


## Belief-based / intention motivation
### Parameter
- kappa is least influential (that differs to the bury paper)
- temperature-factor dominates
- beta and N have almost the same values
- social_norm_factor is second last place
- results do not change qualitatively between the different goal-variables

### Classifications
- similar classifications to the no-norm reference
    - 30% of all runs are transitional/unresolved
    - 58.6% approaches to 1
    - 11.7% collapse to 0
- timing and slope are pretty even. Seems like they do change depending on N. Due to the fact that N is evenly distributed between -1 an 1, thats the  that i expected
- no damped/persistent oscilaations

## Observation-based___intention_motivation_(agents)
### Parameter
- temperature_factor and beta dominate mitigation
- climate is dominated by the temperature_factor
- dynamics are dominated by beta
- network_size has a value of 0 in mean x, end temperature and cumulative emissions. However, it has little influence on if x ever reaches >=95% (value = 0.1)
- MISSING: social_norm_factor

### Classifications
- TODO: ich mach hier erstmal nicht weiter, da ich vermute, dass die Sensi für diese Norm nochmal neu durchgeführt werden muss

## Observation_based___approval_(punish_only_one_behaviour)
### Parameter
- dominated by temperature_factor
- beta has second highest impact

### Classifications
- 86.5% of all runs end at x>=95%
- no damped/persistent oscillations
- 88% of those runs that end at x>=95% are faster (makes sense because only mitigators benefit from this norm)
- 70% of those runs that end at x<=5% are slower (makes sense because non-mitigators likely are punished by the norm and can never benefit from it)
- 63.6% of all runs have a higher max annual change: runs where x->1
- 31.1% are flatter: runs where x->0

## Static injunctive
### Parameter
- social_norm_factor has high impact on the dynamics (first x>=95% & oscillations), but low impact on the climate (cumulative emissions & finaltemperature)
- ...?

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
    - Why is that?


## Dynamic_social_norm
### Parameter
- ...

### Classifications
- no damped/persistent oscilations
- 71.7% approach to 1
- 78% of all runs reach x<=5% earlier compared to the no-norm reference (0% are later)
    - so if x<=5 is reached with this norm, then its always reached earlier>
- 59.4% of all runs reach x<=95% later compared to the no-norm reference (26.1% are earlier)
- obviously most runs are steeper than the no-norm-reference (94.8%)
- only 1.4% are flatter

## Dynamic_social_norm 2
### Parameter
- ...

### Classifications
- no damped/persistent oscilations
- 63.5% approach to 1
- 43.8% of all runs reach x<=5% equally(!) fast compared to the no-norm reference (34.2% are earlier) (0% are later)
    - so if x<=5 is reached with this norm, then its always reached earlier (similar to the other dynamic norm)
- 59.8% of all runs reach x<=95% earlier compared to the no-norm reference (28.1% are earlier) 
- In 67% of the runs the largest annual change is steeper than the no-norm reference (16.8% flatter)

## Descriptive,_injunctive,_dynamic
### Parameter
- ...

### Classifications


## Descriptive,_injunctive,_dynamic 2
### Parameter
- ...

### Classifications




## Comparing the norms
...


## Main results
- If a dynamic norm is used and x reaches <=5% then the norm implementation always reaches this point faster or equally fast compared to the no-norm reference. 
    - TODO: Das gilt erstmal nur für die einfachen dynamischen normen. Für Kombinationen muss das noch nachgeschaut werden




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
