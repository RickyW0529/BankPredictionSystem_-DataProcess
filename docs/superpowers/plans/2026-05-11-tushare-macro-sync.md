# Tushare 宏观数据补充模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加第三条数据来源——Tushare Pro 宏观数据，提供独立的搜索、勾选、预览、合并导出功能。API 无效时不影响现有本地数据处理和 AkShare 宏观数据同步两条线路。

**Architecture:** 新增独立模块 `bank_pipeline/tushare_sync.py`，公共接口与 `akshare_sync.py` 保持对称（catalog/get/search/merge）。`app.py` 在侧边栏增加第三个页面导航选项。复用现有 `DataCleaner` 和 `handle_spring_festival_split` 处理日度/季度 → 月度转换。

**Tech Stack:** Python 3.9+, tushare, pandas, streamlit

---

## File Structure

| File | Responsibility |
|------|---------------|
| `bank_pipeline/tushare_sync.py` (create) | Tushare 核心模块：catalog、API 初始化、日期解析、数据获取、缓存、搜索、合并 |
| `tests/test_tushare_sync.py` (create) | 单元测试：API 连接、数据获取、日期过滤、合并、搜索 |
| `app.py` (modify) | 增加第三个页面导航 "Tushare 宏观数据补充"，包含 API 配置区、指标搜索勾选、预览、合并导出 |
| `requirements.txt` (modify) | 增加 `tushare` 依赖 |

---

## Task 1: Create `bank_pipeline/tushare_sync.py` core module

**Files:**
- Create: `bank_pipeline/tushare_sync.py`

- [ ] **Step 1: Write TUSHARE_CATALOG and imports**

```python
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
    {
        "id": "cpi",
        "name": "CPI（居民消费价格指数）",
        "freq": "monthly",
        "func": "cn_cpi",
        "date_col": "month",
        "columns": ["nt_val", "nt_yoy", "nt_mom", "nt_accu"],
    },
    {
        "id": "ppi",
        "name": "PPI（工业生产者出厂价格指数）",
        "freq": "monthly",
        "func": "cn_ppi",
        "date_col": "month",
        "columns": ["ppi", "ppi_yoy", "ppi_mom", "ppi_accu"],
    },
    {
        "id": "gdp",
        "name": "GDP（国内生产总值）",
        "freq": "quarterly",
        "func": "cn_gdp",
        "date_col": "quarter",
        "columns": ["gdp", "gdp_yoy", "pi", "si", "ti"],
    },
    {
        "id": "m2",
        "name": "货币供应量（M0/M1/M2）",
        "freq": "monthly",
        "func": "cn_m",
        "date_col": "month",
        "columns": ["m0", "m0_yoy", "m1", "m1_yoy", "m2", "m2_yoy"],
    },
    {
        "id": "industrial",
        "name": "工业增加值",
        "freq": "monthly",
        "func": "cn_industrial",
        "date_col": "month",
        "columns": ["industrial_yoy", "industrial_accu"],
    },
    {
        "id": "pmi",
        "name": "PMI（采购经理人指数）",
        "freq": "monthly",
        "func": "cn_pmi",
        "date_col": "month",
        "columns": ["pmi", "pmi_yoy"],
    },
    {
        "id": "retail",
        "name": "社会消费品零售总额",
        "freq": "monthly",
        "func": "cn_sf",
        "date_col": "month",
        "columns": ["retail_yoy", "retail_accu"],
    },
    {
        "id": "fdi",
        "name": "外商直接投资（FDI）",
        "freq": "monthly",
        "func": "cn_fdi",
        "date_col": "month",
        "columns": ["fdi_yoy"],
    },
    {
        "id": "export",
        "name": "出口金额",
        "freq": "monthly",
        "func": "cn_export",
        "date_col": "month",
        "columns": ["export_yoy", "export_accu"],
    },
    {
        "id": "import",
        "name": "进口金额",
        "freq": "monthly",
        "func": "cn_import",
        "date_col": "month",
        "columns": ["import_yoy", "import_accu"],
    },
    {
        "id": "consume",
        "name": "居民收入与消费",
        "freq": "monthly",
        "func": "cn_consume",
        "date_col": "month",
        "columns": ["income_yoy", "consume_yoy"],
    },
    {
        "id": "shibor",
        "name": "SHIBOR",
        "freq": "daily",
        "func": "shibor",
        "date_col": "date",
        "columns": ["on", "1w", "1m", "3m", "6m", "9m", "1y"],
    },
    {
        "id": "money_supply",
        "name": "货币供应量（另一口径）",
        "freq": "monthly",
        "func": "money_supply",
        "date_col": "month",
        "columns": ["m2", "m2_yoy", "m1", "m1_yoy"],
    },
    {
        "id": "fx_daily",
        "name": "人民币汇率",
        "freq": "daily",
        "func": "fx_daily",
        "date_col": "trade_date",
        "columns": ["bid_close"],
    },
    {
        "id": "house_price",
        "name": "房价指数",
        "freq": "monthly",
        "func": "cn_ppr",
        "date_col": "month",
        "columns": ["price_yoy", "price_mom"],
    },
]

logger = logging.getLogger(__name__)
```

