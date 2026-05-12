import os

import pandas as pd
import pytest

from bank_pipeline.ifind_parser import (
    parse_ifind_excel,
    detect_date_column_ifind,
    parse_yyyymmdd_date,
    extract_frequency_from_metadata,
    extract_unit_from_metadata,
)


def test_detect_date_column_ifind_standard():
    df = pd.DataFrame({"指标名称": ["20260101", "20260201"], "CPI": [1.0, 2.0]})
    assert detect_date_column_ifind(df) == "指标名称"


def test_detect_date_column_ifind_fallback():
    df = pd.DataFrame({"日期": ["20260101", "20260201"], "CPI": [1.0, 2.0]})
    assert detect_date_column_ifind(df) == "日期"


def test_parse_yyyymmdd_date():
    series = pd.Series(["20260331", "20260228", "invalid", None])
    result = parse_yyyymmdd_date(series)
    assert result[0] == pd.Timestamp("2026-03-31")
    assert result[1] == pd.Timestamp("2026-02-28")
    assert pd.isna(result[2])
    assert pd.isna(result[3])


def test_extract_frequency_monthly():
    df = pd.DataFrame({"指标名称": ["频率", "单位", "20260101"], "a": ["月", "%", "1.0"]})
    assert extract_frequency_from_metadata(df) == "monthly"


def test_extract_frequency_daily():
    df = pd.DataFrame({"指标名称": ["频率", "单位", "20260101"], "a": ["日", "元", "1.0"]})
    assert extract_frequency_from_metadata(df) == "daily"


def test_extract_frequency_quarterly():
    df = pd.DataFrame({"指标名称": ["频率", "单位", "20260101"], "a": ["季", "%", "1.0"]})
    assert extract_frequency_from_metadata(df) == "quarterly"


def test_extract_frequency_no_metadata():
    df = pd.DataFrame({"指标名称": ["20260101", "20260102"], "a": ["1.0", "2.0"]})
    assert extract_frequency_from_metadata(df) == "unknown"


def test_extract_unit_from_metadata():
    df = pd.DataFrame({"指标名称": ["频率", "单位", "20260101"], "a": ["月", "%", "1.0"]})
    assert extract_unit_from_metadata(df) == "%"


def test_parse_ifind_excel_monthly_with_metadata():
    df = pd.DataFrame({
        "指标名称": ["频率", "单位", "20260331", "20260228", "20260131"],
        "CPI同比": ["月", "%", "3.3", "2.4", "2.4"],
    })
    result = parse_ifind_excel(df)
    assert result["date_col"] == "指标名称"
    assert result["data_cols"] == ["CPI同比"]
    assert result["freq"] == "monthly"
    assert result["unit"] == "%"
    assert len(result["data"]) == 3
    assert result["data"]["指标名称"].iloc[0] == pd.Timestamp("2026-03-31")


def test_parse_ifind_excel_daily_no_metadata():
    df = pd.DataFrame({
        "指标名称": ["20260511", "20260509", "20260508"],
        "价格": ["193000", "189000", "189000"],
    })
    result = parse_ifind_excel(df)
    assert result["date_col"] == "指标名称"
    assert result["data_cols"] == ["价格"]
    assert result["freq"] in ("daily", "unknown")
    assert len(result["data"]) == 3


REFERENCE_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "Reference data table")


@pytest.mark.skipif(
    not os.path.exists(REFERENCE_DIR),
    reason="Reference data directory not found",
)
def test_parse_real_monthly_cpi():
    """Parse the real monthly CPI Excel file."""
    files = [f for f in os.listdir(REFERENCE_DIR) if "CPI" in f and f.endswith(".xlsx")]
    if not files:
        pytest.skip("CPI reference file not found")
    path = os.path.join(REFERENCE_DIR, sorted(files)[0])
    df_raw = pd.read_excel(path)
    result = parse_ifind_excel(df_raw)
    assert result["date_col"] == "指标名称"
    assert result["freq"] == "monthly"
    assert len(result["data_cols"]) >= 1
    assert len(result["data"]) > 10


@pytest.mark.skipif(
    not os.path.exists(REFERENCE_DIR),
    reason="Reference data directory not found",
)
def test_parse_real_quarterly_gdp():
    """Parse the real quarterly GDP Excel file."""
    files = [f for f in os.listdir(REFERENCE_DIR) if "GDP" in f and f.endswith(".xlsx")]
    if not files:
        pytest.skip("GDP reference file not found")
    path = os.path.join(REFERENCE_DIR, sorted(files)[0])
    df_raw = pd.read_excel(path)
    result = parse_ifind_excel(df_raw)
    assert result["date_col"] == "指标名称"
    assert result["freq"] == "quarterly"
    assert len(result["data_cols"]) >= 1
    assert len(result["data"]) > 4


@pytest.mark.skipif(
    not os.path.exists(REFERENCE_DIR),
    reason="Reference data directory not found",
)
def test_parse_real_daily_spot_price():
    """Parse the real daily spot price Excel file."""
    files = [f for f in os.listdir(REFERENCE_DIR) if "现货价" in f and f.endswith(".xlsx")]
    if not files:
        pytest.skip("Spot price reference file not found")
    path = os.path.join(REFERENCE_DIR, sorted(files)[0])
    df_raw = pd.read_excel(path)
    result = parse_ifind_excel(df_raw)
    assert result["date_col"] == "指标名称"
    # Daily data may not have metadata rows; freq detected from dates
    assert result["freq"] in ("daily", "unknown")
    assert len(result["data_cols"]) >= 1
    assert len(result["data"]) > 10
