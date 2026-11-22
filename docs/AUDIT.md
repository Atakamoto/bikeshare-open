# Peer Audit (Exercise 3)

- **Peer repository:** https://github.com/alanx1234/bikeshare-open
- **Commit audited:** `d885671`
- **Auditor:** `leakage-auditor` subagent, run in a fresh context from a separate Claude Code session (`~/Code/DSC180/alan-peer-audit`).

## Leakage-auditor report (verbatim)

The report below is the complete, unedited final report of the `leakage-auditor` subagent, copied from that session's transcript. All experiments and numerical findings in it (ablations, mutation test, pipeline runs) were produced by the subagent, not independently reproduced by me.

---

# Methodology Audit: bikeshare-open

- **Repository:** https://github.com/alanx1234/bikeshare-open (local clone `/Users/alex/Code/DSC180/alan-peer-audit`)
- **Commit audited:** `d885671` (branch `main`, clean working tree)
- **Date:** 2026-11-21
- **Scope:** the whole pipeline (`src/`, `tests/`, `Makefile`, `README.md`, `docs/DECISIONS.md`), checked against five things: target leakage, temporal ordering, calendar gaps, silent row loss and baseline reporting.

## Summary

| ID | Severity | Check | File:line | Description |
|---|---|---|---|---|
| F1 | High | 2 (feature availability) | `src/features.py:68-69`, `src/config.py:51-54` | Weather is the day's actual recorded weather, which nobody knows when the forecast is made. Ridge's test R^2 falls from 0.636 to 0.521 when weather is lagged one day, and its MAE becomes worse than persistence. |
| F2 | Medium | 2 (tuning on test) / 5 | `tests/test_contract.py:71-77`, `docs/DECISIONS.md:9` | `make test` checks test-set R^2 on every run. The test does not compare against either baseline, and DECISIONS' claim that the test set was "touched once" is false by its own record. |
| F3 | Medium | 5 (misleading baseline claims) | `docs/DECISIONS.md:6, 10, 11` | The ridge and persistence numbers were not updated after `cnt_std_7` was added. The HGB numbers cannot be reproduced with the pinned versions. |
| F4 | Low | 3 / 4 (test gap) | `tests/test_contract.py:53-68`, `tests/test_leakage.py:37-46, 62-69`, `src/features.py:80` | All 23 tests still pass when the calendar reindex is removed, so the gap fix is not protected. The row-loss bound only checks one direction, and the pipeline itself has no check on how many rows it drops. |

Pipeline output as it stands (pinned versions, run in memory on a copy):

| model | valid R^2 / MAE | test R^2 / MAE |
|---|---|---|
| baseline_mean | -0.9318 / 2002.2 | -2.1441 / 2847.7 |
| baseline_persistence | 0.4507 / 900.6 | 0.5099 / 840.1 |
| ridge | 0.7224 / 700.4 | 0.6356 / 840.3 |
| hgb | 0.0977 / 1381.6 | -0.6959 / 2108.4 |

n_train=348, n_valid=182, n_test=184; 15 features.

---

## F1 (High): Features use the day's actual weather, which is not known when the forecast is made

**Location:** `src/features.py:68-69` (`out["weather_severity"] = encode_weather(out.weather)` under the comment "Weather: measured same-day, available to a forecaster"). `src/config.py:51-54` puts `temp`, `atemp`, `hum`, `windspeed` and `weather` in `RAW_FEATURE_COLS`, so `feature_columns()` passes them through unchanged.

**Evidence.** Each row's weather values are the observed daily summaries for day *d*: mean temperature, humidity, wind speed and the day's weather category. The demand features (`cnt_lag_1`, `cnt_roll_7`, `cnt_std_7`) use counts up to *d-1*. That implies the forecast is made at the end of *d-1*, and at that point day *d*'s actual weather has not happened. The comment says this data is "available to a forecaster", but nothing in the code checks that.

Ablation with the same models, split and pinned versions:

