---
name: model-summary
description: Summarize the current validation results and leakage safeguards for a focus the user names (e.g. baselines, extrapolation, leakage, weather). Read-only; never evaluates or reports the held-out test set. Use when someone asks where the models stand or what protects the pipeline.
allowed-tools: Read, Grep
---

# Current state (validation only, read from disk)

!`python -c "import json; from src.config import FORBIDDEN, METRICS, TRAIN_END, VALID_END; m=json.loads(METRICS.read_text()); print('split: train <=', TRAIN_END, '| valid <=', VALID_END, '| n_train', m['n_train'], 'n_valid', m['n_valid'], 'n_features', m['n_features']); print('features:', ', '.join(m['features'])); print('forbidden:', ', '.join(sorted(FORBIDDEN))); [print(k, m[k]['valid']) for k in ('baseline_mean','baseline_persistence','ridge','hgb')]"`

# Summarizing the pipeline, focus: $ARGUMENTS

If `$ARGUMENTS` is empty, ask the user for a focus (for example `baselines`,
`extrapolation`, `leakage`, `weather`, or `all`) and stop.

Rules for this skill. They are not optional:

- **Read-only.** Do not edit any file and do not run training, tests or
  any model fit. Use only the state printed above and the files you read.
- **Validation only.** Do not read the `test` entries of
  `reports/metrics.json`, do not call `src.train.temporal_split` to score
  test rows, and do not quote test-set numbers, even if the user asks for
  them. Say that test results are reported separately, as a final
  descriptive check, and are not used for model decisions.
- **If the state block above is an error or empty,** `reports/metrics.json`
  is missing. Say so and tell the user to run `make all`. Do not guess
  numbers.

Then answer for the requested focus, in at most 12 lines:

1. **Results.** A small table of validation R^2 and MAE for the mean
   baseline, the persistence baseline, ridge and hgb, taken from the block
   above. Always show both baselines next to the models.
2. **Focus.** Address `$ARGUMENTS` using evidence you can point to:
   - `leakage`: name the columns in `FORBIDDEN` and why each is excluded
     (read `src/config.py`), and name the tests that guard them in
     `tests/test_leakage.py`.
   - `baselines`: compare each model with persistence, not only the mean.
   - `extrapolation`: relate hgb's gap to ridge to the 2011-to-2012 growth
     noted in `CLAUDE.md` and `docs/DECISIONS.md`.
   - `weather`: state that the weather columns are same-day observed
     values, so next-day scores are optimistic estimates because forecast
     errors are not modeled.
   - anything else: say what the repository can and cannot show about it.
3. **Caveat.** One sentence on what these validation numbers cannot show
   (one split, 182 days, no significance test).

Cite file paths for every claim about the code. If you cannot find the
evidence, say so instead of inferring it.

## Invoke

    /model-summary leakage
    /model-summary baselines
    /model-summary extrapolation
    /model-summary weather
