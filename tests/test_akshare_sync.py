"""Unit tests for bank_pipeline.akshare_sync module."""

import pandas as pd
import pytest
from bank_pipeline.akshare_sync import search_macros, get_macro_data, _parse_chinese_date, MACRO_CATALOG

try:
    import akshare as ak  # noqa: F401
except ImportError:
    ak = None

requires_akshare = pytest.mark.skipif(
    ak is None,
    reason="akshare not installed",
)


def test_catalog_contains_shrzgm():
    results = search_macros("社会融资")
    ids = [r["id"] for r in results]
    assert "shrzgm" in ids


def test_catalog_contains_vegetable_basket():
    results = search_macros("菜篮子")
    ids = [r["id"] for r in results]
    assert "vegetable_basket" in ids


@requires_akshare
def test_shrzgm_fetch():
    df = get_macro_data("shrzgm")
    assert df is not None, "get_macro_data returned None for shrzgm"
    assert not df.empty, "get_macro_data returned empty DataFrame for shrzgm"
    assert "社会融资规模增量" in df.columns, f"Expected column not found, got: {list(df.columns)}"


@requires_akshare
def test_vegetable_basket_fetch():
    df = get_macro_data("vegetable_basket")
    assert df is not None, "get_macro_data returned None for vegetable_basket"
    assert not df.empty, "get_macro_data returned empty DataFrame for vegetable_basket"


def test_parse_chinese_date_yearly_returns_nat():
    """Year-only strings like '2025年' should return NaT so they get dropped."""
    assert pd.isna(_parse_chinese_date("2025年"))


def test_parse_chinese_date_quarterly_preserved():
    """Quarterly strings must still parse correctly."""
    ts = _parse_chinese_date("2025年第1季度")
    assert ts == pd.Timestamp("2025-01-01")


def test_catalog_construction_is_daily():
    meta = next(m for m in MACRO_CATALOG if m["id"] == "construction")
    assert meta["freq"] == "daily"


def test_catalog_energy_is_daily():
    meta = next(m for m in MACRO_CATALOG if m["id"] == "energy")
    assert meta["freq"] == "daily"


def test_catalog_agricultural_is_daily():
    meta = next(m for m in MACRO_CATALOG if m["id"] == "agricultural")
    assert meta["freq"] == "daily"


def test_catalog_freight_is_daily():
    meta = next(m for m in MACRO_CATALOG if m["id"] == "freight")
    assert meta["freq"] == "daily"
