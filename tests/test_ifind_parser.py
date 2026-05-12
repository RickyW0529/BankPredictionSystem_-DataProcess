import os

import pandas as pd
import pytest

from bank_pipeline.ifind_parser import (
    parse_ifind_excel,
    detect_date_column_ifind,
    parse_yyyymmdd_date,
    extract_frequency_from_metadata,
    extract_unit_from_metadata,
    _detect_date_column_by_content,
    fix_column_names,
    filter_numeric_columns,
    auto_parse_dataframe,
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


def test_detect_date_column_by_content_yyyymmdd():
    """When column names are not standard, detect date column by YYYYMMDD content."""
    df = pd.DataFrame({
        "A": ["20260101", "20260201", "20260301"],
        "B": ["1.0", "2.0", "3.0"],
    })
    assert _detect_date_column_by_content(df) == "A"
    assert detect_date_column_ifind(df) == "A"


def test_detect_date_column_by_content_standard_date():
    """Detect standard ISO date strings like 2026-01-01."""
    df = pd.DataFrame({
        "col1": ["2026-01-01", "2026-02-01", "2026-03-01"],
        "col2": ["100", "200", "300"],
    })
    assert _detect_date_column_by_content(df) == "col1"
    assert detect_date_column_ifind(df) == "col1"


def test_detect_date_column_by_content_with_metadata():
    """Content detection should skip metadata rows and find date column."""
    df = pd.DataFrame({
        "foo": ["频率", "单位", "20260101", "20260201"],
        "bar": ["月", "%", "1.0", "2.0"],
    })
    assert detect_date_column_ifind(df) == "foo"


def test_detect_date_column_by_content_not_numeric():
    """Plain numeric columns should NOT be mis-detected as dates."""
    df = pd.DataFrame({
        "x": [1.0, 2.0, 3.0],
        "y": [4.0, 5.0, 6.0],
    })
    assert _detect_date_column_by_content(df) is None


def test_detect_date_column_by_content_chinese_date():
    """Detect Chinese date format like 2026年01月."""
    df = pd.DataFrame({
        "a": ["2026年01月", "2026年02月", "2026年03月"],
        "b": ["100", "200", "300"],
    })
    assert _detect_date_column_by_content(df) == "a"
    assert detect_date_column_ifind(df) == "a"


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


def test_fix_column_names_all_default():
    """When all column names are Unnamed, use first row as names."""
    df = pd.DataFrame({
        "Unnamed: 0": ["指标名称", "20260101", "20260201"],
        "Unnamed: 1": ["CPI同比", "2.5", "2.4"],
        "Unnamed: 2": ["GDP同比", "5.1", "5.2"],
    })
    fixed = fix_column_names(df)
    assert list(fixed.columns) == ["指标名称", "CPI同比", "GDP同比"]
    assert len(fixed) == 2
    assert fixed["指标名称"].iloc[0] == "20260101"


def test_fix_column_names_partial_default():
    """Fix only the default column names, keep valid ones (do not drop row)."""
    # 4 columns, only 1 is default -> minority, should only fix that one
    df = pd.DataFrame({
        "指标名称": ["频率", "20260101", "20260201"],
        "CPI": ["2.5", "2.6", "2.4"],
        "GDP": ["5.1", "5.2", "5.3"],
        "Unnamed: 3": ["备注", "A", "B"],
    })
    fixed = fix_column_names(df)
    assert "指标名称" in fixed.columns
    assert "CPI" in fixed.columns
    assert "GDP" in fixed.columns
    assert "备注" in fixed.columns
    # First row should be kept because majority columns have real data there
    assert len(fixed) == 3
    assert fixed["指标名称"].iloc[0] == "频率"


def test_filter_numeric_columns_skips_text():
    """Non-numeric columns should be filtered out."""
    df = pd.DataFrame({
        "日期": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"]),
        "CPI": [2.5, 2.4, 2.3],
        "备注": ["备注A", "备注B", "备注C"],
        "地区": ["北京", "上海", "广州"],
    })
    cols = filter_numeric_columns(df, "日期")
    assert cols == ["CPI"]


def test_filter_numeric_columns_keeps_mixed():
    """Columns with mostly numeric values should be kept."""
    df = pd.DataFrame({
        "日期": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"]),
        "CPI": [2.5, 2.4, None],
        "备注": ["A", "B", "C"],
    })
    cols = filter_numeric_columns(df, "日期")
    assert cols == ["CPI"]


def test_auto_parse_dataframe_skips_text_columns():
    """auto_parse_dataframe should skip text columns and keep numeric ones."""
    df = pd.DataFrame({
        "指标名称": ["20260101", "20260201", "20260301"],
        "CPI": ["2.5", "2.4", "2.3"],
        "备注": ["A", "B", "C"],
        "地区": ["北京", "上海", "广州"],
    })
    result = auto_parse_dataframe(df)
    assert result["date_col"] == "指标名称"
    assert result["data_cols"] == ["CPI"]
    assert len(result["data"]) == 3
    assert "备注" not in result["data"].columns
    assert "地区" not in result["data"].columns


def test_auto_parse_dataframe_fixes_default_names():
    """auto_parse_dataframe should fix default column names and parse."""
    df = pd.DataFrame({
        "Unnamed: 0": ["指标名称", "20260101", "20260201"],
        "Unnamed: 1": ["CPI", "2.5", "2.4"],
    })
    result = auto_parse_dataframe(df)
    assert result["date_col"] == "指标名称"
    assert result["data_cols"] == ["CPI"]
    assert len(result["data"]) == 2