- [ ] **Step 2: Write `_parse_tushare_date` and `get_tushare_pro_api`**

```python
def _parse_tushare_date(val, fmt: str = "month") -> pd.Timestamp:
    """Parse Tushare date strings.
    month/quarter -> YYYYMM / YYYYQQ
    date/trade_date -> YYYYMMDD
    """
    s = str(val).strip()
    if fmt in ("month", "quarter"):
        # YYYYMM or YYYYQQ
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
    # fallback
    return pd.to_datetime(s, errors="coerce")


def get_tushare_pro_api(token: str, api_url: str = "http://tsy.xiaodefa.cn") -> Optional[object]:
    """Initialize Tushare Pro API with token and custom URL."""
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


def test_api_connection(token: str, api_url: str = "http://tsy.xiaodefa.cn") -> Tuple[bool, str]:
    """Test if token is valid. Returns (is_valid, message)."""
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
```

- [ ] **Step 3: Write `_fetch_tushare_data` and `get_tushare_data`**

```python
def _fetch_tushare_data(pro, func_name: str, date_col: str) -> Optional[pd.DataFrame]:
    """Fetch macro data from tushare."""
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
    api_url: str = "http://tsy.xiaodefa.cn",
    use_cache: bool = True,
    cache_dir: str = "./.tushare_cache",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """Fetch tushare macro data by id, with optional caching and date filtering."""
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
```

- [ ] **Step 4: Write `search_tushare` and `merge_tushare_selected`**

```python
def search_tushare(keyword: str = "") -> List[Dict]:
    """Search TUSHARE_CATALOG by keyword (case-insensitive)."""
    keyword = keyword.strip().lower()
    if not keyword:
        return list(TUSHARE_CATALOG)
    return [
        item
        for item in TUSHARE_CATALOG
        if keyword in item.get("id", "").lower()
        or keyword in item.get("name", "").lower()
    ]


def merge_tushare_selected(
    selected_ids: List[str],
    token: str,
    api_url: str = "http://tsy.xiaodefa.cn",
    output_path: str = "./output/tushare_merged.csv",
    missing_value_threshold: float = 20.0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[Optional[pd.DataFrame], Dict]:
    """Fetch and merge selected Tushare indicators."""
    metadata = {
        "selected": selected_ids,
        "fetched": [],
        "failed": [],
        "output": output_path,
        "shape": None,
    }

    data_list = []

    for indicator_id in selected_ids:
        meta = next((m for m in TUSHARE_CATALOG if m["id"] == indicator_id), None)
        if meta is None:
            metadata["failed"].append(indicator_id)
            continue

        df = get_tushare_data(
            indicator_id,
            token=token,
            api_url=api_url,
            start_date=start_date,
            end_date=end_date,
        )
        if df is None or df.empty:
            metadata["failed"].append(indicator_id)
            continue

        keep_cols = ["指标名称"]
        if meta.get("columns"):
            available = [c for c in meta["columns"] if c in df.columns]
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
    merged_df.to_csv(output_path, index=False)
    logger.info("Merged data saved to %s", output_path)

    metadata["shape"] = merged_df.shape
    return merged_df, metadata
```

- [ ] **Step 5: Verify syntax**

Run: `python -c "from bank_pipeline.tushare_sync import TUSHARE_CATALOG, search_tushare, test_api_connection; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add bank_pipeline/tushare_sync.py
git commit -m "feat: add tushare_sync.py core module with 15 macro indicators"
```

---