| ridge feature set | valid R^2 / MAE | test R^2 / MAE |
|---|---|---|
| as shipped (day-*d* actual weather) | 0.7224 / 700.4 | 0.6356 / 840.3 |
| weather shifted by 1 day (`shift(1)` on calendar index) | 0.5793 / 884.2 | 0.5210 / 987.5 |
| no weather columns | 0.5723 / 894.6 | 0.5123 / 1005.6 |
| persistence baseline | 0.4507 / 900.6 | 0.5099 / 840.1 |

HGB with weather lagged one day: valid -0.0464, test -1.1833.

**Why the result is wrong.** For a next-day forecast, which is what the lag features imply, the reported ridge score depends on perfect knowledge of tomorrow's weather. With weather that would actually be known, ridge beats persistence on test R^2 by only 0.011 and loses to it on MAE by 147 rides per day (987.5 vs 840.1). That reverses the conclusion "ridge beats persistence".

**Minimal fix.** Pick one:
- (a) Build the weather features from `shift(1)` on the calendar-reindexed frame, the same way as the demand lags.
- (b) Keep same-day weather, but state in the README and DECISIONS that this is a perfect-weather-forecast upper bound, and report the lagged-weather row next to it.

---

## F2 (Medium): The test set is checked on every `make test`, and the test compares against no baseline

**Location:** `tests/test_contract.py:71-77`

```python
def test_beats_the_mean_baseline(feats):
    ...
    train, _, test = temporal_split(feats)
    ...
    assert r2_score(test[TARGET], ridge.predict(test[cols])) > 0.4
```

**Evidence.**
- **The test set gates every change.** Every `make test` (which CLAUDE.md says to run "before claiming anything works") scores ridge on the H2 2012 test set and fails if R^2 is 0.4 or below. Any feature change is therefore accepted or rejected partly on test performance. That breaks the rule "Never tune on test" and the claim in `docs/DECISIONS.md:9`: "Test set touched once, after all feature work."
- **DECISIONS contradicts itself.** Lines 6 and 10 record test scores (ridge 0.583, persistence 0.510) from before the `cnt_std_7` feature work on line 11. I reproduced ridge test 0.5833 with `cnt_std_7` removed, which confirms those numbers predate it.
- **The test name does not match what it checks.** It never computes the mean baseline (test R^2 -2.14) or persistence (0.51). A ridge with test R^2 0.45 would pass while losing to "yesterday again".
- **The persistence test is weak too.** `test_persistence_baseline_is_reported` (lines 80-83) only checks that `"baseline_persistence" in MODELS`, not that the score is computed or written anywhere.

**Why the result is wrong.** The reported test score is not a clean held-out estimate. A feature that hurts validation but keeps test above 0.4 passes. A feature that fails on test gets reworked until it passes, which is selection on the test set.

**Minimal fix.** Run the check on the validation split, and compare ridge against persistence on that split:

```python
_, valid, _ = temporal_split(feats)
assert r2_score(valid.cnt, ridge.predict(valid[cols])) > r2_score(valid.cnt, valid.cnt_lag_1)
```

Also correct `docs/DECISIONS.md:9` to describe how the test set has actually been used.

---

## F3 (Medium): DECISIONS.md numbers do not match what the code computes

**Location:** `docs/DECISIONS.md` lines 6, 10 and 11.

**Evidence** (pinned numpy 2.5.3, pandas 3.0.5, scikit-learn 1.9.1):

| Line | Claim | What the current code produces |
|---|---|---|
| 6 | "honest ridge 0.583" | Test R^2 is 0.6356 (valid 0.7224). 0.583 is the score from before `cnt_std_7` (reproduced: 0.5833). |
| 10 | "Persistence (test R^2 0.510, MAE 840) is within 0.07 R^2 of ridge and beats it on MAE" | Gap is 0.6356 - 0.5099 = 0.126, not under 0.07. The MAE part still holds, but only just: persistence 840.1 vs ridge 840.3. |
| 11 | "hgb 0.2368 -> 0.0964 (-0.140)" | Reproduced: 0.2185 -> 0.0977 (-0.121). The ridge, persistence and mean numbers on this line reproduce exactly. |

