import pandas as pd
from bank_pipeline.loader import detect_frequency


def test_detect_frequency_monthly_21_days():
    """Business-day-monthly (~21 days) should be detected as monthly."""
    dates = pd.date_range("2024-01-01", periods=6, freq="BMS")
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
    """Daily with weekend gaps (median diff 1-2 days) should be daily."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({"dt": dates})
    assert detect_frequency(df, "dt") == "daily"
