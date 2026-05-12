import pandas as pd
from bank_pipeline.loader import detect_frequency


def test_detect_frequency_monthly_21_days():
    """~21-day spacing should be detected as monthly."""
    dates = pd.date_range("2024-01-01", periods=6, freq="21D")
    df = pd.DataFrame({"dt": dates})
    assert detect_frequency(df, "dt") == "monthly"


def test_detect_frequency_monthly_35_days():
    """Sparse monthly (~35 days) should still be monthly."""
    dates = pd.to_datetime(["2024-01-05", "2024-02-10", "2024-03-15", "2024-04-20"])
    df = pd.DataFrame({"dt": dates})
    assert detect_frequency(df, "dt") == "monthly"


def test_detect_frequency_quarterly_80_days():
    """Quarterly at ~80 days should be detected as quarterly."""
    dates = pd.to_datetime(["2024-01-01", "2024-04-20", "2024-07-15", "2024-10-10"])
    df = pd.DataFrame({"dt": dates})
    assert detect_frequency(df, "dt") == "quarterly"


def test_detect_frequency_daily_weekend_gaps():
    """Daily with every-2-day gaps (median diff 2 days) should be daily."""
    dates = pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-05", "2024-01-07", "2024-01-09", "2024-01-11"])
    df = pd.DataFrame({"dt": dates})
    assert detect_frequency(df, "dt") == "daily"


def test_detect_frequency_boundary_2_days():
    """Exact boundary: median diff of 2 days should be daily."""
    dates = pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-05"])
    df = pd.DataFrame({"dt": dates})
    assert detect_frequency(df, "dt") == "daily"


def test_detect_frequency_boundary_20_days():
    """Exact boundary: median diff of 20 days should be monthly."""
    dates = pd.to_datetime(["2024-01-01", "2024-01-21", "2024-02-10"])
    df = pd.DataFrame({"dt": dates})
    assert detect_frequency(df, "dt") == "monthly"


def test_detect_frequency_boundary_40_days():
    """Exact boundary: median diff of 40 days should be monthly."""
    dates = pd.to_datetime(["2024-01-01", "2024-02-10", "2024-03-21"])
    df = pd.DataFrame({"dt": dates})
    assert detect_frequency(df, "dt") == "monthly"


def test_detect_frequency_boundary_80_days():
    """Exact boundary: median diff of 80 days should be quarterly."""
    dates = pd.to_datetime(["2024-01-01", "2024-03-21", "2024-06-10"])
    df = pd.DataFrame({"dt": dates})
    assert detect_frequency(df, "dt") == "quarterly"


def test_detect_frequency_boundary_100_days():
    """Exact boundary: median diff of 100 days should be quarterly."""
    dates = pd.to_datetime(["2024-01-01", "2024-04-10", "2024-07-20"])
    df = pd.DataFrame({"dt": dates})
    assert detect_frequency(df, "dt") == "quarterly"


def test_detect_frequency_unknown_weekly():
    """Weekly (~7 days) should return unknown."""
    dates = pd.date_range("2024-01-01", periods=6, freq="7D")
    df = pd.DataFrame({"dt": dates})
    assert detect_frequency(df, "dt") == "unknown"


def test_detect_frequency_unknown_biweekly():
    """Bi-weekly (~14 days) should return unknown."""
    dates = pd.date_range("2024-01-01", periods=6, freq="14D")
    df = pd.DataFrame({"dt": dates})
    assert detect_frequency(df, "dt") == "unknown"


def test_detect_frequency_missing_column():
    """Missing date column should return unknown."""
    df = pd.DataFrame({"other": [1, 2, 3]})
    assert detect_frequency(df, "dt") == "unknown"


def test_detect_frequency_fewer_than_two_dates():
    """Fewer than 2 valid dates should return unknown."""
    df = pd.DataFrame({"dt": [pd.Timestamp("2024-01-01")]})
    assert detect_frequency(df, "dt") == "unknown"
