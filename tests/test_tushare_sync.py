"""Unit tests for bank_pipeline.tushare_sync module."""

import os
from typing import Dict, List

import pandas as pd
import pytest

from bank_pipeline.tushare_sync import (
    TUSHARE_CATALOG,
    search_tushare,
    test_api_connection as _test_api_connection,
    get_tushare_data,
    merge_tushare_selected,
)

API_URL = "http://tsy.xiaodefa.cn"
TUSHARE_TOKEN = os.environ.get(
    "TUSHARE_TOKEN", "5d61f00d3f0d18bfbd2b3cb713ebf9c753aa6d4e8ab8e7be99369fa6"
)

try:
    import tushare as ts  # noqa: F401

    TUSHARE_INSTALLED = True
except ImportError:
    TUSHARE_INSTALLED = False

requires_tushare = pytest.mark.skipif(
    not TUSHARE_INSTALLED or not TUSHARE_TOKEN,
    reason="tushare not installed or no token available",
)


# ---------------------------------------------------------------------------
# Catalog tests
# ---------------------------------------------------------------------------
def test_tushare_catalog_frequencies():
    """All indicators must declare one of daily/monthly/quarterly."""
    valid_freqs = {"daily", "monthly", "quarterly"}
    for item in TUSHARE_CATALOG:
        assert item["freq"] in valid_freqs, (
            f"Indicator '{item['id']}' has invalid frequency '{item['freq']}'"
        )


def test_tushare_catalog_total():
    """Catalog must contain exactly 15 macro indicators."""
    assert len(TUSHARE_CATALOG) == 15


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------
def test_search_tushare_empty_keyword():
    """Empty keyword should return the full catalog."""
    result = search_tushare("")
    assert len(result) == len(TUSHARE_CATALOG)
    ids = [r["id"] for r in result]
    assert ids == [item["id"] for item in TUSHARE_CATALOG]


def test_search_tushare_by_name():
    """Searching by name (case-insensitive) should return matching indicators."""
    result = search_tushare("CPI")
    ids = [r["id"] for r in result]
    assert "cpi" in ids


def test_search_tushare_by_id():
    """Searching by id should return exactly one result."""
    result = search_tushare("gdp")
    assert len(result) == 1
    assert result[0]["id"] == "gdp"


# ---------------------------------------------------------------------------
# API connection tests
# ---------------------------------------------------------------------------
def test_api_connection_invalid():
    """Fake token must be rejected."""
    ok, msg = _test_api_connection("fake_token", API_URL)
    assert ok is False
    assert isinstance(msg, str)


@requires_tushare
def test_api_connection_valid():
    """Real token must succeed."""
    ok, msg = _test_api_connection(TUSHARE_TOKEN, API_URL)
    assert ok is True
    assert msg == "连接成功"


# ---------------------------------------------------------------------------
# Data fetch tests
# ---------------------------------------------------------------------------
@requires_tushare
def test_get_tushare_data_cpi():
    """Fetch CPI and verify expected columns and non-empty shape."""
    df = get_tushare_data(
        "cpi",
        token=TUSHARE_TOKEN,
        api_url=API_URL,
        use_cache=False,
    )
    assert df is not None, "get_tushare_data returned None for cpi"
    assert not df.empty, "CPI DataFrame is empty"
    assert "指标名称" in df.columns, "Missing date column '指标名称'"

    meta = next(item for item in TUSHARE_CATALOG if item["id"] == "cpi")
    for col in meta["columns"]:
        assert col in df.columns, f"Expected column '{col}' missing from CPI data"


@requires_tushare
def test_get_tushare_data_with_date_filter():
    """Date filtering must restrict returned rows to the requested range."""
    start_date = "2020-01-01"
    end_date = "2020-12-31"
    df = get_tushare_data(
        "cpi",
        token=TUSHARE_TOKEN,
        api_url=API_URL,
        use_cache=False,
        start_date=start_date,
        end_date=end_date,
    )
    assert df is not None, "get_tushare_data returned None"
    assert not df.empty, "Filtered DataFrame is empty"

    dates = df["指标名称"]
    assert dates.min() >= pd.Timestamp(start_date), "Data starts before start_date"
    assert dates.max() <= pd.Timestamp(end_date), "Data ends after end_date"


# ---------------------------------------------------------------------------
# Merge tests
# ---------------------------------------------------------------------------
@requires_tushare
def test_merge_tushare_selected(tmp_path) -> None:
    """Merge 3 monthly indicators and verify output shape and Date column."""
    output_path = tmp_path / "tushare_merged.csv"
    selected = ["cpi", "ppi", "m2"]

    merged_df, metadata = merge_tushare_selected(
        selected_ids=selected,
        token=TUSHARE_TOKEN,
        api_url=API_URL,
        output_path=str(output_path),
    )

    assert merged_df is not None, "merge_tushare_selected returned None"
    assert not merged_df.empty, "Merged DataFrame is empty"
    assert "Date" in merged_df.columns, "Missing 'Date' column in merged output"
    assert merged_df.shape[0] > 0, "Merged DataFrame has no rows"
    assert merged_df.shape[1] > 1, "Merged DataFrame has no feature columns"

    assert metadata["selected"] == selected
    assert set(metadata["fetched"]).issubset(set(selected))
    assert output_path.exists(), "Output CSV was not written"
