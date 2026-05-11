# Tushare 宏观数据补充模块设计文档

## 目标

为银行预测数据处理系统增加第三条数据来源——Tushare Pro 宏观数据。作为 AkShare 宏观数据的补充，提供独立的搜索、勾选、预览、合并导出功能。如果用户未配置 Tushare API Token 或 API 无效，不影响现有本地数据处理和 AkShare 宏观数据同步两条线路的正常使用。

## 技术栈

- Python 3.9+
- tushare (Pro API)
- pandas
- streamlit
- 复用现有 `DataCleaner` 和 `handle_spring_festival_split`

## 架构

新增一个独立模块 `bank_pipeline/tushare_sync.py`，公共接口与 `akshare_sync.py` 保持对称。`app.py` 在侧边栏增加第三个页面导航选项。

```
app.py
  ├── 本地数据处理（已有，不变）
  ├── AkShare 宏观数据同步（已有，不变）
  └── Tushare 宏观数据补充（新增）

bank_pipeline/
  ├── akshare_sync.py（已有，不变）
  ├── tushare_sync.py（新增）
  ├── cleaner.py（复用，不变）
  └── engineer.py（复用，不变）
```

## Tushare 核心指标清单（15 个）

| ID | 名称 | 频率 | 函数 | 日期列 |
|---|---|---|---|---|
| `cpi` | CPI | monthly | `cn_cpi` | `month` |
| `ppi` | PPI | monthly | `cn_ppi` | `month` |
| `gdp` | GDP | quarterly | `cn_gdp` | `quarter` |
| `m2` | 货币供应量 | monthly | `cn_m` | `month` |
| `industrial` | 工业增加值 | monthly | `cn_industrial` | `month` |
| `pmi` | PMI | monthly | `cn_pmi` | `month` |
| `retail` | 社零总额 | monthly | `cn_sf` | `month` |
| `fdi` | 外商直接投资 | monthly | `cn_fdi` | `month` |
| `export` | 出口 | monthly | `cn_export` | `month` |
| `import` | 进口 | monthly | `cn_import` | `month` |
| `consume` | 居民收入/消费 | monthly | `cn_consume` | `month` |
| `shibor` | SHIBOR | daily | `shibor` | `date` |
| `money_supply` | 货币供应量(另一口径) | monthly | `money_supply` | `month` |
| `fx_daily` | 人民币汇率 | daily | `fx_daily` | `trade_date` |
| `house_price` | 房价指数 | monthly | `cn_ppr` | `month` |

**频率限制**：仅保留 `daily`、`monthly`、`quarterly`，无 `yearly`/`weekly`，确保可合并为月度大表。

## `tushare_sync.py` 公共接口

```python
# 频率映射
FREQ_MAP = {"daily": "日度", "monthly": "月度", "quarterly": "季度"}

# 指标目录
TUSHARE_CATALOG: List[Dict]

def get_tushare_pro_api(token: str, api_url: str = "http://tsy.xiaodefa.cn") -> Optional[object]:
    """Initialize Tushare Pro API with token and custom URL."""

def test_api_connection(token: str, api_url: str = "http://tsy.xiaodefa.cn") -> Tuple[bool, str]:
    """Test if token is valid. Returns (is_valid, message)."""

def get_tushare_data(
    indicator_id: str,
    token: str,
    api_url: str = "http://tsy.xiaodefa.cn",
    use_cache: bool = True,
    cache_dir: str = "./.tushare_cache",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """Fetch Tushare macro data by id, with optional caching and date filtering.
    Standardizes date column to '指标名称' to match akshare_sync interface.
    """

def search_tushare(keyword: str = "") -> List[Dict]:
    """Search TUSHARE_CATALOG by keyword (case-insensitive)."""

def merge_tushare_selected(
    selected_ids: List[str],
    token: str,
    api_url: str = "http://tsy.xiaodefa.cn",
    output_path: str = "./output/tushare_merged.csv",
    missing_value_threshold: float = 20.0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[Optional[pd.DataFrame], Dict]:
    """Fetch selected Tushare indicators, standardize, apply spring festival handling, then merge."""
```

## 日期处理

