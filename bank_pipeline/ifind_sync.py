"""iFinD HTTP API client for macro data."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://ft.10jqka.com.cn/api/v1"

FREQ_MAP = {"daily": "日度", "monthly": "月度", "quarterly": "季度", "yearly": "年度"}

# Default catalog of common macro indicators for iFinD.
# Users can override or extend these via `ifind_catalog.json`.
IFIND_CATALOG: List[Dict] = [
    {"id": "cpi_yoy", "name": "CPI同比", "freq": "monthly", "indicator": "M0000001"},
    {"id": "cpi_mom", "name": "CPI环比", "freq": "monthly", "indicator": "M0000002"},
    {"id": "cpi_accu", "name": "CPI累计同比", "freq": "monthly", "indicator": "M0000003"},
    {"id": "ppi_yoy", "name": "PPI同比", "freq": "monthly", "indicator": "M0000138"},
    {"id": "ppi_mom", "name": "PPI环比", "freq": "monthly", "indicator": "M0000139"},
    {"id": "industrial_yoy", "name": "工业增加值同比", "freq": "monthly", "indicator": "M0000274"},
    {"id": "industrial_accu", "name": "工业增加值累计同比", "freq": "monthly", "indicator": "M0000275"},
    {"id": "m0_yoy", "name": "M0同比", "freq": "monthly", "indicator": "M0000091"},
    {"id": "m1_yoy", "name": "M1同比", "freq": "monthly", "indicator": "M0000092"},
    {"id": "m2_yoy", "name": "M2同比", "freq": "monthly", "indicator": "M0000093"},
    {"id": "retail_yoy", "name": "社会消费品零售总额同比", "freq": "monthly", "indicator": "M0001428"},
    {"id": "retail_accu", "name": "社会消费品零售总额累计同比", "freq": "monthly", "indicator": "M0001429"},
    {"id": "investment_accu", "name": "固定资产投资累计同比", "freq": "monthly", "indicator": "M0000545"},
    {"id": "import_yoy", "name": "进口同比", "freq": "monthly", "indicator": "M0000604"},
    {"id": "export_yoy", "name": "出口同比", "freq": "monthly", "indicator": "M0000605"},
    {"id": "trade_balance", "name": "贸易差额", "freq": "monthly", "indicator": "M0000607"},
    {"id": "fx_reserve", "name": "外汇储备", "freq": "monthly", "indicator": "M0001227"},
    {"id": "pmi_mfg", "name": "制造业PMI", "freq": "monthly", "indicator": "M0009856"},
    {"id": "pmi_nonmfg", "name": "非制造业PMI", "freq": "monthly", "indicator": "M0009857"},
    {"id": "pmi_cx", "name": "财新制造业PMI", "freq": "monthly", "indicator": "M0009862"},
    {"id": "lpr_1y", "name": "LPR(1年)", "freq": "daily", "indicator": "M0009915"},
    {"id": "lpr_5y", "name": "LPR(5年)", "freq": "daily", "indicator": "M0009916"},
    {"id": "shibor_overnight", "name": "SHIBOR隔夜", "freq": "daily", "indicator": "M0009898"},
    {"id": "gdp_yoy", "name": "GDP同比", "freq": "quarterly", "indicator": "M0000272"},
    {"id": "gdp", "name": "GDP当季值", "freq": "quarterly", "indicator": "M0000271"},
    {"id": "fdi_yoy", "name": "外商直接投资同比", "freq": "monthly", "indicator": "M0001416"},
    {"id": "new_credit", "name": "新增人民币贷款", "freq": "monthly", "indicator": "M0001384"},
    {"id": "shrzgm", "name": "社会融资规模增量", "freq": "monthly", "indicator": "M0001383"},
    {"id": "house_price_yoy", "name": "70城房价同比", "freq": "monthly", "indicator": "M0001431"},
    {"id": "house_price_mom", "name": "70城房价环比", "freq": "monthly", "indicator": "M0001432"},
    {"id": "gold_reserve", "name": "黄金储备", "freq": "monthly", "indicator": "M0001228"},
    {"id": "unemployment", "name": "城镇调查失业率", "freq": "monthly", "indicator": "M0001430"},
    {"id": "foreign_debt", "name": "外债余额", "freq": "quarterly", "indicator": "M0001433"},
    {"id": "electricity", "name": "全社会用电量", "freq": "monthly", "indicator": "M0001434"},
    {"id": "railway", "name": "铁路货运量", "freq": "monthly", "indicator": "M0001435"},
    {"id": "logistics", "name": "物流业景气指数", "freq": "monthly", "indicator": "M0001436"},
]

IFIND_CUSTOM_CATALOG_PATH = os.environ.get("IFIND_CATALOG_PATH", "./ifind_catalog.json")


def _load_custom_catalog(path: Optional[str] = None) -> List[Dict]:
    """Load user-defined indicator catalog from JSON.

    JSON format: a list of dicts with keys `id`, `name`, `freq`, `indicator`.
    User entries override defaults by `id`, and new entries are appended.
    """
    p = Path(path) if path else Path(IFIND_CUSTOM_CATALOG_PATH)
    if not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        logger.warning("Custom catalog %s is not a list, ignoring", p)
        return []
    except Exception as e:
        logger.warning("Failed to load custom iFinD catalog from %s: %s", p, e)
        return []


def get_ifind_catalog() -> List[Dict]:
    """Return full catalog (defaults + custom overrides/appends)."""
    custom = _load_custom_catalog()
    merged = {item["id"]: item for item in IFIND_CATALOG}
    for item in custom:
        if "id" in item and "indicator" in item:
            merged[item["id"]] = item
    return list(merged.values())


def search_ifind(keyword: str = "") -> List[Dict]:
    """Search iFinD catalog by keyword (case-insensitive)."""
    keyword = keyword.strip().lower()
    catalog = get_ifind_catalog()
    if not keyword:
        return catalog
    return [
        item
        for item in catalog
        if keyword in item.get("id", "").lower()
        or keyword in item.get("name", "").lower()
        or keyword in item.get("indicator", "").lower()
    ]


def get_ifind_data(
    indicator_id: str,
    access_token: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    frequency: str = "day",
    use_cache: bool = True,
    cache_dir: str = "./.ifind_cache",
) -> Optional[pd.DataFrame]:
    """Fetch iFinD macro data by catalog ID, with optional caching."""
    catalog = get_ifind_catalog()
    meta = next((item for item in catalog if item["id"] == indicator_id), None)
    if meta is None:
        logger.warning("indicator_id %s not found in iFinD catalog", indicator_id)
        return None

    indicator = meta["indicator"]
    cache_path = Path(cache_dir) / f"{indicator_id}_{indicator}.csv"

    df = None
    if use_cache and cache_path.exists():
        logger.info("Cache hit for %s, reading from %s", indicator_id, cache_path)
        try:
            df = pd.read_csv(cache_path)
            df["指标名称"] = pd.to_datetime(df["指标名称"], errors="coerce")
            df = df.dropna(subset=["指标名称"])
            df = df.sort_values(by="指标名称", ascending=True)
        except Exception as e:
            logger.warning("Failed to read cache for %s: %s", indicator_id, e)
            df = None

    if df is None:
        logger.info("Fetching %s from iFinD...", indicator_id)
        client = IFindClient(access_token)
        df = client.fetch_history(
            indicator,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
        )
        if df is not None and use_cache:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                df.to_csv(cache_path, index=False)
                logger.info("Saved cache for %s to %s", indicator_id, cache_path)
            except Exception as e:
                logger.warning("Failed to save cache for %s: %s", indicator_id, e)

    if df is None or df.empty:
        return None

    # Apply date range filter
    if start_date:
        start_dt = pd.to_datetime(start_date)
        df = df[df["指标名称"] >= start_dt]
    if end_date:
        end_dt = pd.to_datetime(end_date)
        df = df[df["指标名称"] <= end_dt]

    return df.reset_index(drop=True)


def merge_ifind_selected(
    selected_ids: List[str],
    access_token: str,
    frequency: str = "day",
    output_path: str = "./output/ifind_merged.csv",
    missing_value_threshold: float = 20.0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[Optional[pd.DataFrame], Dict]:
    """Fetch and merge selected iFinD indicators."""
    metadata = {
        "selected": selected_ids,
        "fetched": [],
        "failed": [],
        "output": output_path,
        "shape": None,
    }
    data_list = []

    catalog = get_ifind_catalog()
    for indicator_id in selected_ids:
        meta = next((m for m in catalog if m["id"] == indicator_id), None)
        if meta is None:
            metadata["failed"].append(indicator_id)
            continue

        df = get_ifind_data(
            indicator_id,
            access_token,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
        )
        if df is None or df.empty:
            metadata["failed"].append(indicator_id)
            continue

        # Rename non-date columns to avoid collisions
        rename_map = {}
        for col in df.columns:
            if col != "指标名称":
                rename_map[col] = f"{meta['name']}_{col}"
        if rename_map:
            df = df.rename(columns=rename_map)

        data_list.append((df, "指标名称", meta["freq"]))
        metadata["fetched"].append(indicator_id)

    if not data_list:
        logger.error("No data fetched for selected ids: %s", selected_ids)
        return None, metadata

    from .cleaner import DataCleaner

    cleaner = DataCleaner(missing_value_threshold=missing_value_threshold)
    merged_df = cleaner.merge_dataframes(data_list)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    try:
        merged_df.to_csv(output_path, index=False)
        logger.info("Merged data saved to %s", output_path)
    except Exception as e:
        logger.error("Failed to save merged data to %s: %s", output_path, e)
        metadata["save_error"] = str(e)

    metadata["shape"] = merged_df.shape
    return merged_df, metadata


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
