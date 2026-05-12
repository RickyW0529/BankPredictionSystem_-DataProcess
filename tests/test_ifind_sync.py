import json
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest
import requests

from bank_pipeline.ifind_sync import (
    IFindClient,
    get_ifind_client,
    IFIND_CATALOG,
    search_ifind,
    get_ifind_catalog,
    _load_custom_catalog,
    save_ifind_catalog,
    reset_ifind_catalog,
    get_ifind_data,
    merge_ifind_selected,
    load_ifind_token,
    save_ifind_token,
    clear_ifind_token,
)


def test_client_init_with_access_token():
    client = IFindClient(access_token="test_token")
    assert client.access_token == "test_token"
    assert client.base_url == "https://ft.10jqka.com.cn/api/v1"


def test_client_default_headers():
    client = IFindClient(access_token="test_token")
    assert client._headers["access_token"] == "test_token"
    assert client._headers["Content-Type"] == "application/json"


@patch("bank_pipeline.ifind_sync.requests.post")
def test_fetch_history_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "code": 0,
        "data": {
            "table": [
                ["20260101", "1.0"],
                ["20260201", "2.0"],
            ],
            "header": ["时间", "CPI"],
        },
    }
    mock_post.return_value = mock_resp

    client = IFindClient(access_token="test_token")
    df = client.fetch_history(indicator="M0000001", start_date="20260101", end_date="20260201")

    assert df is not None
    assert len(df) == 2
    assert "指标名称" in df.columns
    assert "CPI" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df["指标名称"])
    assert df["CPI"].dtype == "float64"


