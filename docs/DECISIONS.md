# Decisions

One line per methodological decision: what you chose, why, and what it changed.
Agents append here via the `/new-feature` skill; you append here by hand.

- Exclude `casual`, `registered`: they sum to `cnt` exactly. Leaky model R^2 1.000 -> honest ridge 0.583.
- Exclude `cnt_2d_bfr`: a shipped 2-day lag we cannot test the alignment of. Build our own lags instead.
- Exclude `instant`, `yr`, `days_since_2011`: time indexes let a tree predict a flat constant past 2011 and a linear model extrapolate a trend we have no grounds for.
- Split 2011 / H1 2012 / H2 2012 by date. Test set touched once, after all feature work.
- Report mean and persistence baselines with every score. Persistence (test R^2 0.510, MAE 840) is within 0.07 R^2 of ridge and beats it on MAE; that caveat goes in the report.
- Add `cnt_roll_14` (mean of the previous 14 calendar days of `cnt`, `.shift(1)` before `.rolling(14)`, so today's count is excluded and every input is known at prediction time). Validation R^2: ridge 0.6475 -> 0.6919 (+0.044), hgb 0.2185 -> 0.1643 (-0.054). Kept because ridge improved by more than 0.01; hgb's drop is consistent with trees failing to extrapolate 2011 levels to 2012. `LAG_WARMUP` raised 7 -> 14, so the training sample fell from 348 to 334 rows; window lengths now live in `LAG_WEEK`/`ROLL_SHORT`/`ROLL_LONG` so the warmup change does not alter `cnt_lag_7` or `cnt_roll_7`.
