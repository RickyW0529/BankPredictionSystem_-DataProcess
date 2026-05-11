# AkShare 宏观数据实时同步与勾选合并 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在前端集成 AkShare 中国宏观数据接口，用户可搜索、勾选、预览数据，一键下载合并为一张标准化月度大表。

**Architecture:** 新增 `akshare_sync.py` 模块负责数据获取与标准化缓存；扩展 Streamlit 前端增加"宏观数据浏览器"页面，支持关键词搜索、勾选、预览、合并导出；复用现有 `DataCleaner.merge_dataframes` 逻辑做最终合并。

**Tech Stack:** Python 3.9+, AkShare, Streamlit, pandas

---

## File Structure

| File | Responsibility |
|------|---------------|
| `bank_pipeline/akshare_sync.py` (create) | AkShare 宏观数据目录定义、数据获取、标准化缓存、合并 |
| `app.py` (modify) | 新增"宏观数据同步"页面：搜索、勾选、预览、运行合并 |
| `requirements.txt` (modify) | 追加 `akshare` |

---

## Task 1: 定义 AkShare 宏观数据目录

**Files:**
- Create: `bank_pipeline/akshare_sync.py`

**背景:** AkShare 有 85+ 个 `macro_china_*` 接口，数据格式各异（日期列名可能是"月份"、"季度"、"日期"、"TRADE_DATE"），频率也不同（日/月/季）。需要一张元数据表描述每个接口的名称、频率、可用指标列、日期列名。

- [ ] **Step 1: 定义 MACRO_CATALOG 常量**

在 `bank_pipeline/akshare_sync.py` 中写入：

```python
"""AkShare macro data synchronization module."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# 频率映射
FREQ_MAP = {
    "daily": "日度",
    "monthly": "月度",
    "quarterly": "季度",
    "yearly": "年度",
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
        "columns": [],  # 动态获取
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
        "id": "cpi_yearly",
        "name": "CPI年率",
        "freq": "yearly",
        "func": "macro_china_cpi_yearly",
        "date_col": "年份",
        "columns": [],
    },
    {
        "id": "ppi_yearly",
        "name": "PPI年率",
        "freq": "yearly",
        "func": "macro_china_ppi_yearly",
        "date_col": "年份",
        "columns": [],
    },
    {
        "id": "gdp_yearly",
        "name": "GDP年率",
        "freq": "yearly",
        "func": "macro_china_gdp_yearly",
        "date_col": "年份",
        "columns": [],
    },
    {
        "id": "m2_yearly",
        "name": "M2年率",
        "freq": "yearly",
        "func": "macro_china_m2_yearly",
        "date_col": "年份",
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
        "id": "vegetable",
        "name": "菜篮子指数",
        "freq": "weekly",
        "func": "macro_china_vegetable_basket",
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
        "id": "tourism",
        "name": "国际旅游外汇收入",
        "freq": "yearly",
        "func": "macro_china_international_tourism_fx",
        "date_col": "年份",
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
]
```

---

## Task 2: 实现数据获取与标准化

**Files:**
- Modify: `bank_pipeline/akshare_sync.py`

- [ ] **Step 1: 导入依赖并实现 `_fetch_data` 函数**

```python
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _fetch_data(func_name: str, date_col: str) -> Optional[pd.DataFrame]:
    """Call akshare function and return standardized DataFrame."""
    try:
        import akshare as ak
        func = getattr(ak, func_name)
        df = func()
        if df is None or df.empty:
            return None
        # Rename date column to standard name
        if date_col in df.columns:
            df = df.rename(columns={date_col: "指标名称"})
        else:
            logger.warning(f"Date column '{date_col}' not found in {func_name}, cols={list(df.columns)}")
            return None
        # Drop rows where date is NaT or NaN
        df["指标名称"] = pd.to_datetime(df["指标名称"], errors="coerce")
        df = df.dropna(subset=["指标名称"])
        df = df.sort_values("指标名称")
        return df
    except Exception as e:
        logger.error(f"Failed to fetch {func_name}: {e}")
        return None
```

- [ ] **Step 2: 实现 `get_macro_data` 函数**

