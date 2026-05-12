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