`requirements.txt` claims the pins reproduce `reports/metrics.json` "to the printed digit". No `reports/` directory is committed, so that cannot be checked.

**Why the result is wrong.** A reader of DECISIONS would quote a ridge score that is out of date, and an R^2 gap over persistence that is half the true one. The HGB numbers on line 11 cannot be reproduced from this commit with the pinned environment.

**Minimal fix.**
- Regenerate the numbers on lines 6 and 10 from `reports/metrics.json` at this commit, and state test MAE as a tie (840.1 vs 840.3).
- Re-run the line 11 ablation and correct the HGB numbers, or note which environment produced 0.2368.
- After F1 these all change again. Report the lagged-weather numbers.

---

## F4 (Low): Tests do not protect the calendar-gap fix, and the pipeline has no check on dropped rows

**Location:** `tests/test_contract.py:53-68`, `tests/test_leakage.py:37-46` and `:62-69`, `src/features.py:80`.

**Evidence (mutation test).** In a scratch copy I replaced line 54 of `src/features.py` with a version that skips the reindex:

```python
out = df.sort_values("dteday").reset_index(drop=True).copy()
```

Result: **23 passed**. With this bug, the features are wrong for 2011-03-11 to 2011-03-17. For example:
- 2011-03-14 gets `cnt_lag_7 = 605`, which is the count for 2011-03-06 (8 days earlier).
- 2011-03-11 gets `cnt_lag_1 = 1891`, which is the count for 2011-03-09.

Each test misses it for a different reason:
- **`test_lags_are_true_calendar_lags`** skips any date whose previous calendar day is missing (`if prev in by_date.index`). 2011-03-11 is exactly that case, so it is never checked. Nothing tests `cnt_lag_7` at all.
- **The 2011-03-18 rolling-mean and rolling-std cases** cannot catch it either. On 2011-03-18 the window by rows and the window by calendar days are the same seven dates. The days the bug breaks are 2011-03-11 to 2011-03-17, and none of them is tested.
- **`test_only_expected_rows_are_dropped`** only checks for too many lost rows (`lost <= allowed_loss`). The bug loses fewer rows (7 instead of 14), so it passes.

On top of that, `build_features` calls `dropna()` with no assertion of its own. The bound exists only in the test suite, so a re-downloaded file (`python -m src.ingest --force`) could lose rows without any error.

**Effect on the numbers.** None at this commit: the code does reindex, and I confirmed that exactly 14 rows are dropped (2011-01-03 to 01-09 and 2011-03-11 to 03-17). But nothing stops a regression on check 3.

**Minimal fix.**
- In `test_only_expected_rows_are_dropped`, change the assertion to `lost == allowed_loss`.
- Add a lag test against the raw CSV for every row and every lag (1 and 7). It should fail when the *d-k* date is missing from the raw file, instead of skipping that row.
- Add an `assert` on the drop count inside `build_features`, using `LAG_WARMUP` and the number of missing calendar days.

---

## Checks that passed

- **Check 1: target leakage.** Passed.
  - The feature set is `temp, atemp, hum, windspeed, dayofweek, is_weekend, is_holiday, is_workday, month_sin, month_cos, weather_severity, cnt_lag_1, cnt_lag_7, cnt_roll_7, cnt_std_7`.
  - `casual`, `registered`, `cnt`, `cnt_2d_bfr`, `instant`, `yr` and `days_since_2011` are excluded through `FORBIDDEN`. No feature is an arithmetic combination of `casual`, `registered` or same-day `cnt`.
  - The highest absolute correlation of any feature with `cnt` is 0.849 (`cnt_roll_7`).
  - All four demand features are built from `cnt.shift(...)` (`src/features.py:74-78`).
  - `src/leakage_demo.py` is a deliberate demonstration of leakage and is not part of the pipeline.