```python
def get_macro_data(macro_id: str, use_cache: bool = True, cache_dir: str = "./.akshare_cache") -> Optional[pd.DataFrame]:
    """Fetch macro data by ID, with local CSV cache."""
    catalog_map = {item["id"]: item for item in MACRO_CATALOG}
    meta = catalog_map.get(macro_id)
    if not meta:
        raise ValueError(f"Unknown macro_id: {macro_id}")

    cache_path = Path(cache_dir) / f"{macro_id}.csv"
    if use_cache and cache_path.exists():
        try:
            df = pd.read_csv(cache_path)
            df["指标名称"] = pd.to_datetime(df["指标名称"], errors="coerce")
            logger.info(f"Loaded {macro_id} from cache ({len(df)} rows)")
            return df
        except Exception:
            pass

    df = _fetch_data(meta["func"], meta["date_col"])
    if df is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_path, index=False)
        logger.info(f"Fetched {macro_id} from akshare ({len(df)} rows)")
    return df
```

- [ ] **Step 3: 实现 `search_macros` 函数**

```python
def search_macros(keyword: str = "") -> List[Dict]:
    """Search macro catalog by keyword (Chinese or English)."""
    keyword = keyword.lower().strip()
    if not keyword:
        return MACRO_CATALOG
    results = []
    for item in MACRO_CATALOG:
        if keyword in item["name"].lower() or keyword in item["id"].lower():
            results.append(item)
    return results
```

- [ ] **Step 4: 实现 `merge_selected_macros` 函数**

```python
from .cleaner import DataCleaner


def merge_selected_macros(
    selected_ids: List[str],
    output_path: str = "./output/akshare_merged.csv",
    missing_value_threshold: float = 20.0,
) -> Tuple[Optional[pd.DataFrame], Dict]:
    """Fetch selected macro data, standardize, and merge into one monthly DataFrame."""
    data_list = []
    metadata = {"selected": selected_ids, "fetched": [], "failed": []}

    for macro_id in selected_ids:
        meta = next((m for m in MACRO_CATALOG if m["id"] == macro_id), None)
        if not meta:
            metadata["failed"].append(macro_id)
            continue

        df = get_macro_data(macro_id)
        if df is None or df.empty:
            metadata["failed"].append(macro_id)
            continue

        # If user specified columns, keep only those + date
        keep_cols = ["指标名称"]
        if meta.get("columns"):
            available = [c for c in meta["columns"] if c in df.columns]
            keep_cols.extend(available)
        else:
            # Keep all numeric columns
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            keep_cols.extend([c for c in numeric_cols if c != "指标名称"])

        df = df[[c for c in keep_cols if c in df.columns]]

        # Rename columns to avoid collision: prefix with macro_id
        rename_map = {}
        for c in df.columns:
            if c != "指标名称":
                rename_map[c] = f"{meta['name']}_{c}"
        df = df.rename(columns=rename_map)

        data_list.append((df, "指标名称", meta["freq"]))
        metadata["fetched"].append(macro_id)

    if not data_list:
        return None, metadata

    cleaner = DataCleaner(missing_value_threshold=missing_value_threshold)
    merged = cleaner.merge_dataframes(data_list)

    # Save
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    metadata["output"] = output_path
    metadata["shape"] = merged.shape

    return merged, metadata
```

---

## Task 3: 更新 requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: 追加 akshare**

```
akshare>=1.14.0
```

---

## Task 4: 扩展 Streamlit 前端

**Files:**
- Modify: `app.py`

- [ ] **Step 1: 在侧边栏添加页面导航**

在 `st.sidebar.title("⚙️ 参数配置")` 之前添加：

```python
# Page navigation
page = st.sidebar.radio("页面", ["本地数据处理", "AkShare 宏观数据同步"])
```

- [ ] **Step 2: 将现有内容放入 `if page == "本地数据处理"` 分支**

用 `if page == "本地数据处理":` 包裹当前所有主区域代码。

- [ ] **Step 3: 新增 `elif page == "AkShare 宏观数据同步"` 分支**

