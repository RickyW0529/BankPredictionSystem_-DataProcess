"""Tushare macro data synchronization module."""

import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .cleaner import DataCleaner
from .engineer import handle_spring_festival_split

FREQ_MAP = {"daily": "日度", "monthly": "月度", "quarterly": "季度"}

TUSHARE_CATALOG: List[Dict] = [
    {"id": "cpi", "name": "CPI（居民消费价格指数）", "freq": "monthly", "func": "cn_cpi", "date_col": "month", "columns": ["nt_val", "nt_yoy", "nt_mom", "nt_accu"]},
    {"id": "ppi", "name": "PPI（工业生产者出厂价格指数）", "freq": "monthly", "func": "cn_ppi", "date_col": "month", "columns": ["ppi", "ppi_yoy", "ppi_mom", "ppi_accu"]},
    {"id": "gdp", "name": "GDP（国内生产总值）", "freq": "quarterly", "func": "cn_gdp", "date_col": "quarter", "columns": ["gdp", "gdp_yoy", "pi", "si", "ti"]},
    {"id": "m2", "name": "货币供应量（M0/M1/M2）", "freq": "monthly", "func": "cn_m", "date_col": "month", "columns": ["m0", "m0_yoy", "m1", "m1_yoy", "m2", "m2_yoy"]},
    {"id": "industrial", "name": "工业增加值", "freq": "monthly", "func": "cn_industrial", "date_col": "month", "columns": ["industrial_yoy", "industrial_accu"]},
    {"id": "pmi", "name": "PMI（采购经理人指数）", "freq": "monthly", "func": "cn_pmi", "date_col": "month", "columns": ["pmi", "pmi_yoy"]},
    {"id": "retail", "name": "社会消费品零售总额", "freq": "monthly", "func": "cn_sf", "date_col": "month", "columns": ["retail_yoy", "retail_accu"]},
    {"id": "fdi", "name": "外商直接投资（FDI）", "freq": "monthly", "func": "cn_fdi", "date_col": "month", "columns": ["fdi_yoy"]},
    {"id": "export", "name": "出口金额", "freq": "monthly", "func": "cn_export", "date_col": "month", "columns": ["export_yoy", "export_accu"]},
    {"id": "import", "name": "进口金额", "freq": "monthly", "func": "cn_import", "date_col": "month", "columns": ["import_yoy", "import_accu"]},
    {"id": "consume", "name": "居民收入与消费", "freq": "monthly", "func": "cn_consume", "date_col": "month", "columns": ["income_yoy", "consume_yoy"]},
    {"id": "shibor", "name": "SHIBOR", "freq": "daily", "func": "shibor", "date_col": "date", "columns": ["on", "1w", "1m", "3m", "6m", "9m", "1y"]},
    {"id": "money_supply", "name": "货币供应量（另一口径）", "freq": "monthly", "func": "money_supply", "date_col": "month", "columns": ["m2", "m2_yoy", "m1", "m1_yoy"]},
    {"id": "fx_daily", "name": "人民币汇率", "freq": "daily", "func": "fx_daily", "date_col": "trade_date", "columns": ["bid_close"]},
    {"id": "house_price", "name": "房价指数", "freq": "monthly", "func": "cn_ppr", "date_col": "month", "columns": ["price_yoy", "price_mom"]},
]

logger = logging.getLogger(__name__)


def _parse_tushare_date(val, fmt: str = "month") -> pd.Timestamp:
    s = str(val).strip()
    if fmt in ("month", "quarter"):
        if len(s) == 6 and s.isdigit():
            return pd.Timestamp(f"{s[:4]}-{s[4:6]}-01")
        if len(s) == 6 and s[4] == 'Q':
            year = s[:4]
            q = int(s[5])
            month = (q - 1) * 3 + 1
            return pd.Timestamp(f"{year}-{month:02d}-01")
    if fmt in ("date", "trade_date"):
        if len(s) == 8 and s.isdigit():
            return pd.Timestamp(f"{s[:4]}-{s[4:6]}-{s[6:8]}")
    return pd.to_datetime(s, errors="coerce")


def get_tushare_pro_api(token: str, api_url: str = "https://api.tushare.pro") -> Optional[object]:
    try:
        import tushare as ts
    except ImportError:
        logger.error("tushare is not installed")
        return None
    try:
        pro = ts.pro_api(token)
        pro._DataApi__http_url = api_url
        return pro
    except Exception as e:
        logger.warning("Failed to initialize tushare pro api: %s", e)
        return None