- **Check 2: split and fitted transformers.** Passed, apart from F1 and F2.
  - `temporal_split` splits by date: 348 train / 182 valid / 184 test, with no overlap.
  - `StandardScaler` sits inside the ridge pipeline and is fitted on train only. `DummyRegressor` uses the 2011 mean.
  - No imputer, encoder or hyperparameter search is fitted on valid or test. Ridge `alpha=1.0` and the HGB parameters are fixed.
  - Every rolling feature applies `.shift(1)` before `.rolling(7)`.
- **Check 3: calendar gaps (current code).** Passed.
  - `reindex_to_calendar` inserts 2011-03-10. Every row whose lag window touches that date is dropped.
  - The dropped dates match exactly what the gap implies.
- **Check 4: silent row loss (current data).** Passed.
  - The raw CSV has no NaN values.
  - The weather labels are exactly GOOD/MISTY/BAD (463/245/20), and `encode_weather` raises on unknown labels.
  - The holiday and workday columns use only `Y`/`N`.
  - 728 -> 714 rows, which is the expected loss of 14.
- **Check 5: baselines in `metrics.json`.** Passed. `fit_and_score` reports the mean and persistence baselines next to ridge and HGB, on both valid and test. The problems are in the docs and tests (F2, F3), not in the metrics output.

## What I ran and limitations

- **Environment.** The system Python's scikit-learn would not load (x86_64 build on an arm64 Mac). I made a scratch venv with the pinned versions (numpy 2.5.3, pandas 3.0.5, pyarrow 26.0.1, scikit-learn 1.9.1, pytest 9.1.1) at `/private/tmp/claude-501/-Users-alex-Code-DSC180-alan-peer-audit/8322c347-f210-4459-b6e4-b0ed534f123e/scratchpad/venv`.
- **What I ran.**
  - The 23 tests, on a copy of `src/`, `tests/` and `data/` at `/private/tmp/claude-501/-Users-alex-Code-DSC180-alan-peer-audit/8322c347-f210-4459-b6e4-b0ed534f123e/scratchpad/audit-copy`: all pass.
  - `fit_and_score()` on that copy, writing features to the scratchpad instead of `data/processed/`.
  - The ablations in F1 and F3, in memory.
  - The mutation test in F4, on a second copy at `/private/tmp/claude-501/-Users-alex-Code-DSC180-alan-peer-audit/8322c347-f210-4459-b6e4-b0ed534f123e/scratchpad/mut`.
- **Nothing in the repo was changed.** No `make` targets were run there and no git commands that change state.
- **Data.** I used the committed `data/raw/bike_daily.csv`. I did not re-download from `DATA_URL`.
- **No committed metrics.** There is no `reports/metrics.json` at this commit, so the documented numbers could only be checked against my own runs.
- **Not reviewed.** `.claude/` hooks and skills, `agent/audit.py` and `model/` do not produce any reported numbers. `docs/SEEDED_FAULTS.md` was not used as evidence.


---

## My independent verdict

This section is my own assessment of the subagent's findings. I did not independently reproduce the experiments or numbers cited here. They are attributed to the peer-audit subagent's report above.

**F1 — Agree, conditional on next-day forecasting.** Actual same-day observed weather is unavailable at the previous day's prediction time. The subagent's reported ablation changes ridge validation R² from 0.7224 to 0.5793 and MAE from 700.4 to 884.2. If the task instead assumes accurate same-day weather forecasts, that assumption must be documented.

**F2 — Agree.** Running a test-set R² threshold on every `make test` risks using held-out performance during development. The check should use validation data.

**F3 — Agree.** Outdated or unreproducible metrics in `DECISIONS.md` misrepresent the current pipeline's performance and should be corrected.

**F4 — Agree that there is a test-coverage gap, but it is not an existing numerical error.** The subagent reports that the current pipeline reindexes correctly; its mutation experiment shows the tests fail to protect that behavior.

**Overall ranking.** F1 has the strongest direct numerical impact, F2 threatens evaluation validity, F3 affects reported conclusions, and F4 exposes a future regression risk.
