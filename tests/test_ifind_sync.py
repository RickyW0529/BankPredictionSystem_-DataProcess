from unittest.mock import patch, MagicMock

import pandas as pd
import pytest
import requests

from bank_pipeline.ifind_sync import IFindClient, get_ifind_client


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