def test_api_connection(token: str, api_url: str = "https://api.tushare.pro") -> Tuple[bool, str]:
    pro = get_tushare_pro_api(token, api_url)
    if pro is None:
        return False, "tushare 未安装"
    try:
        df = pro.query("stock_basic", limit=1)
        if df is not None and not df.empty:
            return True, "连接成功"
        return False, "API 返回空数据"
    except Exception as e:
        return False, f"API 连接失败: {e}"


def _fetch_tushare_data(pro, func_name: str, date_col: str) -> Optional[pd.DataFrame]:
    try:
        func = getattr(pro, func_name)
        if func_name == "shibor":
            df = func(start_date="20100101")
        elif func_name == "fx_daily":
            df = func(ts_code="USDCNH.FXCM", start_date="20100101")
        else:
            df = func()
    except Exception as e:
        logger.warning("Failed to fetch data via %s: %s", func_name, e)
        return None

    if df is None or df.empty:
        logger.warning("Empty response from %s", func_name)
        return None

    if date_col not in df.columns:
        logger.warning("Date column %s not found in response from %s", date_col, func_name)
        return None

    df = df.rename(columns={date_col: "指标名称"})
    df["指标名称"] = df["指标名称"].apply(lambda x: _parse_tushare_date(x, date_col))
    df = df.dropna(subset=["指标名称"])
    df = df.sort_values(by="指标名称", ascending=True)
    return df


def get_tushare_data(
    indicator_id: str,
    token: str,
    api_url: str = "https://api.tushare.pro",
    use_cache: bool = True,
    cache_dir: str = "./.tushare_cache",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    meta = next((item for item in TUSHARE_CATALOG if item["id"] == indicator_id), None)
    if meta is None:
        logger.warning("indicator_id %s not found in catalog", indicator_id)
        return None

    token_hash = hashlib.md5(token.encode()).hexdigest()[:8]
    cache_path = Path(cache_dir) / f"{indicator_id}_{token_hash}.csv"

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
        pro = get_tushare_pro_api(token, api_url)
        if pro is None:
            return None
        logger.info("Fetching %s from tushare...", indicator_id)
        df = _fetch_tushare_data(pro, meta["func"], meta["date_col"])
        if df is not None and use_cache:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                df.to_csv(cache_path, index=False)
                logger.info("Saved cache for %s to %s", indicator_id, cache_path)
            except Exception as e:
                logger.warning("Failed to save cache for %s: %s", indicator_id, e)

    if df is None or df.empty:
        return None

    if start_date:
        start_dt = pd.to_datetime(start_date)
        df = df[df["指标名称"] >= start_dt]
    if end_date:
        end_dt = pd.to_datetime(end_date)
        df = df[df["指标名称"] <= end_dt]

    return df.reset_index(drop=True)


def search_tushare(keyword: str = "") -> List[Dict]:
    keyword = keyword.strip().lower()
    if not keyword:
        return list(TUSHARE_CATALOG)
    return [
        item for item in TUSHARE_CATALOG
        if keyword in item.get("id", "").lower() or keyword in item.get("name", "").lower()
    ]


def merge_tushare_selected(
    selected_ids: List[str],
    token: str,
    api_url: str = "https://api.tushare.pro",
    output_path: str = "./output/tushare_merged.csv",
    missing_value_threshold: float = 20.0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[Optional[pd.DataFrame], Dict]:
    metadata = {"selected": selected_ids, "fetched": [], "failed": [], "output": output_path, "shape": None}
    data_list = []

    for indicator_id in selected_ids:
        meta = next((m for m in TUSHARE_CATALOG if m["id"] == indicator_id), None)
        if meta is None:
            metadata["failed"].append(indicator_id)
            continue

        df = get_tushare_data(indicator_id, token=token, api_url=api_url, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            metadata["failed"].append(indicator_id)
            continue

        keep_cols = ["指标名称"]
        if meta.get("columns"):
            available = [c for c in meta["columns"] if c in df.columns]
            if not available:
                logger.warning(
                    "No specified columns found for %s, keeping all numeric", indicator_id
                )
                numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
                keep_cols.extend([c for c in numeric_cols if c != "指标名称"])
            else:
                keep_cols.extend(available)
        else:
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            keep_cols.extend([c for c in numeric_cols if c != "指标名称"])

        df = df[[c for c in keep_cols if c in df.columns]]

        rename_map = {}
        for c in df.columns:
            if c != "指标名称":
                rename_map[c] = f"{meta['name']}_{c}"
        if rename_map:
            df = df.rename(columns=rename_map)

        if meta["freq"] in ("daily", "monthly"):
            df = df.set_index("指标名称")
            df = handle_spring_festival_split(df)
            df = df.reset_index()

        data_list.append((df, "指标名称", meta["freq"]))
        metadata["fetched"].append(indicator_id)

    if not data_list:
        logger.error("No data fetched for selected ids: %s", selected_ids)
        return None, metadata

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
