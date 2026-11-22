# Bikeshare Demand Forecasting: Final Report

We forecast daily Capital Bikeshare ride counts (`cnt`, 2011–2012) from calendar, weather and lagged-demand features. The split is by date: train on 2011 (334 rows), validate on H1 2012 (182 rows), test on H2 2012 (184 rows). Models are selected on validation only. Test scores are a final descriptive check.

## 1. Results

Regenerated with `make all` in the project virtual environment (`make test`: 18 passed). All four models use the same 15 features from `feature_columns()` and the original, untransformed `cnt` target.

| Model | Valid R² | Valid MAE | Test R² | Test MAE |
|---|---|---|---|---|
| Mean baseline (2011 average) | -0.8583 | 1965.6 | -2.0333 | 2793.1 |
| Persistence (yesterday's `cnt`) | 0.4507 | 900.6 | 0.5099 | 840.1 |
| Ridge (standardised, alpha 1.0) | **0.6919** | **763.2** | **0.6268** | 870.9 |
| HGB (`max_iter=300`, `random_state=0`) | 0.1643 | 1341.2 | -0.6534 | 2087.9 |

On validation, Ridge is best on both metrics. On test, Ridge has the best R² but persistence has the lower MAE. HGB scores below persistence everywhere and below zero R² on test. A negative R² is a finding, not an error: it means HGB is worse than predicting the test-period mean.

**Limitations of this table.**
- The reported weather columns are the day's *observed* weather (see section 4).
- Test includes 2012-10-29 (Hurricane Sandy, 22 rides), an extreme day that affects every model.
- An earlier version of the smoke test `test_beats_the_mean_baseline` scored Ridge on the test split on every `make test`, the pattern the peer audit flagged in Alan's repository (finding F2). It was never used to change features or hyperparameters, and it has been corrected to use the validation split, so the test suite no longer evaluates held-out test data.

## 2. Headline finding

**Ridge beats HGB because trees trained on 2011 cannot extrapolate to 2012 demand.** Ridership grew roughly 65% from 2011 to 2012. A tree can only predict values built from its training targets: the 2011 maximum is 6,043 rides, while validation days reach 8,362. In an in-memory check on validation, the original HGB never predicted above 5,512 and under-predicted by about 1,235 rides per day on average. Ridge, a linear model on the lagged-demand features, scales with them: its validation predictions reach about 7,084 and its average error is about -378. On test, the gap becomes large: HGB R² is -0.65 against Ridge's 0.63.

**The 14-day rolling feature widens the gap.** `cnt_roll_14` is the mean of the previous 14 calendar days (shifted by one day before rolling, so today is excluded). It was added on the basis of validation R²: Ridge improved from 0.6475 to 0.6919 (+0.044) and HGB fell from 0.2185 to 0.1643 (-0.054). It is a smooth, near-linear summary of the current demand level, which Ridge can use directly. The tree can only use it up to the range it saw in 2011, so extra level information adds little. The larger warmup also cut the training sample from 348 to 334 rows. This is a single ablation on one split, so the mechanism is consistent with the evidence, not proven by it.

## 3. Exercise 4: target transformation

**Question.** Can a transformed target let HGB compete with Ridge? Each variant was fitted on training rows only and scored on validation only, on the original ride-count scale. No test score was inspected. The features, split and HGB hyperparameters were unchanged, with 334 training rows, 182 validation rows and 15 features.

| HGB target | Inverse transform | Valid R² | Valid MAE |
|---|---|---|---|
| `cnt` (original) | none | 0.164 | 1341.2 |
| `log1p(cnt)` | `expm1` | 0.079 | 1423.1 |
| `cnt / cnt_lag_1` (ratio) | multiply by `cnt_lag_1` | 0.544 | 912.1 |
| **`cnt - cnt_lag_1` (residual)** | **add `cnt_lag_1`** | **0.616** | **823.5** |
| Ridge (benchmark) | none | 0.692 | 763.2 |
| Persistence (benchmark) | none | 0.451 | 900.6 |

**Selection, on validation only.** The residual target is the best HGB variant. Against original HGB it improves R² by 0.452 and MAE by 517.7 (38.6%). It is the only variant that beats persistence on both R² and MAE.
- **Why residual works.** Predicting the change from yesterday anchors every prediction to the known current level, so the tree no longer has to produce counts above its training range. Its predictions reach about 8,331 on validation.
- **Why not `log1p`.** It made HGB worse (R² 0.164 to 0.079). A monotone transform changes how errors are weighted but does not let a tree predict outside its training range.
- **Why not ratio.** It improved on original HGB but loses to persistence on MAE (912.1 vs 900.6). Its target is heavy-tailed (0.167 to 5.313 in training) and undefined if `cnt_lag_1` is ever zero. The check that `cnt_lag_1` is strictly positive passed in train and validation.

**Still behind Ridge.** Residual HGB trails Ridge by 0.076 R² and 60.3 MAE. It still under-predicts on average (about -407 rides per day), and it approximates the residual with piecewise-constant leaves.

**Causal availability.** `cnt_lag_1` is yesterday's count, built from `cnt.shift(1)` on a gap-free calendar index. It is known at the end of day d-1, so the transformed target and its inverse use no day-d information.

**Status.** The residual model is a documented experiment, not a pipeline change. `src/train.py` and `reports/metrics.json` remain on the original, untransformed models. The decision is recorded in `docs/DECISIONS.md`. This is one deterministic run on one validation split.

## 4. Exercise 5: ridge vs persistence

| Model | Valid R² | Valid MAE | Test R² | Test MAE |
|---|---|---|---|---|
| Persistence | 0.4507 | 900.6 | 0.5099 | 840.1 |
| Ridge | 0.6919 | 763.2 | 0.6268 | 870.9 |

**Why Ridge looks better on validation.** Ridge uses weekday, holiday and seasonal effects, a smoothed demand level and the day's weather. Persistence ignores everything but yesterday. On validation, Ridge cuts MAE by 137 rides (15%) and raises R² by 0.24. Demand was rising through spring 2012, so yesterday's count also lags the trend, which plausibly hurts persistence further.

**Why persistence is competitive on test MAE.** Persistence has the lower test MAE (840.1 vs 870.9, a 30-ride or 3.7% difference), while Ridge has the higher R². Both can hold if persistence makes many small errors and a few very large ones: squared-error R² is dominated by the large ones, absolute error is not. We did not analyse test residuals, so this is the pattern the metrics imply, not a verified cause. Test results are a descriptive check here, not a selection criterion, and a 30-ride gap on one half-year is small.

**Operations and explainability.** Persistence needs one input, has no maintenance and is explained as "same as yesterday". Ridge needs 15 inputs, including weather. It has more failure modes (late or missing inputs, feature bugs), needs retraining as ridership grows and requires monitoring. Its linear coefficients are still easy to inspect.

**Weather is the key dependency.** Ridge uses same-day weather columns (`temp`, `atemp`, `hum`, `windspeed`, `weather_severity`). These hold *observed* weather for the day being predicted. A next-day forecast is made the evening before, when that weather has not occurred, so production would have to use weather *forecasts*, which contain errors. Every Ridge score in this report is therefore an optimistic estimate for next-day forecasting, because actual forecast errors were not modeled. Persistence has no weather dependency. We did not run a lagged-weather ablation on this pipeline. The peer audit of Alan's repository (section 5) found a large drop for his Ridge when weather was lagged by a day; that is his repository's result, not ours.

**Recommendation: a staged rollout.**
1. **Deploy persistence first.** It matches Ridge on test MAE, needs no external data and cannot fail on missing weather.
2. **Run Ridge in shadow mode**, fed with the weather forecast actually available the evening before, logging both predictions against actual counts without acting on Ridge's output.
3. **Promote Ridge only if** the evidence below supports it.

**Evidence required before deploying Ridge.**
- Validation scores using archived weather forecasts, or a Ridge retrained with lagged or no weather, still beating persistence.
- A shadow period (weeks to months) in which Ridge at least matches persistence on MAE and wins on the operational cost that matters.
- A confidence interval or paired comparison for the MAE difference.
- Error analysis by day type (holidays, extreme weather, storms).
- A retraining and drift-monitoring plan, given the 65% growth.
- Confirmation that weather and lag inputs arrive on time, with a fallback to persistence.

## 5. Attribution

**My direction and review.** I set the exercise goals and constraints, issued each instruction, and reviewed the outputs. I chose Alan's repository as the audit target and the positions taken on the four audit findings (agree or agree with conditions, and the ranking of F1–F4). I directed the use of Sonnet for the automated audit, the restoration of the `Write(./data/raw/**)` deny rule and the `.gitignore` change, the validation-only target-transformation experiments, the staged deployment recommendation, and this test correction. I reviewed the results, but I did not write the code, documentation or report text described below.

**Claude Code's implementation and drafting.** Claude Code implemented and wrote the work I directed: the `cnt_roll_14` feature and its tests, the raw-data contract, the weather-label regression test, and the seeded-fault introductions and repairs (documented in `docs/SEEDED_FAULTS.md`). It ran the peer audit and automated audit, extracted the verbatim subagent report into `docs/AUDIT.md`, and drafted the verdict text there from the positions I gave. It also ran the target-transformation experiments in memory, drafted the `docs/DECISIONS.md` entry and the Exercise 5 text, corrected the smoke test, regenerated `reports/metrics.json`, and drafted this report.

**Custom skill.** `.claude/skills/model-summary/SKILL.md` is a new, read-only skill that I directed and Claude Code wrote. It takes a focus through `$ARGUMENTS` (for example `/model-summary leakage`), summarizes validation results and leakage safeguards for that focus, and is instructed never to read or report test-set scores.

**Peer audit.** The `leakage-auditor` subagent, run in a fresh context, audited Alan's repository (`https://github.com/alanx1234/bikeshare-open`, commit `d885671`). The verbatim report is in `docs/AUDIT.md`. All experiments and numbers in it were produced by the subagent, and I did not independently reproduce them. My verdict separates findings that change results (F1, F2, F3) from a test-coverage gap that is not an existing numerical error (F4).

**Automated audit of this repository.** `agent/audit.py` run with Sonnet returned `leakage: none` with `temporal_ok`, `baseline_reported` and `reproducible` all true, plus two minor findings (the Makefile calls bare `python`; no train-set scores are reported). **This is not proof that leakage is absent.** It is a language-model review with no guarantee of coverage, and it did not flag the same-day-weather availability issue or the test-set smoke test that the peer audit pattern identified and that we later corrected (section 1). The leakage defences that carry weight are the deterministic ones: the `FORBIDDEN` exclusion list, the identity check that `casual + registered == cnt`, the hand-computed lag and rolling tests, and the temporal split.

**Models used.** The starter configuration pointed Claude Code at a local Ollama model (`bikeshare-coder`). The current configuration uses Sonnet. The automated audit was run with `AUDIT_MODEL=sonnet`, and the target-transformation experiments, the Exercise 5 draft and this report were produced with Claude Sonnet 5.5. The repository does not record which model ran the earlier sessions.
