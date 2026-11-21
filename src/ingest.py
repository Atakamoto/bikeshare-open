"""Stage 1: fetch the raw dataset and assert its shape.

Run: python -m src.ingest
"""
import sys
import urllib.request

import pandas as pd

from src.config import DATA_URL, EXPECTED_RAW_COLS, RAW

EXPECTED_MIN_ROWS = 700
REQUIRED_COLS = {"dteday", "cnt", "casual", "registered", "temp", "hum", "windspeed"}


def download(force: bool = False) -> None:
    if RAW.exists() and not force:
        return
    RAW.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(DATA_URL, RAW)


def validate_raw(df: pd.DataFrame) -> None:
    """Raise ValueError unless `df` matches the raw-data contract."""
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"raw data is missing required columns: {sorted(missing)}")
    unclassified = set(df.columns) - EXPECTED_RAW_COLS
    if unclassified:
        raise ValueError(
            f"raw data has unclassified columns: {sorted(unclassified)}. "
            "Decide whether each is leakage, a time index, or a feature, then "
            "add it to EXPECTED_RAW_COLS (and FORBIDDEN if excluded) in src/config.py."
        )
    if len(df) < EXPECTED_MIN_ROWS:
        raise ValueError(f"raw data has only {len(df)} rows; expected >= {EXPECTED_MIN_ROWS}")


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(RAW, parse_dates=["dteday"])
    validate_raw(df)
    return df


if __name__ == "__main__":
    download(force="--force" in sys.argv)
    df = load_raw()
    print(f"OK ingest: {len(df)} rows, {df.dteday.min().date()} -> {df.dteday.max().date()}")
