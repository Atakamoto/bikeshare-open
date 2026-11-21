# Seeded faults

Exercise 2: three faults introduced one at a time, each caught by the test
suite and the PostToolUse hook (`.claude/hooks/check_leakage.sh`), then
repaired. Output below is copied from the real runs in the session.

## Exercise 1: test-first failure (commit `3837e4d`)

Commit `3837e4d` ("test: add failing test for 14-day rolling mean") added
`test_roll_14_hand_computed_on_known_date` to `tests/test_leakage.py` before
`cnt_roll_14` existed. The feature followed in `70124fd`.

**The failing output was not retained.** The Exercise 1 session's terminal
output isn't available in this session, and a re-run of that commit in a
scratch directory was declined, so it is not reproduced here. Nothing below
is reconstructed.

## Fault 1: a forbidden column admitted by `feature_columns()`

### Fault introduced

`src/features.py`, in `feature_columns()` (line 92):

```diff
-    return [c for c in numeric if c not in FORBIDDEN]
+    return [c for c in numeric if c not in FORBIDDEN - {"casual"}]
```

The change lets `casual` through the filter. `casual + registered == cnt`
exactly, so it is a leak of the target.

### Baseline (before the fault)

`make test`:

```
python -m pytest tests/ -q
.................                                                        [100%]
17 passed in 1.74s
```

### Failing pytest output (verbatim)

`python -m pytest tests/test_leakage.py -q`, run after the fault:

```
.F......                                                                 [100%]
=================================== FAILURES ===================================
__________________________ test_no_forbidden_features __________________________

feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7  cnt_roll_14
0   2011-01-17     17.0  WINTER  ...     132....142857  2814.714286
699 2012-12-31    731.0  WINTER  ...      920.0  1531.428571  2672.571429

[700 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_14', 'cnt_roll_7', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests/test_leakage.py:31: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 7 passed in 0.45s
```

`make test` with the fault: `1 failed, 16 passed in 1.81s`, then
`make: *** [test] Error 1`. The only failure was `test_no_forbidden_features`.
`test_beats_the_mean_baseline` still passed, so nothing else catches a leaked
`casual`.

### PostToolUse hook stderr (verbatim, exit 2)

```
Leakage tests failed after editing /Users/alex/Code/DSC180/bikeshare-open/src/features.py:
feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7  cnt_roll_14
0   2011-01-17     17.0  WINTER  ...     132....142857  2814.714286
699 2012-12-31    731.0  WINTER  ...      920.0  1531.428571  2672.571429

[700 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_14', 'cnt_roll_7', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests/test_leakage.py:31: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 7 passed in 0.47s
```

The hook shows only the last 20 lines of pytest output, so it omits the
progress line and the `FAILURES` header.

### Repair

Reverted the same line with the Edit tool:

```diff
-    return [c for c in numeric if c not in FORBIDDEN - {"casual"}]
+    return [c for c in numeric if c not in FORBIDDEN]
```

- **Hook after repair:** it exited 0 and printed no stderr, so there is
  nothing to quote.
- **`make test` after repair:**

```
python -m pytest tests/ -q
.................                                                        [100%]
17 passed in 1.81s
```

### Agent repair turns

1 (the repair was done in a single response).

## Fault 2: `.shift(1)` removed from `cnt_roll_7`

### Fault introduced

`src/features.py`, line 83:

```diff
-    out["cnt_roll_7"] = out[TARGET].shift(1).rolling(ROLL_SHORT).mean()
+    out["cnt_roll_7"] = out[TARGET].rolling(ROLL_SHORT).mean()
```

Without the shift, each row's 7-day window includes that day's own `cnt`,
so the feature contains the target. `cnt_roll_14` and the lags were left
unchanged.

### Baseline (before the fault)

`make test`:

```
python -m pytest tests/ -q
.................                                                        [100%]
17 passed in 1.74s
```

### PostToolUse hook stderr (verbatim, exit 2)

