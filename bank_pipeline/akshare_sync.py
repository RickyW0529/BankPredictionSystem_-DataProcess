"""AkShare macro data synchronization module."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .cleaner import DataCleaner
from .engineer import handle_spring_festival_split

# 频率映射
FREQ_MAP = {
    "daily": "日度",
    "monthly": "月度",
    "quarterly": "季度",
    "yearly": "年度",
    "weekly": "周度",
}

# 每个接口的元数据：名称、频率、日期列名、可用指标列（子列名前缀）
MACRO_CATALOG: List[Dict] = [
    {
        "id": "cpi",
        "name": "CPI（居民消费价格指数）",
        "freq": "monthly",
        "func": "macro_china_cpi",
        "date_col": "月份",
        "columns": ["全国-当月", "全国-同比增长", "全国-环比增长", "全国-累计"],
    },
    {
        "id": "ppi",
        "name": "PPI（工业生产者出厂价格指数）",
        "freq": "monthly",
        "func": "macro_china_ppi",
        "date_col": "月份",
        "columns": ["当月", "当月同比增长", "累计"],
    },
    {
        "id": "pmi",
        "name": "PMI（采购经理人指数）",
        "freq": "monthly",
        "func": "macro_china_pmi",
        "date_col": "月份",
        "columns": ["制造业-指数", "制造业-同比增长", "非制造业-指数", "非制造业-同比增长"],
    },
    {
        "id": "gdp",
        "name": "GDP（国内生产总值）",
        "freq": "quarterly",
        "func": "macro_china_gdp",
        "date_col": "季度",
        "columns": ["国内生产总值-绝对值", "国内生产总值-同比增长", "第一产业-绝对值", "第二产业-绝对值", "第三产业-绝对值"],
    },
    {
        "id": "m2",
        "name": "货币供应量（M0/M1/M2）",
        "freq": "monthly",
        "func": "macro_china_money_supply",
        "date_col": "月份",
        "columns": ["货币和准货币(M2)-数量(亿元)", "货币和准货币(M2)-同比增长", "货币(M1)-数量(亿元)", "货币(M1)-同比增长", "流通中的现金(M0)-数量(亿元)", "流通中的现金(M0)-同比增长"],
    },
    {
        "id": "lpr",
        "name": "LPR（贷款市场报价利率）",
        "freq": "daily",
        "func": "macro_china_lpr",
        "date_col": "TRADE_DATE",
        "columns": ["LPR1Y", "LPR5Y"],
    },
    {
        "id": "gzjz",
        "name": "工业增加值",
        "freq": "monthly",
        "func": "macro_china_gyzjz",
        "date_col": "月份",
        "columns": ["同比增长", "累计增长"],
    },
    {
        "id": "xfzxx",
        "name": "消费者信心指数",
        "freq": "monthly",
        "func": "macro_china_xfzxx",
        "date_col": "月份",
        "columns": ["消费者信心指数-指数值", "消费者信心指数-同比增长", "消费者信心指数-环比增长"],
    },
    {
        "id": "reserve_ratio",
        "name": "存款准备金率",
        "freq": "monthly",
        "func": "macro_china_reserve_requirement_ratio",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "shibor",
        "name": "SHIBOR",
        "freq": "daily",
        "func": "macro_china_shibor_all",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "fdi",
        "name": "外商直接投资（FDI）",
        "freq": "monthly",
        "func": "macro_china_fdi",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "exports",
        "name": "出口同比",
        "freq": "monthly",
        "func": "macro_china_exports_yoy",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "imports",
        "name": "进口同比",
        "freq": "monthly",
        "func": "macro_china_imports_yoy",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "trade_balance",
        "name": "贸易差额",
        "freq": "monthly",
        "func": "macro_china_trade_balance",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "industrial_production",
        "name": "工业生产指数同比",
        "freq": "monthly",
        "func": "macro_china_industrial_production_yoy",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "retail",
        "name": "社会消费品零售总额",
        "freq": "monthly",
        "func": "macro_china_consumer_goods_retail",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "foreign_exchange",
        "name": "外汇储备",
        "freq": "monthly",
        "func": "macro_china_fx_reserves_yearly",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "real_estate_index",
        "name": "房地产指数",
        "freq": "monthly",
        "func": "macro_china_real_estate",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "enterprise_boom",
        "name": "企业景气指数",
        "freq": "quarterly",
        "func": "macro_china_enterprise_boom_index",
        "date_col": "季度",
        "columns": [],
    },
    {
        "id": "construction",
        "name": "建筑业指数",
        "freq": "monthly",
        "func": "macro_china_construction_index",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "energy",
        "name": "能源指数",
        "freq": "monthly",
        "func": "macro_china_energy_index",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "commodity",
        "name": "大宗商品价格指数",
        "freq": "daily",
        "func": "macro_china_commodity_price_index",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "agricultural",
        "name": "农产品指数",
        "freq": "monthly",
        "func": "macro_china_agricultural_index",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "freight",
        "name": "货运指数",
        "freq": "monthly",
        "func": "macro_china_freight_index",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "passenger",
        "name": "客运指数",
        "freq": "monthly",
        "func": "macro_china_passenger_load_factor",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "postal",
        "name": "邮电业务",
        "freq": "monthly",
        "func": "macro_china_postal_telecommunicational",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "electricity",
        "name": "全社会用电量",
        "freq": "monthly",
        "func": "macro_china_society_electricity",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "insurance",
        "name": "保险业经营数据",
        "freq": "monthly",
        "func": "macro_china_insurance_income",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "stock_market",
        "name": "股票市场规模",
        "freq": "monthly",
        "func": "macro_china_stock_market_cap",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "rmb",
        "name": "人民币汇率",
        "freq": "daily",
        "func": "macro_china_rmb",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "gold",
        "name": "黄金储备",
        "freq": "monthly",
        "func": "macro_china_fx_gold",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "tax",
        "name": "全国税收收入",
        "freq": "monthly",
        "func": "macro_china_national_tax_receipts",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "bank_financing",
        "name": "银行理财产品",
        "freq": "monthly",
        "func": "macro_china_bank_financing",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "new_credit",
        "name": "新增信贷",
        "freq": "monthly",
        "func": "macro_china_new_financial_credit",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "central_bank",
        "name": "央行资产负债表",
        "freq": "monthly",
        "func": "macro_china_central_bank_balance",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "bond_public",
        "name": "国债发行",
        "freq": "monthly",
        "func": "macro_china_bond_public",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "swap_rate",
        "name": "利率互换",
        "freq": "daily",
        "func": "macro_china_swap_rate",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "margin_sh",
        "name": "上海融资融券",
        "freq": "daily",
        "func": "macro_china_market_margin_sh",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "margin_sz",
        "name": "深圳融资融券",
        "freq": "daily",
        "func": "macro_china_market_margin_sz",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "mobile",
        "name": "移动电话用户数",
        "freq": "monthly",
        "func": "macro_china_mobile_number",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "traffic",
        "name": "交通运输",
        "freq": "monthly",
        "func": "macro_china_society_traffic_volume",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "retail_price",
        "name": "商品零售价格指数",
        "freq": "monthly",
        "func": "macro_china_retail_price_index",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "non_man_pmi",
        "name": "非制造业PMI",
        "freq": "monthly",
        "func": "macro_china_non_man_pmi",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "cx_pmi",
        "name": "财新PMI",
        "freq": "monthly",
        "func": "macro_china_cx_pmi_yearly",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "urban_unemployment",
        "name": "城镇失业率",
        "freq": "monthly",
        "func": "macro_china_urban_unemployment",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "lpi",
        "name": "物流景气指数",
        "freq": "monthly",
        "func": "macro_china_lpi_index",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "bdti",
        "name": "波罗的海原油指数",
        "freq": "daily",
        "func": "macro_china_bdti_index",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "bsi",
        "name": "波罗的海超灵便型指数",
        "freq": "daily",
        "func": "macro_china_bsi_index",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "czsr",
        "name": "财政收入",
        "freq": "monthly",
        "func": "macro_china_czsr",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "gdzctz",
        "name": "固定资产投资",
        "freq": "monthly",
        "func": "macro_china_gdzctz",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "hgjck",
        "name": "海关进出口",
        "freq": "monthly",
        "func": "macro_china_hgjck",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "qyspjg",
        "name": "企业商品价格",
        "freq": "monthly",
        "func": "macro_china_qyspjg",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "whxd",
        "name": "外汇信贷",
        "freq": "monthly",
        "func": "macro_china_whxd",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "wbck",
        "name": "外币存款",
        "freq": "monthly",
        "func": "macro_china_wbck",
        "date_col": "月份",
        "columns": [],
    },
    {
        "id": "agricultural_product",
        "name": "农产品价格",
        "freq": "daily",
        "func": "macro_china_agricultural_product",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "au_report",
        "name": "贵金属报告",
        "freq": "daily",
        "func": "macro_china_au_report",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "construction_price_index",
        "name": "建筑业价格指数",
        "freq": "daily",
        "func": "macro_china_construction_price_index",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "cpi_monthly",
        "name": "CPI月度报告（商品维度）",
        "freq": "monthly",
        "func": "macro_china_cpi_monthly",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "cx_services_pmi",
        "name": "财新服务业PMI",
        "freq": "monthly",
        "func": "macro_china_cx_services_pmi_yearly",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "daily_energy",
        "name": "沿海六大电煤炭数据",
        "freq": "daily",
        "func": "macro_china_daily_energy",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "foreign_exchange_gold",
        "name": "外汇储备与黄金",
        "freq": "monthly",
        "func": "macro_china_foreign_exchange_gold",
        "date_col": "统计时间",
        "columns": [],
    },
    {
        "id": "insurance_business",
        "name": "保险业经营数据",
        "freq": "monthly",
        "func": "macro_china_insurance",
        "date_col": "统计时间",
        "columns": [],
    },
    {
        "id": "new_house_price",
        "name": "新建商品住宅价格指数",
        "freq": "monthly",
        "func": "macro_china_new_house_price",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "supply_of_money",
        "name": "货币供应量（另一口径）",
        "freq": "monthly",
        "func": "macro_china_supply_of_money",
        "date_col": "统计时间",
        "columns": [],
    },
    {
        "id": "yw_electronic",
        "name": "义乌电子指数",
        "freq": "daily",
        "func": "macro_china_yw_electronic_index",
        "date_col": "日期",
        "columns": [],
    },
    {
        "id": "shrzgm",
        "name": "社会融资规模增量",
        "freq": "monthly",
        "func": "macro_china_shrzgm",
        "date_col": "月份",
        "columns": ["社会融资规模增量", "其中-人民币贷款", "其中-委托贷款", "其中-信托贷款", "其中-未贴现银行承兑汇票", "其中-企业债券", "其中-非金融企业境内股票融资"],
    },
    {
        "id": "vegetable_basket",
        "name": "菜篮子产品批发价格指数",
        "freq": "daily",
        "func": "macro_china_vegetable_basket",
        "date_col": "日期",
        "columns": ["最新值", "涨跌幅", "近3月涨跌幅", "近6月涨跌幅", "近1年涨跌幅", "近2年涨跌幅", "近3年涨跌幅"],
    },
]

logger = logging.getLogger(__name__)


def _parse_chinese_date(val):
    """Parse Chinese date strings like '2026年04月份', '2026年第1季度', '2026年'."""
    import re

    s = str(val).strip()
    # 201501 -> 2015-01-01
    m = re.match(r"^(\d{4})(\d{2})$", s)
    if m:
        return pd.Timestamp(f"{m.group(1)}-{m.group(2)}-01")
    # 2026年04月份 -> 2026-04-01
    m = re.match(r"(\d{4})年(\d{2})月份", s)
    if m:
        return pd.Timestamp(f"{m.group(1)}-{m.group(2)}-01")
    # 2026年第1季度 -> 2026-01-01
    m = re.match(r"(\d{4})年第(\d)季度", s)
    if m:
        q = int(m.group(2))
        month = (q - 1) * 3 + 1
        return pd.Timestamp(f"{m.group(1)}-{month:02d}-01")
    # 2026年 -> 2026-01-01
    m = re.match(r"(\d{4})年$", s)
    if m:
        return pd.Timestamp(f"{m.group(1)}-01-01")
    # fallback to pandas parser
    return pd.to_datetime(s, errors="coerce")


def _fetch_data(func_name: str, date_col: str) -> Optional[pd.DataFrame]:
    """Fetch macro data from akshare lazily."""
    try:
        import akshare as ak
    except ImportError:
        logger.error("akshare is not installed")
        return None

    try:
        func = getattr(ak, func_name)
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
    df["指标名称"] = df["指标名称"].apply(_parse_chinese_date)
    df = df.dropna(subset=["指标名称"])
    df = df.sort_values(by="指标名称", ascending=True)
    return df


def get_macro_data(
    macro_id: str,
    use_cache: bool = True,
    cache_dir: str = "./.akshare_cache",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """Get macro data by id, with optional caching."""
    meta = next((item for item in MACRO_CATALOG if item["id"] == macro_id), None)
    if meta is None:
        logger.warning("macro_id %s not found in catalog", macro_id)
        return None

    cache_path = Path(cache_dir) / f"{macro_id}.csv"
    df = None
    if use_cache and cache_path.exists():
        logger.info("Cache hit for %s, reading from %s", macro_id, cache_path)
        try:
            df = pd.read_csv(cache_path)
            df["指标名称"] = pd.to_datetime(df["指标名称"], errors="coerce")
            df = df.dropna(subset=["指标名称"])
            df = df.sort_values(by="指标名称", ascending=True)
        except Exception as e:
            logger.warning("Failed to read cache for %s: %s", macro_id, e)
            df = None

    if df is None:
        logger.info("Fetching %s from akshare...", macro_id)
        df = _fetch_data(meta["func"], meta["date_col"])
        if df is not None and use_cache:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                df.to_csv(cache_path, index=False)
                logger.info("Saved cache for %s to %s", macro_id, cache_path)
            except Exception as e:
                logger.warning("Failed to save cache for %s: %s", macro_id, e)

    if df is None or df.empty:
        return None

    # Apply date range filter (now applies to both cached and fresh data)
    if start_date:
        start_dt = pd.to_datetime(start_date)
        df = df[df["指标名称"] >= start_dt]
    if end_date:
        end_dt = pd.to_datetime(end_date)
        df = df[df["指标名称"] <= end_dt]

    return df.reset_index(drop=True)


def search_macros(keyword: str = "") -> List[Dict]:
    """Search MACRO_CATALOG by keyword (case-insensitive)."""
    keyword = keyword.strip().lower()
    if not keyword:
        return list(MACRO_CATALOG)
    return [
        item
        for item in MACRO_CATALOG
        if keyword in item.get("id", "").lower()
        or keyword in item.get("name", "").lower()
    ]


def merge_selected_macros(
    selected_ids: List[str],
    output_path: str = "./output/akshare_merged.csv",
    missing_value_threshold: float = 20.0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[Optional[pd.DataFrame], Dict]:
    """Fetch and merge selected macro indicators."""
    metadata = {
        "selected": selected_ids,
        "fetched": [],
        "failed": [],
        "output": output_path,
        "shape": None,
    }

    data_list: List[Tuple[pd.DataFrame, str, str]] = []

    for macro_id in selected_ids:
        meta = next(
            (item for item in MACRO_CATALOG if item["id"] == macro_id), None
        )
        if meta is None:
            logger.warning("Skipping unknown macro_id: %s", macro_id)
            metadata["failed"].append(macro_id)
            continue

        df = get_macro_data(macro_id, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            metadata["failed"].append(macro_id)
            continue

        # Keep only desired columns
        if meta.get("columns"):
            keep_cols = [c for c in ["指标名称"] + meta["columns"] if c in df.columns]
            if len(keep_cols) <= 1:
                logger.warning(
                    "No specified columns found for %s, keeping all numeric", macro_id
                )
                numeric_df = df.select_dtypes(include=["number"])
                df = pd.concat([df[["指标名称"]], numeric_df], axis=1)
            else:
                df = df[keep_cols]
        else:
            numeric_df = df.select_dtypes(include=["number"])
            df = pd.concat([df[["指标名称"]], numeric_df], axis=1)

        # Rename non-date columns to avoid collisions
        rename_map = {}
        for col in df.columns:
            if col != "指标名称":
                rename_map[col] = f"{meta['name']}_{col}"
        if rename_map:
            df = df.rename(columns=rename_map)

        # Apply spring festival split for daily/monthly data
        if meta["freq"] in ("daily", "monthly"):
            df = df.set_index("指标名称")
            df = handle_spring_festival_split(df)
            df = df.reset_index()

        data_list.append((df, "指标名称", meta["freq"]))
        metadata["fetched"].append(macro_id)

    if not data_list:
        logger.error("No data fetched for selected ids: %s", selected_ids)
        return None, metadata

    cleaner = DataCleaner(missing_value_threshold=missing_value_threshold)
    merged_df = cleaner.merge_dataframes(data_list)

    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    merged_df.to_csv(output_path_obj, index=False)
    logger.info("Merged data saved to %s", output_path_obj)

    metadata["shape"] = merged_df.shape
    return merged_df, metadata