## Task 2: Create `tests/test_tushare_sync.py`

**Files:**
- Create: `tests/test_tushare_sync.py`
- Modify: `requirements.txt` (add `tushare` if not present)

- [ ] **Step 1: Write the test file**

```python
"""Tests for bank_pipeline.tushare_sync module."""

import pytest
from bank_pipeline.tushare_sync import (
    TUSHARE_CATALOG,
    search_tushare,
    test_api_connection,
    get_tushare_data,
    merge_tushare_selected,
)

VALID_TOKEN = "5d61f00d3f0d18bfbd2b3cb713ebf9c753aa6d4e8ab8e7be99369fa6"
API_URL = "http://tsy.xiaodefa.cn"


def test_tushare_catalog_frequencies():
    """All indicators must have daily/monthly/quarterly frequency only."""
    valid_freqs = {"daily", "monthly", "quarterly"}
    for item in TUSHARE_CATALOG:
        assert item["freq"] in valid_freqs, f"{item['id']} has invalid freq {item['freq']}"


def test_tushare_catalog_total():
    """Verify total number of indicators."""
    assert len(TUSHARE_CATALOG) == 15


def test_search_tushare_empty_keyword():
    """Empty keyword returns all indicators."""
    results = search_tushare("")
    assert len(results) == len(TUSHARE_CATALOG)


def test_search_tushare_by_name():
    """Search by Chinese name."""
    results = search_tushare("CPI")
    assert len(results) >= 1
    assert any("cpi" in r["id"] for r in results)


def test_search_tushare_by_id():
    """Search by id."""
    results = search_tushare("gdp")
    assert len(results) == 1
    assert results[0]["id"] == "gdp"


def test_api_connection_invalid():
    """Test connection with fake token returns False."""
    is_valid, msg = test_api_connection("fake_token_123", API_URL)
    assert is_valid is False
    assert "失败" in msg or "invalid" in msg.lower()


@pytest.mark.skipif(not VALID_TOKEN, reason="No valid token provided")
def test_api_connection_valid():
    """Test connection with real token."""
    is_valid, msg = test_api_connection(VALID_TOKEN, API_URL)
    assert is_valid is True, msg
    assert "成功" in msg or "success" in msg.lower()


@pytest.mark.skipif(not VALID_TOKEN, reason="No valid token provided")
def test_get_tushare_data_cpi():
    """Fetch CPI data and verify columns and shape."""
    df = get_tushare_data("cpi", token=VALID_TOKEN, api_url=API_URL, use_cache=False)
    assert df is not None
    assert not df.empty
    assert "指标名称" in df.columns
    assert "nt_val" in df.columns or "CPI（居民消费价格指数）_nt_val" in df.columns


@pytest.mark.skipif(not VALID_TOKEN, reason="No valid token provided")
def test_get_tushare_data_with_date_filter():
    """Verify start_date/end_date filtering works."""
    df = get_tushare_data(
        "cpi",
        token=VALID_TOKEN,
        api_url=API_URL,
        use_cache=False,
        start_date="2020-01-01",
        end_date="2020-12-31",
    )
    assert df is not None
    assert not df.empty
    assert df["指标名称"].min().year == 2020
    assert df["指标名称"].max().year == 2020


@pytest.mark.skipif(not VALID_TOKEN, reason="No valid token provided")
def test_merge_tushare_selected():
    """Merge 3 indicators and verify output shape and Date column."""
    df, meta = merge_tushare_selected(
        ["cpi", "ppi", "m2"],
        token=VALID_TOKEN,
        api_url=API_URL,
        output_path="./output/tushare_test_merge.csv",
        missing_value_threshold=60.0,
        start_date="2020-01-01",
        end_date="2023-12-31",
    )
    assert df is not None, meta
    assert "Date" in df.columns
    assert meta["fetched"] == ["cpi", "ppi", "m2"]
    assert len(meta["failed"]) == 0
```

- [ ] **Step 2: Add tushare to requirements.txt**

If `tushare` is not already in `requirements.txt`, add:
```
tushare>=1.2.0
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_tushare_sync.py -v`
Expected:
- `test_tushare_catalog_frequencies` PASS
- `test_tushare_catalog_total` PASS
- `test_search_tushare_empty_keyword` PASS
- `test_search_tushare_by_name` PASS
- `test_search_tushare_by_id` PASS
- `test_api_connection_invalid` PASS
- `test_api_connection_valid` PASS (if token valid)
- `test_get_tushare_data_cpi` PASS (if token valid)
- `test_get_tushare_data_with_date_filter` PASS (if token valid)
- `test_merge_tushare_selected` PASS (if token valid)

