"""iFinD HTTP API client for macro data."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

from . import config as _config

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://ft.10jqka.com.cn/api/v1"

FREQ_MAP = {"daily": "日度", "monthly": "月度", "quarterly": "季度", "yearly": "年度"}


def _load_default_catalog() -> List[Dict]:
    """Load the built-in indicator catalog from JSON."""
    if not _config.IFIND_DEFAULT_CATALOG_PATH.exists():
        logger.warning("Default iFinD catalog not found at %s", _config.IFIND_DEFAULT_CATALOG_PATH)
        return []
    try:
        with open(_config.IFIND_DEFAULT_CATALOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        logger.warning("Default catalog %s is not a list, ignoring", _config.IFIND_DEFAULT_CATALOG_PATH)
        return []
    except Exception as e:
        logger.warning("Failed to load default iFinD catalog from %s: %s", _config.IFIND_DEFAULT_CATALOG_PATH, e)
        return []


# Default catalog of common macro indicators for iFinD.
# Users can override or extend these via `ifind_catalog.json`.
IFIND_CATALOG: List[Dict] = _load_default_catalog()


def _load_custom_catalog(path: Optional[str] = None) -> List[Dict]:
    """Load user-defined indicator catalog from JSON.

    JSON format: a list of dicts with keys `id`, `name`, `freq`, `indicator`.
    """
    p = Path(path) if path else Path(_config.IFIND_CUSTOM_CATALOG_PATH)
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
    """Return current effective catalog (user config if exists, else defaults)."""
    custom = _load_custom_catalog()
    if custom:
        return custom
    return list(IFIND_CATALOG)


def save_ifind_catalog(catalog: List[Dict]) -> None:
    """Save full indicator catalog to JSON."""
    p = Path(_config.IFIND_CUSTOM_CATALOG_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)


def reset_ifind_catalog() -> None:
    """Remove user catalog file to restore defaults."""
    p = Path(_config.IFIND_CUSTOM_CATALOG_PATH)
    if p.exists():
        p.unlink()


def load_ifind_token() -> Optional[str]:
    """Load saved access token from config file."""
    if not _config.IFIND_TOKEN_PATH.exists():
        return None
    try:
        with open(_config.IFIND_TOKEN_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("access_token")
    except Exception:
        return None


def save_ifind_token(token: str) -> None:
    """Save access token to config file."""
    config = {}
    if _config.IFIND_TOKEN_PATH.exists():
        try:
            with open(_config.IFIND_TOKEN_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass
    config["access_token"] = token
    with open(_config.IFIND_TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def clear_ifind_token() -> None:
    """Remove saved access token."""
    if not _config.IFIND_TOKEN_PATH.exists():
        return
    try:
        with open(_config.IFIND_TOKEN_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        config.pop("access_token", None)
        with open(_config.IFIND_TOKEN_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


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
    use_cache: bool = True,
    cache_dir: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """Fetch iFinD macro data by catalog ID, with optional caching."""
    catalog = get_ifind_catalog()
    meta = next((item for item in catalog if item["id"] == indicator_id), None)
    if meta is None:
        logger.warning("indicator_id %s not found in iFinD catalog", indicator_id)
        return None

    indicator = meta["indicator"]
    cache_root = Path(cache_dir) if cache_dir else _config.IFIND_CACHE_DIR
    cache_path = cache_root / f"{indicator_id}_{indicator}.csv"

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
        df = client.fetch_edb(
            indicator,
            start_date=start_date,
            end_date=end_date,
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

        data_list.append((df, "指标名称", meta.get("freq", "monthly")))
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
                msg = data.get("message", "unknown")
                logger.warning("iFinD API error: %s", msg)
                return None
            return data
        except requests.exceptions.RequestException as e:
            logger.error("iFinD HTTP request failed: %s", e)
            return None

    def fetch_edb(
        self,
        indicators: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """Fetch iFinD EDB (macroeconomic) data for a given indicator.

        Parameters
        ----------
        indicators: str
            iFinD EDB indicator code (e.g. 'M0000001').
        start_date, end_date: str, optional
            Date range in YYYY-MM-DD format.

        Returns
        -------
        pd.DataFrame or None
        """
        payload = {
            "indicators": indicators,
        }
        if start_date:
            payload["startdate"] = start_date
        if end_date:
            payload["enddate"] = end_date

        result = self._post("edb_service", payload)
        if result is None:
            raise RuntimeError(f"iFinD API request failed for indicator {indicators}")
        if "data" not in result:
            logger.warning("iFinD API response for %s: %s", indicators, json.dumps(result, ensure_ascii=False))
            raise RuntimeError(f"iFinD API response missing 'data' field for indicator {indicators}. Response keys: {list(result.keys())}")

        data = result["data"]
        table = data.get("table", [])
        header = data.get("header", [])

        if not table or not header:
            raise RuntimeError(f"iFinD returned empty data for indicator {indicators}")

        df = pd.DataFrame(table, columns=header)

        # Detect date column (usually the first column) and parse
        date_col = header[0] if header else None
        if date_col is None:
            logger.warning("No header found for indicator %s", indicators)
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
        try:
            result = self._post("edb_service", {"indicators": "M0000001", "startdate": "20240101", "enddate": "20240101"})
            return result is not None
        except Exception:
            return False


# Convenience module-level functions for Streamlit integration


def get_ifind_client(access_token: str) -> IFindClient:
    return IFindClient(access_token)


def fetch_ifind_indicator(
    indicator: str,
    access_token: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    client = get_ifind_client(access_token)
    return client.fetch_edb(indicator, start_date, end_date)
