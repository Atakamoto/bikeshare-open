"""The tests that make the agent honest.

test_no_forbidden_features is the single most valuable test in this repo:
casual + registered == cnt exactly, so any model handed those columns
scores R^2 = 1.0 and looks brilliant while having learned nothing.
"""
import pandas as pd
import pytest

from src.config import FORBIDDEN, TARGET
from src.features import build_features, feature_columns
from src.ingest import load_raw


@pytest.fixture(scope="module")
def feats():
    return build_features(load_raw())


def test_leakage_identity_holds(feats):
    """Documents *why* casual and registered are forbidden."""
    assert (feats.casual + feats.registered == feats[TARGET]).all()


def test_no_forbidden_features(feats):
    """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
    construction, so this cannot discover a *new* leaky column. What it
    catches is someone editing feature_columns() or FORBIDDEN -- which is
    exactly the fault the Step 7 hook demonstrates."""
    cols = set(feature_columns(feats))
    assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"


def test_lags_are_true_calendar_lags(feats):
    """cnt_lag_1 for date d must equal cnt on d-1, in calendar days."""
    by_date = feats.set_index("dteday")[TARGET]
    checked = 0
    for date, lag in feats.set_index("dteday").cnt_lag_1.items():
        prev = date - pd.Timedelta(days=1)
        if prev in by_date.index:
            assert lag == pytest.approx(by_date[prev]), f"bad lag at {date.date()}"
            checked += 1
    assert checked > 600, "too few rows actually verified"


def test_lag_is_not_the_target(feats):
    assert not (feats.cnt_lag_1 == feats[TARGET]).all()


def test_rolling_mean_excludes_today(feats):
    """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
    by_date = feats.set_index("dteday")[TARGET]
    date = feats.dteday.iloc[200]
    window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
    if all(d in by_date.index for d in window):
        expected = sum(by_date[d] for d in window) / 7
        assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)


def test_roll_14_hand_computed_on_known_date(feats):
    """cnt_roll_14 on 2012-06-15 is the mean of 2012-06-01..2012-06-14.

    Counts below are copied from the raw CSV, not read from `feats`, so the
    expectation is independent of the code under test. 2012-06-15's own
    count (7665) must NOT be in the window.
    """
    prior_14 = [
        4127, 8120, 7641, 6998, 7001, 7055, 7494,  # Jun 1-7
        7736, 7498, 6598, 6664, 4972, 7421, 7363,  # Jun 8-14
    ]
    assert len(prior_14) == 14
    expected = sum(prior_14) / 14  # 96688 / 14 = 6906.2857...
    row = feats.set_index("dteday").loc[pd.Timestamp("2012-06-15")]
    assert row[TARGET] == 7665, "fixture date changed; recompute the window"
    assert row.cnt_roll_14 == pytest.approx(expected)
    # Including today would give a different answer, so this also pins shift(1).
    assert row.cnt_roll_14 != pytest.approx((sum(prior_14[1:]) + 7665) / 14)


def test_no_missing_values(feats):
    assert feats[feature_columns(feats)].isna().sum().sum() == 0


def test_dates_are_sorted_and_unique(feats):
    assert feats.dteday.is_monotonic_increasing
    assert feats.dteday.is_unique


def test_unknown_weather_label_is_rejected():
    """An unseen weather label must raise, not become a silent NaN that a
    later dropna() deletes without comment."""
    from src.features import encode_weather

    known = pd.Series(["GOOD", "MISTY", "BAD"])
    assert encode_weather(known).tolist() == [0.0, 1.0, 2.0]  # valid labels still encode

    with pytest.raises(ValueError, match="STORMY"):
        encode_weather(pd.Series(["GOOD", "STORMY"]))