- [ ] **Step 4: Commit**

```bash
git add tests/test_tushare_sync.py requirements.txt
git commit -m "test: add tushare_sync unit tests"
```

---

## Task 3: Add Tushare page to `app.py`

**Files:**
- Modify: `app.py:61-62` (page navigation)
- Modify: `app.py:77-81` (sidebar info text)
- Append: `app.py` after line 282 (new page block)

- [ ] **Step 1: Update page navigation**

Replace:
```python
page = st.sidebar.radio("页面", ["本地数据处理", "AkShare 宏观数据同步"])
```
With:
```python
page = st.sidebar.radio("页面", ["本地数据处理", "AkShare 宏观数据同步", "Tushare 宏观数据补充"])
```

- [ ] **Step 2: Update sidebar info text**

Replace:
```python
st.sidebar.info(
    "💡 **提示**：本地数据处理页：将数据文件放入 `raw_data` 文件夹中然后点击【开始处理】。"
    "AkShare 页：搜索并勾选需要的宏观数据指标，然后点击【下载合并后的月度数据】。"
)
```
With:
```python
st.sidebar.info(
    "💡 **提示**：本地数据处理页：将数据文件放入 `raw_data` 文件夹中然后点击【开始处理】。"
    "AkShare/Tushare 页：搜索并勾选需要的宏观数据指标，然后点击【下载合并后的月度数据】。"
)
```

- [ ] **Step 3: Append Tushare page block at end of file**

Append the following block after the last line of `app.py`:

```python
elif page == "Tushare 宏观数据补充":
    st.title("📡 Tushare 宏观数据补充")
    st.markdown("从 Tushare Pro 搜索、勾选、预览宏观数据，一键合并导出")

    from bank_pipeline.tushare_sync import (
        search_tushare,
        get_tushare_data,
        merge_tushare_selected,
        test_api_connection,
        FREQ_MAP as TUSHARE_FREQ_MAP,
    )

    # API Configuration
    st.header("🔑 API 配置")
    token_col, btn_col = st.columns([3, 1])
    with token_col:
        tushare_token = st.text_input(
            "Tushare API Token",
            value="",
            type="password",
            help="请输入您的 Tushare Pro API Token",
        )
        tushare_api_url = st.text_input(
            "API 地址",
            value="http://tsy.xiaodefa.cn",
            help="自定义 API 地址，如无特殊需求保持默认",
        )
    with btn_col:
        st.write("")
        st.write("")
        if st.button("🧪 测试连接", use_container_width=True):
            if not tushare_token:
                st.error("请先输入 Token")
            else:
                with st.spinner("测试中..."):
                    is_valid, msg = test_api_connection(tushare_token, tushare_api_url)
                if is_valid:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

    api_ready = bool(tushare_token)
    if not api_ready:
        st.info("请输入 Tushare API Token 并测试连接后方可使用")

    # Search
    st.header("🔍 搜索宏观数据")
    search_col, _ = st.columns([2, 1])
    with search_col:
        tushare_keyword = st.text_input("输入关键词搜索（如 CPI、GDP、M2）", value="", key="tushare_search")

    tushare_results = search_tushare(tushare_keyword)
    st.caption(f"找到 {len(tushare_results)} 个数据指标")

    # Selection table
    st.header("📋 数据列表")

    if "selected_tushare" not in st.session_state:
        st.session_state.selected_tushare = set()

    cols_per_row = 2
    for i in range(0, len(tushare_results), cols_per_row):
        row_items = tushare_results[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, item in zip(cols, row_items):
            with col:
                checked = item["id"] in st.session_state.selected_tushare
                freq_label = TUSHARE_FREQ_MAP.get(item["freq"], item["freq"])
                disabled = not api_ready
                if st.checkbox(
                    f"**{item['name']}**  ({freq_label})",
                    value=checked,
                    key=f"tushare_chk_{item['id']}",
                    disabled=disabled,
                ):
                    st.session_state.selected_tushare.add(item["id"])
                else:
                    st.session_state.selected_tushare.discard(item["id"])

    # Preview selected
    tushare_selected = list(st.session_state.selected_tushare)
    if tushare_selected:
        st.header(f"✅ 已选择 {len(tushare_selected)} 个指标")

        preview_tabs = st.tabs(
            [next((r["name"] for r in tushare_results if r["id"] == sid), sid) for sid in tushare_selected]
        )
        for tab, sid in zip(preview_tabs, tushare_selected):
            with tab:
                with st.spinner("加载中..."):
                    if api_ready:
                        df_preview = get_tushare_data(sid, token=tushare_token, api_url=tushare_api_url)
                    else:
                        df_preview = None
                if df_preview is not None and not df_preview.empty:
                    st.write(f"数据量: {len(df_preview)} 行 × {len(df_preview.columns)} 列")
                    st.dataframe(df_preview.tail(10), use_container_width=True)
                else:
                    st.error("数据加载失败")
    else:
        st.info("请在上方勾选需要的数据指标")

    # Merge and export
    st.header("▶️ 合并导出")
    merge_disabled = not api_ready or not tushare_selected
    if st.button(
        "🚀 下载合并后的月度数据",
        type="primary",
        use_container_width=True,
        disabled=merge_disabled,
    ):
        with st.spinner(f"正在同步 {len(tushare_selected)} 个指标的数据..."):
            merged_df, meta = merge_tushare_selected(
                tushare_selected,
                token=tushare_token,
                api_url=tushare_api_url,
                output_path="./output/tushare_merged.csv",
                missing_value_threshold=missing_threshold,
                start_date=str(start_date),
                end_date=str(end_date),
            )
        if merged_df is not None:
            st.success(f"✅ 合并完成！{meta['shape'][0]} 行 × {meta['shape'][1]} 列")
            with open(meta["output"], "rb") as f:
                st.download_button(
                    label="⬇️ 下载 CSV",
                    data=f,
                    file_name="tushare_merged.csv",
                    mime="text/csv",
                )
            st.dataframe(merged_df.tail(20), use_container_width=True)
        else:
            st.error("合并失败，请检查网络或选择的指标")

    st.markdown("---")
    st.caption("数据来源于 Tushare Pro 财经数据接口")
```