Tushare 日期格式：
- `month`: `"202601"` (YYYYMM) → parse to `2026-01-01`
- `quarter`: `"2026Q1"` → parse to `2026-01-01`
- `date`: `"20260110"` (YYYYMMDD) → parse to `2026-01-10`
- `trade_date`: `"20260110"` → parse to `2026-01-10`

统一标准化为 `指标名称` 列（和 AkShare 保持一致），便于复用 `DataCleaner`。

## 日度/季度 → 月度转换

复用 `DataCleaner.resample_to_monthly()`：
- **daily**（shibor, fx_daily）：`resample('ME').mean()`，和 AkShare 日度逻辑一致
- **quarterly**（gdp）：`resample('ME').asfreq()` + `interpolate(method='linear')`
- **monthly**：直接 `resample('ME').mean()`

合并前对 daily/monthly 数据调用 `handle_spring_festival_split`（和 AkShare 逻辑一致）。

## Streamlit 前端设计

### 页面导航

```python
page = st.sidebar.radio("页面", ["本地数据处理", "AkShare 宏观数据同步", "Tushare 宏观数据补充"])
```

### Tushare 页面结构

1. **API 配置区**（最上方）：
   - Token 输入框（`st.text_input`，type="password"，支持粘贴）
   - 自定义 API 地址输入框（默认 `http://tsy.xiaodefa.cn`）
   - "💾 保存 Token" 按钮：保存到 `./.tushare_token` 文件
   - "🧪 测试连接" 按钮：调用 `test_api_connection()`
   - 连接状态提示：绿色 `st.success` / 红色 `st.error`

2. **指标搜索与勾选区**（和 AkShare 页面对称）：
   - 关键词搜索框
   - 2 列布局 checkbox 列表
   - 频率标签显示

3. **预览区**（和 AkShare 页面对称）：
   - Tab 展示每个已选指标的最后 10 行

4. **合并导出区**（和 AkShare 页面对称）：
   - "下载合并后的月度数据" 按钮
   - `st.spinner` 显示同步进度
   - 成功提示 + CSV 下载按钮 + 数据预览

### API 无效时的行为

- **未配置 token**：显示 `st.info("请输入 Tushare API Token 并测试连接")`，指标列表可浏览但勾选和合并按钮禁用
- **测试连接失败**：显示 `st.error("API 连接失败：token 无效或已过期，请检查配置")`，同时禁用勾选和合并
- **不影响其他页面**：用户可随时切换到 AkShare 或本地数据处理页面正常使用

## 缓存策略

- 每个指标独立 CSV 缓存到 `./.tushare_cache/{indicator_id}.csv`
- 缓存 key 包含 token 前 8 位哈希，避免多 token 混用

## 单元测试（`tests/test_tushare_sync.py`）

```python
def test_api_connection_valid():
    """Test connection with real token."""

def test_api_connection_invalid():
    """Test connection with fake token returns False."""

def test_get_tushare_data_cpi():
    """Fetch CPI data and verify columns and shape."""

def test_get_tushare_data_with_date_filter():
    """Verify start_date/end_date filtering works."""

def test_merge_tushare_selected():
    """Merge 3 indicators and verify output shape and Date column."""

def test_search_tushare():
    """Search keyword returns matching indicators."""

def test_tushare_catalog_frequencies():
    """All indicators have daily/monthly/quarterly frequency only."""
```

## 错误处理

| 场景 | 处理 |
|---|---|
| Token 为空 | 提示输入 token，禁用操作 |
| Token 无效 | 提示 API 过期/无效，禁用操作 |
| 网络超时 | 记录日志，返回 None，前端显示"数据加载失败" |
| 指标无数据 | 返回 None，跳过该指标，记录到 metadata["failed"] |
| 日期解析失败 | 丢弃该行，继续处理 |

## Self-Review

1. **Spec coverage**: ✅ 独立页面、API 配置、15 个指标、日期处理、合并逻辑、缓存、测试、错误处理全覆盖
2. **Placeholder scan**: ✅ 无 TBD/TODO
3. **Type consistency**: ✅ `get_tushare_data` 和 `merge_tushare_selected` 参数与 `akshare_sync.py` 对应函数一致
4. **Scope check**: ✅ 聚焦 Tushare 补充数据源，不改动现有 AkShare/本地处理逻辑