```python
elif page == "AkShare 宏观数据同步":
    st.title("📡 AkShare 宏观数据同步")
    st.markdown("从中国宏观数据库搜索、勾选、预览数据，一键合并导出")

    from bank_pipeline.akshare_sync import search_macros, get_macro_data, merge_selected_macros

    # Search
    st.header("🔍 搜索宏观数据")
    search_col, _ = st.columns([2, 1])
    with search_col:
        keyword = st.text_input("输入关键词搜索（如 CPI、GDP、PMI）", value="")

    results = search_macros(keyword)
    st.caption(f"找到 {len(results)} 个数据指标")

    # Selection table
    st.header("📋 数据列表")

    if "selected_macros" not in st.session_state:
        st.session_state.selected_macros = set()

    # Display as a grid of checkboxes
    cols_per_row = 2
    for i in range(0, len(results), cols_per_row):
        row_items = results[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, item in zip(cols, row_items):
            with col:
                checked = item["id"] in st.session_state.selected_macros
                freq_label = {"daily": "日度", "monthly": "月度", "quarterly": "季度", "yearly": "年度", "weekly": "周度"}.get(item["freq"], item["freq"])
                if st.checkbox(
                    f"**{item['name']}**  ({freq_label})",
                    value=checked,
                    key=f"chk_{item['id']}",
                ):
                    st.session_state.selected_macros.add(item["id"])
                else:
                    st.session_state.selected_macros.discard(item["id"])

    # Preview selected
    selected = list(st.session_state.selected_macros)
    if selected:
        st.header(f"✅ 已选择 {len(selected)} 个指标")

        preview_tabs = st.tabs([next((r["name"] for r in results if r["id"] == sid), sid) for sid in selected])
        for tab, sid in zip(preview_tabs, selected):
            with tab:
                with st.spinner("加载中..."):
                    df_preview = get_macro_data(sid)
                if df_preview is not None and not df_preview.empty:
                    st.write(f"数据量: {len(df_preview)} 行 × {len(df_preview.columns)} 列")
                    st.dataframe(df_preview.tail(10), use_container_width=True)
                else:
                    st.error("数据加载失败")
    else:
        st.info("请在上方勾选需要的数据指标")

    # Merge and export
    st.header("▶️ 合并导出")
    if selected and st.button("🚀 下载合并后的月度数据", type="primary", use_container_width=True):
        with st.spinner("正在获取并合并数据..."):
            merged_df, meta = merge_selected_macros(
                selected,
                output_path="./output/akshare_merged.csv",
                missing_value_threshold=60.0,
            )
        if merged_df is not None:
            st.success(f"✅ 合并完成！{meta['shape'][0]} 行 × {meta['shape'][1]} 列")
            with open(meta["output"], "rb") as f:
                st.download_button(
                    label="⬇️ 下载 CSV",
                    data=f,
                    file_name="akshare_merged.csv",
                    mime="text/csv",
                )
            st.dataframe(merged_df.tail(20), use_container_width=True)
        else:
            st.error("合并失败，请检查网络或选择的指标")

    st.markdown("---")
    st.caption("数据来源于 AkShare 开源财经数据接口")
```

---

## Task 5: 测试

- [ ] **Step 1: 安装依赖并运行**

```bash
pip install akshare streamlit
streamlit run app.py
```

- [ ] **Step 2: 验证搜索功能**

在 AkShare 页面搜索框输入 "CPI"，确认只显示 CPI 相关指标。

- [ ] **Step 3: 验证勾选与预览**

勾选 CPI、PPI、PMI，确认三个 tab 都能正确显示数据预览（底部 10 行）。

- [ ] **Step 4: 验证合并导出**

点击"下载合并后的月度数据"，确认：
- `output/akshare_merged.csv` 被创建
- 文件包含 Date 列 + 所有选中指标列
- 日度数据已被 resample 为月度均值
- 季度数据已被插值为月度

- [ ] **Step 5: 验证本地数据页面未被破坏**

切回"本地数据处理"页面，确认原有功能正常。

---

## Self-Review

**1. Spec coverage:**
- ✅ 使用 AkShare 插件进行宏观数据同步 — Task 2 Step 2 `get_macro_data`
- ✅ 用户实时选择加载哪些宏观数据 — Task 4 Step 3 checkbox grid
- ✅ 支持查询 — Task 2 Step 3 `search_macros` + Task 4 Step 1 text input
- ✅ 勾选宏观数据 — Task 4 Step 3 checkbox + session_state
- ✅ 合并到一张表 — Task 2 Step 4 `merge_selected_macros`

**2. Placeholder scan:** 无 TBD/TODO，所有代码已给出。

**3. Type consistency:** `merge_selected_macros` 返回 `Tuple[Optional[pd.DataFrame], Dict]`，与现有 `run_pipeline` 返回风格一致。