```
Leakage tests failed after editing /Users/alex/Code/DSC180/bikeshare-open/src/features.py:
[700 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4389.428571428572) == 4240.714285714285 ± 0.00424071
E             
E             comparison failed
E             Obtained: 4389.428571428572
E             Expected: 4240.714285714285 ± 0.00424071

tests/test_leakage.py:57: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 7 passed in 0.46s
```

As with Fault 1, the hook shows only the last 20 lines of pytest output.

### Failing pytest output (verbatim)

`python -m pytest tests/test_leakage.py -q`, run after the fault:

```
....F...                                                                 [100%]
=================================== FAILURES ===================================
_______________________ test_rolling_mean_excludes_today _______________________

feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7  cnt_roll_14
0   2011-01-17     17.0  WINTER  ...     132....428571  2814.714286
699 2012-12-31    731.0  WINTER  ...      920.0  1789.857143  2672.571429

[700 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4389.428571428572) == 4240.714285714285 ± 0.00424071
E             
E             comparison failed
E             Obtained: 4389.428571428572
E             Expected: 4240.714285714285 ± 0.00424071

tests/test_leakage.py:57: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 7 passed in 0.45s
```

`make test` with the fault: `1 failed, 16 passed in 1.81s`, then
`make: *** [test] Error 1`. The failure body was identical, and it was the
only failing test.

Notes:
- Only `test_rolling_mean_excludes_today` caught the fault. The 14-day test
  covers `cnt_roll_14`, which was untouched, and
  `test_beats_the_mean_baseline` still passed.
- That test only asserts when all 7 prior days exist in the data, so a gap
  near row 200 would silently skip the check. It ran here.

### Repair

Restored the shift with the Edit tool:

```diff
-    out["cnt_roll_7"] = out[TARGET].rolling(ROLL_SHORT).mean()
+    out["cnt_roll_7"] = out[TARGET].shift(1).rolling(ROLL_SHORT).mean()
```

- **Hook after repair:** it exited 0 and printed no stderr, so there is
  nothing to quote.
- **Diff check:** `git diff src/` was empty after the repair.
- **`make test` after repair:**

```
python -m pytest tests/ -q
.................                                                        [100%]
17 passed in 1.96s
```

### Agent repair turns

1 (the repair was done in a single response).

## Fault 3: the `raise` removed from `encode_weather()`

This fault was first missed, then caught after a test was added.

### Fault introduced

`src/features.py`, line 37, in `encode_weather()`:

```diff
     if unknown:
-        raise ValueError(f"unmapped weather labels: {sorted(unknown)}")
+        pass
```

The `raise` was replaced with `pass` because deleting the line outright
would leave `if unknown:` with no body, which is a syntax error. With the
`raise` gone, an unseen label such as `STORMY` maps to `NaN`, and a later
`dropna()` would delete that row without comment.

### Baseline (before the fault)

`make test`:

```
python -m pytest tests/ -q
.................                                                        [100%]
17 passed in 1.73s
```

### Initial result: the fault was missed

- **Hook:** after the Edit, it exited 0 and printed no stderr, so there is
  no hook output to quote.
- **`python -m pytest tests/test_leakage.py -q`** (what the hook runs):

```
........                                                                 [100%]
8 passed in 0.41s
```

- **`make test`:**

```
python -m pytest tests/ -q
.................                                                        [100%]
17 passed in 1.74s
```

No test called `encode_weather()` with an unknown label, so the suite had
nothing to fail on. The ingest contract tests check column names, not label
values.

### Test added (test-first)

Appended to `tests/test_leakage.py`, with the faulty `pass` still in place:

```python
def test_unknown_weather_label_is_rejected():
    """An unseen weather label must raise, not become a silent NaN that a
    later dropna() deletes without comment."""
    from src.features import encode_weather

    known = pd.Series(["GOOD", "MISTY", "BAD"])
    assert encode_weather(known).tolist() == [0.0, 1.0, 2.0]  # valid labels still encode

    with pytest.raises(ValueError, match="STORMY"):
        encode_weather(pd.Series(["GOOD", "STORMY"]))
```

### Failing pytest output with the new test (verbatim)