- [ ] **Step 4: Verify syntax**

Run: `python -m py_compile app.py`
Expected: exit code 0 (no output)

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: add Tushare macro data page to Streamlit frontend"
```

---

## Task 4: Integration testing

**Files:**
- None (verify existing files work together)

- [ ] **Step 1: Verify app.py can import both modules**

Run:
```bash
python -c "from bank_pipeline.akshare_sync import MACRO_CATALOG; from bank_pipeline.tushare_sync import TUSHARE_CATALOG; print(f'AkShare: {len(MACRO_CATALOG)}, Tushare: {len(TUSHARE_CATALOG)}')"
```
Expected: `AkShare: 65, Tushare: 15`

- [ ] **Step 2: Verify app.py syntax**

Run: `python -m py_compile app.py`
Expected: no errors

- [ ] **Step 3: Run all tests**

Run: `pytest tests/test_tushare_sync.py -v`
Expected: all tests pass

- [ ] **Step 4: Commit and push**

```bash
git push
```

---

## Self-Review

**1. Spec coverage:**
- ✅ 独立 Tushare 页面 — Task 3
- ✅ API 配置区 + 测试连接 — Task 3 Step 1
- ✅ 15 个核心指标 catalog — Task 1 Step 1
- ✅ 搜索勾选预览合并 — Task 1 Step 4 + Task 3 Step 3
- ✅ 日期解析（month/quarter/date/trade_date）— Task 1 Step 2
- ✅ 日度/季度 → 月度转换（复用 DataCleaner）— Task 1 Step 4
- ✅ Spring Festival 处理 — Task 1 Step 4
- ✅ API 无效时禁用操作 — Task 3 Step 3
- ✅ 本地 CSV 缓存 — Task 1 Step 3
- ✅ 单元测试 — Task 2
- ✅ requirements.txt 添加 tushare — Task 2 Step 2

**2. Placeholder scan:** 无 TBD/TODO。

**3. Type consistency:** `get_tushare_data` 和 `merge_tushare_selected` 参数签名与 `akshare_sync.py` 对应函数一致（`start_date`, `end_date`, `missing_value_threshold`）。
