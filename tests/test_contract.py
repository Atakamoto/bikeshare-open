"""Guard rails on the ingest contract and the trained model's behaviour."""
import pandas as pd
import pytest
from sklearn.metrics import r2_score

from src.config import LAG_WARMUP, TARGET
from src.features import build_features, feature_columns, reindex_to_calendar
from src.ingest import load_raw
from src.train import MODELS, temporal_split


@pytest.fixture(scope="module")
def raw():
    return load_raw().sort_values("dteday").reset_index(drop=True)


@pytest.fixture(scope="module")
def feats(raw):
    return build_features(raw)


def test_calendar_is_complete_before_lagging(raw):
    """The reindexed frame must have no gaps, or the lags are wrong."""
    grid = reindex_to_calendar(raw)
    assert set(grid.dteday.diff().dropna().dt.days.unique()) == {1}


def test_only_expected_rows_are_dropped(raw, feats):
    """Rows may only vanish for the lag warm-up or downstream of a genuinely
    absent day -- never because an encoder produced a silent NaN.

    Accounting: the first LAG_WARMUP days have no complete history. Each
    absent calendar day m costs the LAG_WARMUP rows after it (cnt_lag_1 is
    NaN on m+1, cnt_roll_7 is NaN on m+1..m+7, cnt_lag_7 on m+7; their
    union is 7 rows). Day m itself was never in `raw`, so it is not a loss.
    The bound is exact for the current feature set; add a longer lag and
    LAG_WARMUP in src/config.py must grow with it.
    """
    full = pd.date_range(raw.dteday.min(), raw.dteday.max(), freq="D")
    missing_days = len(full) - len(raw)
    allowed_loss = LAG_WARMUP + LAG_WARMUP * missing_days
    lost = len(raw) - len(feats)
    assert lost <= allowed_loss, f"lost {lost} rows; expected at most {allowed_loss}"


def test_beats_the_mean_baseline(feats):
    """A model that cannot beat predicting the training mean is not a result."""
    cols = feature_columns(feats)
    train, _, test = temporal_split(feats)
    ridge = MODELS["ridge"]
    ridge.fit(train[cols], train[TARGET])
    assert r2_score(test[TARGET], ridge.predict(test[cols])) > 0.4


def test_persistence_baseline_is_reported():
    """The baseline that matters for a lag-driven model is 'yesterday again'.
    It must be in the comparison, whatever its score."""
    assert "baseline_persistence" in MODELS


def test_unclassified_raw_column_is_rejected():
    """A raw column nobody has classified must stop ingest, not flow through.

    `feature_columns()` admits every numeric column not in FORBIDDEN, so a new
    numeric column in a refreshed CSV (say `cnt_next_day`, or a `casual` rename)
    would silently become a model input. The contract therefore requires every
    raw column to be listed in `EXPECTED_RAW_COLS`.

    Works on an in-memory copy; the CSV on disk is never touched.
    """
    from src.ingest import validate_raw

    clean = load_raw()
    validate_raw(clean)  # the real data passes

    tampered = clean.copy()
    tampered["cnt_tomorrow"] = tampered[TARGET].shift(-1)
    with pytest.raises(ValueError, match="cnt_tomorrow"):
        validate_raw(tampered)

    # Rejection must be specific to the unknown column, not a side effect.
    assert "cnt_tomorrow" not in clean.columns


def test_missing_required_column_is_still_rejected(raw):
    """Guard: adding the unexpected-column check must not loosen the old one."""
    from src.ingest import validate_raw

    with pytest.raises(ValueError, match="casual"):
        validate_raw(raw.drop(columns=["casual"]))