`python -m pytest tests/test_leakage.py::test_unknown_weather_label_is_rejected -q`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_unknown_weather_label_is_rejected ____________________

    def test_unknown_weather_label_is_rejected():
        """An unseen weather label must raise, not become a silent NaN that a
        later dropna() deletes without comment."""
        from src.features import encode_weather
    
        known = pd.Series(["GOOD", "MISTY", "BAD"])
        assert encode_weather(known).tolist() == [0.0, 1.0, 2.0]  # valid labels still encode
    
>       with pytest.raises(ValueError, match="STORMY"):
E       Failed: DID NOT RAISE ValueError

tests/test_leakage.py:97: Failed
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_unknown_weather_label_is_rejected - Failed...
1 failed in 0.44s
```

The failure is `DID NOT RAISE ValueError`, so the cause is the missing
`raise`, not a syntax or import error. The valid-label assertion on the
line before it passed.

`make test` with the fault and the new test:
`1 failed, 17 passed in 1.85s`, then `make: *** [test] Error 1`. The failure
body was identical.

### PostToolUse hook stderr

**Not captured for this detection.** The hook only fires on edits to
`src/*.py`, and the test was added by editing `tests/test_leakage.py`, so the
hook did not run when the failing test was introduced. The failing output
above comes from my manual pytest runs, not from the hook. The hook has no
stderr for Fault 3 at any point: it was silent after the fault, and silent
after the repair.

### Repair

Restored the `raise` with the Edit tool:

```diff
     if unknown:
-        pass
+        raise ValueError(f"unmapped weather labels: {sorted(unknown)}")
```

- **Hook after repair:** it exited 0 and printed no stderr, so there is
  nothing to quote.
- **`make test` after repair:**

```
python -m pytest tests/ -q
..................                                                       [100%]
18 passed in 1.77s
```

The count is 18 because of the added test. The test stays in
`tests/test_leakage.py` as a permanent guard.

### Agent repair turns

1 for the repair (the `raise` was restored in a single response). The
test-first step took a separate response before it.

## Fault 4: a harmless file copy denied in Claude Code, allowed outside it

This probe tested the permission layer, not the leakage tests. It did not
change `src/` or the pipeline, so no pytest failure or leakage-hook output is
expected. The file it creates is a harmless probe, `data/raw/fault4_probe.txt`.

### Command

```
cp -n /tmp/fault4_probe_src.txt data/raw/fault4_probe.txt
```

### Observations

- **In Claude Code:** the Bash tool repeatedly denied the `cp` command, even
  after an exact Allow rule for it was added.
- **In the user's external terminal:** the same command succeeded. Running
  `cat data/raw/fault4_probe.txt` there printed:

```
fault4 harmless probe
```

- **PostToolUse hook:** no Claude Code PostToolUse hook was invoked for the
  external-terminal command. That is expected, because Claude Code never saw
  the command.

### Interpretation

- This does **not** show that Claude Code's Bash tool can bypass its
  permission system. The Bash tool was denied. The successful `cp` ran in a
  separate terminal that Claude Code does not control.
- The hook is scoped to `"matcher": "Edit|Write"` in `.claude/settings.json`,
  so Bash file operations are outside its matcher. Even a `cp` that Claude
  Code did run would not have triggered the leakage hook. The hook is not a
  guard against file changes made through Bash.
- The probe wrote to `data/raw/`, so the raw CSV's integrity is checked below.

### Verification (run after the probe)

- **Probe files:** cleanup succeeded. Immediately after the probe both files
  existed (22 bytes each, containing `fault4 harmless probe`). In the final
  check, `ls` reported "No such file or directory" for both, and neither
  appears in `git status`:
  - `/tmp/fault4_probe_src.txt`
  - `data/raw/fault4_probe.txt`

  The removal itself was not done in this session's final step, so this
  section does not record how it was done.
- **Raw CSV SHA256** (`data/raw/bike_daily.csv`):
  `a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc`.
  The file is tracked, and the SHA256 of the `HEAD` version is identical, so
  it is unchanged from the last commit. No hash was recorded before the probe,
  so this is a comparison with `HEAD`, not with a pre-probe snapshot.
- **`make test`:**

```
python -m pytest tests/ -q
..................                                                       [100%]
18 passed in 1.76s
```
