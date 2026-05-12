"""iFinD HTTP API client for macro data."""

import logging
from typing import Dict, List, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://ft.10jqka.com.cn/api/v1"


class IFindClient:
    """Thin HTTP client for iFinD macro data API."""

    def __init__(self, access_token: str, base_url: str = DEFAULT_BASE_URL):
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "access_token": access_token,
            "Content-Type": "application/json",
        }

    def _post(self, endpoint: str, payload: Dict) -> Optional[Dict]:
        """Send POST request and return JSON response."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = requests.post(url, headers=self._headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code", 0) != 0:
                logger.warning("iFinD API error: %s", data.get("message", "unknown"))
                return None
            return data
        except requests.exceptions.RequestException as e:
            logger.error("iFinD HTTP request failed: %s", e)
            return None

    def fetch_history(
        self,
        indicator: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: str = "day",
    ) -> Optional[pd.DataFrame]:
        """Fetch historical macro data for a given indicator.

        Parameters
        ----------
        indicator: str
            iFinD indicator code (e.g. 'M0000001').
        start_date, end_date: str, optional
            Date range in YYYYMMDD format.
        frequency: str
            'day', 'month', 'quarter', 'year'.

        Returns
        -------
        pd.DataFrame or None
        """
        payload = {
            "indicator": indicator,
            "frequency": frequency,
        }
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date

        result = self._post("basic_data_service", payload)
        if result is None or "data" not in result:
            return None

        data = result["data"]
        table = data.get("table", [])
        header = data.get("header", [])

        if not table or not header:
            logger.warning("Empty data returned for indicator %s", indicator)
            return None

        df = pd.DataFrame(table, columns=header)

        # Detect date column (usually the first column) and parse
        date_col = header[0] if header else None
        if date_col is None:
            logger.warning("No header found for indicator %s", indicator)
            return None

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        df = df.rename(columns={date_col: "指标名称"})

        # Coerce remaining columns to numeric
        for col in df.columns:
            if col != "指标名称":
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def test_connection(self) -> bool:
        """Test if the access_token is valid."""
        # Use a minimal query to verify token
        result = self._post("basic_data_service", {"indicator": "M0000001", "limit": 1})
        return result is not None


# Convenience module-level functions for Streamlit integration


def get_ifind_client(access_token: str) -> IFindClient:
    return IFindClient(access_token)


def fetch_ifind_indicator(
    indicator: str,
    access_token: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    frequency: str = "day",
) -> Optional[pd.DataFrame]:
    client = get_ifind_client(access_token)
    return client.fetch_history(indicator, start_date, end_date, frequency)