@patch("bank_pipeline.ifind_sync.requests.post")
def test_fetch_history_api_error(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": -1, "message": "invalid indicator"}
    mock_post.return_value = mock_resp

    client = IFindClient(access_token="test_token")
    df = client.fetch_history(indicator="INVALID")
    assert df is None


@patch("bank_pipeline.ifind_sync.requests.post")
def test_fetch_history_http_error(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

    client = IFindClient(access_token="test_token")
    df = client.fetch_history(indicator="M0000001")
    assert df is None


@patch("bank_pipeline.ifind_sync.requests.post")
def test_test_connection_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": 0, "data": {"table": [["20260101", "1.0"]], "header": ["时间", "CPI"]}}
    mock_post.return_value = mock_resp

    client = IFindClient(access_token="test_token")
    assert client.test_connection() is True


@patch("bank_pipeline.ifind_sync.requests.post")
def test_test_connection_failure(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

    client = IFindClient(access_token="test_token")
    assert client.test_connection() is False


def test_get_ifind_client():
    client = get_ifind_client("my_token")
    assert isinstance(client, IFindClient)
    assert client.access_token == "my_token"


def test_ifind_catalog_not_empty():
    assert len(IFIND_CATALOG) > 0
    assert all("id" in item and "name" in item and "indicator" in item for item in IFIND_CATALOG)


def test_search_ifind_empty_keyword():
    results = search_ifind("")
    assert len(results) == len(IFIND_CATALOG)


def test_search_ifind_by_name():
    results = search_ifind("CPI")
    assert len(results) >= 1
    assert all("CPI" in r["name"] or "cpi" in r["id"] for r in results)


def test_search_ifind_by_indicator():
    results = search_ifind("M002826730")
    assert len(results) >= 1
    assert any(r.get("indicator") == "M002826730" for r in results)


def test_search_ifind_no_match():
    results = search_ifind("NONEXISTENTXYZ123")
    assert len(results) == 0


def test_get_ifind_catalog_returns_defaults():
    catalog = get_ifind_catalog()
    assert len(catalog) == len(IFIND_CATALOG)


def test_load_custom_catalog_missing_file():
    custom = _load_custom_catalog("/tmp/nonexistent_ifind_catalog_12345.json")
    assert custom == []


def test_load_custom_catalog_valid_file(tmp_path):
    custom_path = tmp_path / "ifind_catalog.json"
    custom_data = [
        {"id": "custom_1", "name": "自定义指标1", "freq": "monthly", "indicator": "X0000001"},
    ]
    custom_path.write_text(json.dumps(custom_data), encoding="utf-8")
    loaded = _load_custom_catalog(str(custom_path))
    assert len(loaded) == 1
    assert loaded[0]["id"] == "custom_1"


def test_get_ifind_catalog_merges_custom(tmp_path, monkeypatch):
    custom_path = tmp_path / "ifind_catalog.json"
    custom_data = [
        {"id": "cpi_yoy", "name": "CPI同比(覆盖)", "freq": "monthly", "indicator": "M0009999"},
        {"id": "custom_new", "name": "新增指标", "freq": "daily", "indicator": "M0008888"},
    ]
    custom_path.write_text(json.dumps(custom_data), encoding="utf-8")
    monkeypatch.setattr(
        "bank_pipeline.config.IFIND_CUSTOM_CATALOG_PATH", str(custom_path)
    )
    catalog = get_ifind_catalog()
    merged_ids = {item["id"] for item in catalog}
    assert "custom_new" in merged_ids
    cpi_item = next(item for item in catalog if item["id"] == "cpi_yoy")
    assert cpi_item["indicator"] == "M0009999"
    assert cpi_item["name"] == "CPI同比(覆盖)"


@patch("bank_pipeline.ifind_sync.IFindClient")
def test_get_ifind_data_uses_catalog(mock_client_class):
    mock_client = MagicMock()
    mock_client.fetch_history.return_value = pd.DataFrame({
        "指标名称": pd.to_datetime(["2026-01-01", "2026-02-01"]),
        "value": [1.0, 2.0],
    })
    mock_client_class.return_value = mock_client

    df = get_ifind_data(
        "CPI_当月同比",
        access_token="test_token",
        use_cache=False,
    )
    assert df is not None
    assert len(df) == 2
    mock_client.fetch_history.assert_called_once()
    call_args = mock_client.fetch_history.call_args
    assert call_args.args[0] == "M002826730"


def test_get_ifind_data_unknown_id():
    df = get_ifind_data(
        "nonexistent_id",
        access_token="test_token",
        use_cache=False,
    )
    assert df is None


@patch("bank_pipeline.ifind_sync.get_ifind_data")
def test_merge_ifind_selected(mock_get_data):
    mock_get_data.return_value = pd.DataFrame({
        "指标名称": pd.to_datetime(["2026-01-01", "2026-02-01"]),
        "value": [1.0, 2.0],
    })

    merged_df, meta = merge_ifind_selected(
        ["CPI_当月同比", "PPI_当月同比"],
        access_token="test_token",
        output_path="./output/test_ifind_merged.csv",
    )
    assert merged_df is not None
    assert meta["fetched"] == ["CPI_当月同比", "PPI_当月同比"]
    assert meta["failed"] == []


def test_save_and_load_ifind_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "bank_pipeline.config.IFIND_CUSTOM_CATALOG_PATH", str(tmp_path / "catalog.json")
    )
    catalog = [{"id": "a", "name": "A", "freq": "monthly", "indicator": "M1"}]
    save_ifind_catalog(catalog)
    loaded = _load_custom_catalog()
    assert len(loaded) == 1
    assert loaded[0]["indicator"] == "M1"


def test_reset_ifind_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "bank_pipeline.config.IFIND_CUSTOM_CATALOG_PATH", str(tmp_path / "catalog.json")
    )
    save_ifind_catalog([{"id": "a", "name": "A", "freq": "monthly", "indicator": "M1"}])
    reset_ifind_catalog()
    loaded = _load_custom_catalog()
    assert loaded == []


def test_load_save_ifind_token(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "bank_pipeline.config.IFIND_TOKEN_PATH", tmp_path / "token.json"
    )
    assert load_ifind_token() is None
    save_ifind_token("my_secret_token")
    assert load_ifind_token() == "my_secret_token"
    clear_ifind_token()
    assert load_ifind_token() is None
