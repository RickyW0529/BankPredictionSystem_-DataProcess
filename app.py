"""
Bank Prediction System - Streamlit Frontend

Usage:
    streamlit run app.py
"""

import json
import os
import platform
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="银行预测数据处理系统", layout="wide")

if "validated_freqs" not in st.session_state:
    st.session_state.validated_freqs = {}


def open_folder(path: str):
    """Open a folder in the native file explorer."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception as e:
        st.error(f"无法打开文件夹: {e}")


@st.cache_data(show_spinner=False)
def preview_csv(file_path: str, nrows: int = 5) -> pd.DataFrame:
    """Preview first n rows of a CSV/Excel file."""
    try:
        path = Path(file_path)
        if path.suffix == ".csv":
            df = pd.read_csv(file_path, nrows=nrows)
        elif path.suffix in (".xlsx", ".xls"):
            df = pd.read_excel(file_path, nrows=nrows)
        else:
            return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()


def find_data_files(data_dir: str) -> list:
    """Recursively find CSV/Excel files in data_dir."""
    path = Path(data_dir)
    if not path.exists():
        return []
    files = []
    for ext in ("*.csv", "*.xlsx", "*.xls"):
        files.extend(path.rglob(ext))
    return sorted(files)


def _render_indicator_selector(results, selected_key, freq_map, prefix, disabled=False):
    """Render grouped indicator selector with select-all/clear."""

    # Group by frequency
    grouped = defaultdict(list)
    for item in results:
        grouped[item["freq"]].append(item)

    # Frequency order
    freq_order = ["daily", "monthly", "quarterly"]
    freq_labels = {
        "daily": "📅 日度指标",
        "monthly": "📆 月度指标",
        "quarterly": "📊 季度指标",
        "unknown": "📁 其他指标",
    }

    # Single source of truth: read selected state directly from checkbox widget keys
    selected_set = set()
    for item in results:
        chk_key = f"{prefix}_chk_{item['id']}"
        if st.session_state.get(chk_key, False):
            selected_set.add(item["id"])

    # Sync back to canonical session_state key so downstream code can read it
    st.session_state[selected_key] = selected_set

    total_results = len(results)
    st.metric("已选 / 总计", f"{len(selected_set)} / {total_results}")

    # Batch controls: select all / clear only
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 全选", key=f"{prefix}_select_all", width='stretch', disabled=disabled):
            for item in results:
                st.session_state[f"{prefix}_chk_{item['id']}"] = True
            st.rerun()
    with col2:
        if st.button("❌ 清空", key=f"{prefix}_clear_all", width='stretch', disabled=disabled):
            for item in results:
                st.session_state[f"{prefix}_chk_{item['id']}"] = False
            st.rerun()

    # Grouped expanders
    for freq in freq_order:
        if freq not in grouped:
            continue
        items = grouped[freq]
        label = freq_labels.get(freq, freq)
        selected_in_group = sum(1 for it in items if it["id"] in selected_set)
        with st.expander(f"{label} ({len(items)} 个, 已选 {selected_in_group})", expanded=False):
            cols_per_row = 2
            for i in range(0, len(items), cols_per_row):
                row_items = items[i:i + cols_per_row]
                cols = st.columns(cols_per_row)
                for col, item in zip(cols, row_items):
                    with col:
                        freq_label = freq_map.get(item["freq"], item["freq"])
                        st.checkbox(
                            f"**{item['name']}**  ({freq_label})",
                            key=f"{prefix}_chk_{item['id']}",
                            disabled=disabled,
                        )


# Page navigation
page = st.sidebar.radio("页面", ["本地数据处理", "AkShare 宏观数据同步", "Tushare 宏观数据同步", "同花顺 iFinD 宏观数据同步"])

# ===== Sidebar: Configuration =====
st.sidebar.title("⚙️ 参数配置")

missing_threshold = st.sidebar.slider(
    "缺失值阈值 (%)", min_value=0, max_value=100, value=60, step=5,
    help="删除缺失率超过此值的列",
)

st.sidebar.markdown("---")
st.sidebar.subheader("📅 日期范围")
start_date = st.sidebar.date_input("开始日期", value=pd.to_datetime("2019-01-01"))
end_date = st.sidebar.date_input("结束日期", value=pd.to_datetime("today"))

st.sidebar.markdown("---")
st.sidebar.info(
    "💡 **提示**：本地数据处理页：上传 CSV/Excel 数据文件后点击【开始处理】。"
    "AkShare/Tushare 页：搜索并勾选需要的宏观数据指标，然后点击【下载合并后的月度数据】。"
)

if page == "本地数据处理":
    st.title("🏦 银行预测数据处理系统")
    st.markdown("上传日度、月度、季度数据文件 → 点击处理 → 下载结果")

    output_dir = "./output"

    st.header("📂 数据上传")

    auto_detect = st.checkbox("🔍 启用自动识别模式（自动检测日期列、数据列和频率）", value=True)

    if auto_detect:
        uploaded_files = st.file_uploader(
            "上传 CSV/Excel 文件（支持多文件，自动识别日期列和数据列）",
            type=["csv", "xlsx", "xls"],
            accept_multiple_files=True,
            key="auto_uploader",
        )

        all_uploaded = uploaded_files
        parsed_files = []
        if uploaded_files:
            from bank_pipeline.ifind_parser import auto_parse_dataframe

            for f in uploaded_files:
                try:
                    if f.name.endswith(".csv"):
                        df_raw = pd.read_csv(f)
                    else:
                        df_raw = pd.read_excel(f)
                    result = auto_parse_dataframe(df_raw)
                    parsed_files.append({
                        "file": f,
                        "name": f.name,
                        "date_col": result["date_col"],
                        "data_cols": result["data_cols"],
                        "freq": result["freq"],
                        "data": result["data"],
                    })
                    st.success(
                        f"✅ {f.name}: 识别到 {len(result['data_cols'])} 个数据列，"
                        f"频率: {result['freq']}，共 {len(result['data'])} 行"
                    )
                except Exception as e:
                    st.error(f"❌ {f.name} 解析失败: {e}")

            if parsed_files:
                st.subheader("📋 自动识别结果")
                for pf in parsed_files:
                    st.write(f"**{pf['name']}**  |  日期列: `{pf['date_col']}`  |  频率: `{pf['freq']}`")
                    st.write(f"数据列: {', '.join(pf['data_cols'])}")
                    st.dataframe(pf["data"].head(5), width='stretch')

        # Build data_list for pipeline
        data_list = []
        for pf in parsed_files:
            df = pf["data"].copy()
            date_col = pf["date_col"]
            freq = pf["freq"] if pf["freq"] != "unknown" else "monthly"
            data_list.append((df, date_col, freq))
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            daily_files = st.file_uploader(
                "📅 日度数据", type=["csv", "xlsx", "xls"], accept_multiple_files=True, key="daily_uploader"
            )
        with col2:
            monthly_files = st.file_uploader(
                "📆 月度数据", type=["csv", "xlsx", "xls"], accept_multiple_files=True, key="monthly_uploader"
            )
        with col3:
            quarterly_files = st.file_uploader(
                "📊 季度数据", type=["csv", "xlsx", "xls"], accept_multiple_files=True, key="quarterly_uploader"
            )

        all_uploaded = daily_files + monthly_files + quarterly_files

        if all_uploaded:
            st.success(f"✅ 已上传 {len(all_uploaded)} 个文件（日度 {len(daily_files)} / 月度 {len(monthly_files)} / 季度 {len(quarterly_files)}）")

            # Preview
            st.subheader("数据预览（前5行）")
            preview_tabs = st.tabs([f.name for f in all_uploaded])
            for tab, f in zip(preview_tabs, all_uploaded):
                with tab:
                    try:
                        if f.name.endswith(".csv"):
                            df_preview = pd.read_csv(f, nrows=5)
                        else:
                            df_preview = pd.read_excel(f, nrows=5)
                        st.dataframe(df_preview, width='stretch')
                    except Exception as e:
                        st.error(f"无法读取该文件: {e}")
                    f.seek(0)

        # Build data_list for manual mode
        data_list = []
        if all_uploaded:
            from bank_pipeline.loader import detect_date_column, parse_date_column
            for freq, files in [("daily", daily_files), ("monthly", monthly_files), ("quarterly", quarterly_files)]:
                for f in files:
                    try:
                        if f.name.endswith(".csv"):
                            df = pd.read_csv(f)
                        else:
                            df = pd.read_excel(f)
                    except Exception as e:
                        st.error(f"读取 {f.name} 失败: {e}")
                        continue
                    date_col = detect_date_column(df, ["Date", "date", "日期", "月份", "季度", "时间"])
                    if date_col is None:
                        st.error(f"❌ {f.name}: 未找到日期列")
                        continue
                    df[date_col] = parse_date_column(df[date_col])
                    df = df.dropna(subset=[date_col]).sort_values(date_col)
                    data_list.append((df, date_col, freq))

    st.header("▶️ 运行处理")
    run_clicked = st.button("🚀 开始处理", type="primary", width='stretch')

    log_container = st.empty()

    if run_clicked:
        if not data_list:
            st.error("❌ 请先上传数据文件")
            st.stop()

        # Run pipeline in-memory
        import io, logging
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        handler.setFormatter(formatter)
        pipeline_logger = logging.getLogger("bank_pipeline")
        pipeline_logger.addHandler(handler)
        pipeline_logger.setLevel(logging.INFO)

        with st.spinner("正在处理，请稍候..."):
            try:
                from main import run_pipeline
                result_df, metadata = run_pipeline(
                    data_list=data_list,
                    output_dir=output_dir,
                    missing_value_threshold=missing_threshold,
                    save_intermediate=True,
                )
                success = True
            except Exception as e:
                st.error(f"❌ 处理失败: {e}")
                success = False

        # Display logs
        log_text = log_stream.getvalue()
        if log_text:
            log_container.text(log_text[-2000:])  # show last 2000 chars

        pipeline_logger.removeHandler(handler)

        if success:
            st.success("✅ 处理完成！")
            st.header("📊 处理结果")
            output_path = Path(output_dir)
            if output_path.exists():
                result_files = sorted(output_path.glob("*.csv"))
                if result_files:
                    for rf in result_files:
                        st.write(f"- `{rf.name}`")
                        try:
                            df_result = pd.read_csv(rf)
                            st.caption(f"形状: {df_result.shape[0]} 行 × {df_result.shape[1]} 列")
                            with open(rf, "rb") as f:
                                st.download_button(
                                    label=f"⬇️ 下载 {rf.name}",
                                    data=f,
                                    file_name=rf.name,
                                    mime="text/csv",
                                    key=str(rf),
                                )
                        except Exception as e:
                            st.error(f"读取结果失败: {e}")
                else:
                    st.info("output 目录下暂无 CSV 文件")
            else:
                st.info("未找到 output 目录")

    st.markdown("---")
    st.caption("银行预测数据处理系统 | 基于 Streamlit 构建")

elif page == "AkShare 宏观数据同步":
    st.title("📡 AkShare 宏观数据同步")
    st.markdown("从中国宏观数据库搜索、勾选、预览数据，一键合并导出")

    from bank_pipeline.akshare_sync import search_macros, get_macro_data, merge_selected_macros, FREQ_MAP

    # Search
    st.header("🔍 搜索宏观数据")
    search_col, _ = st.columns([2, 1])
    with search_col:
        keyword = st.text_input("输入关键词搜索（如 CPI、GDP、PMI）", value="")

    results = [{**r} for r in search_macros(keyword)]

    # Apply runtime-validated frequencies if available
    validated_freqs = st.session_state.get("validated_freqs", {})
    for r in results:
        if r["id"] in validated_freqs:
            r["freq"] = validated_freqs[r["id"]]

    st.caption(f"找到 {len(results)} 个数据指标")

    # Selection table
    st.header("📋 数据列表")

    if "selected_macros" not in st.session_state:
        st.session_state.selected_macros = set()

    _render_indicator_selector(results, "selected_macros", FREQ_MAP, "akshare")

    # Preview selected
    selected = list(st.session_state.selected_macros)
    if selected:
        st.header(f"✅ 已选择 {len(selected)} 个指标")

        if st.button("🔄 重新拉取", key="akshare_refresh", width='stretch'):
            with st.spinner("正在重新拉取数据..."):
                for sid in selected:
                    get_macro_data(
                        sid,
                        use_cache=False,
                        start_date=str(start_date),
                        end_date=str(end_date),
                    )
            st.success("✅ 已重新拉取")
            st.rerun()

        preview_tabs = st.tabs([next((r["name"] for r in results if r["id"] == sid), sid) for sid in selected])
        for tab, sid in zip(preview_tabs, selected):
            with tab:
                with st.spinner("加载中..."):
                    df_preview = get_macro_data(
                        sid,
                        start_date=str(start_date),
                        end_date=str(end_date),
                    )
                if df_preview is not None and not df_preview.empty:
                    # Runtime frequency validation
                    from bank_pipeline.akshare_sync import detect_data_frequency
                    actual_freq = detect_data_frequency(df_preview)
                    if actual_freq != "unknown":
                        if "validated_freqs" not in st.session_state:
                            st.session_state.validated_freqs = {}
                        st.session_state.validated_freqs[sid] = actual_freq

                    st.write(f"数据量: {len(df_preview)} 行 × {len(df_preview.columns)} 列")
                    st.dataframe(df_preview.tail(10), width='stretch')
                else:
                    st.error("数据加载失败")
    else:
        st.info("请在上方勾选需要的数据指标")

    # Merge and export
    st.header("▶️ 合并导出")
    if selected and st.button("🚀 下载合并后的月度数据", type="primary", width='stretch'):
        with st.spinner(f"正在同步 {len(selected)} 个指标的数据..."):
            merged_df, meta = merge_selected_macros(
                selected,
                output_path="./output/akshare_merged.csv",
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
                    file_name="akshare_merged.csv",
                    mime="text/csv",
                )
            st.dataframe(merged_df.tail(20), width='stretch')
        else:
            st.error("合并失败，请检查网络或选择的指标")

    st.markdown("---")
    st.caption("数据来源于 AkShare 开源财经数据接口")

elif page == "Tushare 宏观数据同步":
    st.title("📡 Tushare 宏观数据同步")
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
        if st.button("🧪 测试连接", width='stretch'):
            if not tushare_token:
                st.error("请先输入 Token")
            else:
                with st.spinner("测试中..."):
                    is_valid, msg = test_api_connection(tushare_token, tushare_api_url)
                if is_valid:
                    st.success(f"✅ {msg}")
                    st.session_state.tushare_api_ready = True
                else:
                    st.error(f"❌ {msg}")
                    st.session_state.tushare_api_ready = False

    api_ready = st.session_state.get("tushare_api_ready", False)
    if not tushare_token:
        api_ready = False
        st.info("请输入 Tushare API Token 并测试连接")
    elif not api_ready:
        st.info("请输入 Token 后点击【测试连接】以启用数据操作")

    # Search
    st.header("🔍 搜索宏观数据")
    search_col, _ = st.columns([2, 1])
    with search_col:
        tushare_keyword = st.text_input("输入关键词搜索（如 CPI、GDP、M2）", value="", key="tushare_search")

    tushare_results = [{**r} for r in search_tushare(tushare_keyword)]

    # Apply runtime-validated frequencies if available
    validated_freqs = st.session_state.get("validated_freqs", {})
    for r in tushare_results:
        if r["id"] in validated_freqs:
            r["freq"] = validated_freqs[r["id"]]

    st.caption(f"找到 {len(tushare_results)} 个数据指标")

    # Selection table
    st.header("📋 数据列表")

    if "selected_tushare" not in st.session_state:
        st.session_state.selected_tushare = set()

    _render_indicator_selector(
        tushare_results, "selected_tushare", TUSHARE_FREQ_MAP, "tushare", disabled=not api_ready
    )

    # Preview selected
    tushare_selected = list(st.session_state.selected_tushare)
    if tushare_selected:
        st.header(f"✅ 已选择 {len(tushare_selected)} 个指标")

        refresh_disabled = not api_ready
        if st.button("🔄 重新拉取", key="tushare_refresh", width='stretch', disabled=refresh_disabled):
            with st.spinner("正在重新拉取数据..."):
                for sid in tushare_selected:
                    get_tushare_data(
                        sid,
                        token=tushare_token,
                        api_url=tushare_api_url,
                        use_cache=False,
                        start_date=str(start_date),
                        end_date=str(end_date),
                    )
            st.success("✅ 已重新拉取")
            st.rerun()

        preview_tabs = st.tabs(
            [next((r["name"] for r in tushare_results if r["id"] == sid), sid) for sid in tushare_selected]
        )
        for tab, sid in zip(preview_tabs, tushare_selected):
            with tab:
                with st.spinner("加载中..."):
                    if api_ready:
                        df_preview = get_tushare_data(
                            sid,
                            token=tushare_token,
                            api_url=tushare_api_url,
                            start_date=str(start_date),
                            end_date=str(end_date),
                        )
                    else:
                        df_preview = None
                if df_preview is not None and not df_preview.empty:
                    # Runtime frequency validation
                    from bank_pipeline.akshare_sync import detect_data_frequency
                    actual_freq = detect_data_frequency(df_preview)
                    if actual_freq != "unknown":
                        if "validated_freqs" not in st.session_state:
                            st.session_state.validated_freqs = {}
                        st.session_state.validated_freqs[sid] = actual_freq

                    st.write(f"数据量: {len(df_preview)} 行 × {len(df_preview.columns)} 列")
                    st.dataframe(df_preview.tail(10), width='stretch')
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
        width='stretch',
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
            st.dataframe(merged_df.tail(20), width='stretch')
        else:
            st.error("合并失败，请检查网络或选择的指标")

    st.markdown("---")
    st.caption("数据来源于 Tushare Pro 财经数据接口")

elif page == "同花顺 iFinD 宏观数据同步":
    st.title("📡 同花顺 iFinD 宏观数据同步")
    st.caption("从 iFinD HTTP API 搜索、勾选、预览宏观数据，一键合并导出")

    from bank_pipeline.ifind_sync import (
        search_ifind,
        get_ifind_data,
        merge_ifind_selected,
        IFindClient,
        FREQ_MAP as IFIND_FREQ_MAP,
        get_ifind_catalog,
        save_ifind_catalog,
        reset_ifind_catalog,
        load_ifind_token,
        save_ifind_token,
        clear_ifind_token,
    )

    # Format dates for iFinD API (YYYYMMDD)
    ifind_start = start_date.strftime("%Y%m%d") if start_date else None
    ifind_end = end_date.strftime("%Y%m%d") if end_date else None

    # ── API 配置卡片 ──────────────────────────────────────
    with st.container(border=True):
        st.markdown("#### 🔑 API 配置")
        saved_token = load_ifind_token()
        token_col, save_col, test_col = st.columns([3, 1, 1])
        with token_col:
            ifind_token = st.text_input(
                "iFinD Access Token",
                value=saved_token or "",
                type="password",
                label_visibility="collapsed",
                placeholder="请输入您的 iFinD Access Token",
            )
        with save_col:
            if st.button("💾 保存Token", use_container_width=True):
                if ifind_token:
                    save_ifind_token(ifind_token)
                    st.toast("Token 已保存", icon="✅")
                else:
                    st.toast("Token 为空，未保存", icon="⚠️")
        with test_col:
            if st.button("🧪 测试连接", use_container_width=True):
                if not ifind_token:
                    st.error("请先输入 Token")
                else:
                    with st.spinner("测试中..."):
                        client = IFindClient(ifind_token)
                        is_valid = client.test_connection()
                    if is_valid:
                        st.success("✅ 连接成功")
                        st.session_state.ifind_api_ready = True
                        st.session_state.ifind_last_tested_token = ifind_token
                    else:
                        st.error("❌ 连接失败，请检查 Token")
                        st.session_state.ifind_api_ready = False

        api_ready = st.session_state.get("ifind_api_ready", False)
        last_tested_token = st.session_state.get("ifind_last_tested_token", "")
        if ifind_token != last_tested_token:
            api_ready = False
        if not ifind_token:
            api_ready = False
            st.info("💡 请输入 iFinD Access Token 并测试连接", icon="ℹ️")
        elif not api_ready:
            st.info("💡 请输入 Token 后点击【测试连接】以启用数据操作", icon="ℹ️")

    # ── 管理指标配置 ──────────────────────────────────────
    with st.expander("📋 管理指标配置", expanded=False):
        current_catalog = get_ifind_catalog()
        st.markdown(f"当前共 **{len(current_catalog)}** 个指标")

        display_df = pd.DataFrame([
            {"指标名称": c["name"], "指标代码": c["indicator"], "频率": c.get("freq", "monthly")}
            for c in current_catalog
        ])
        st.dataframe(display_df, hide_index=True, use_container_width=True)

        st.markdown("---")
        st.markdown("**✏️ 自定义指标（JSON 格式）**")

        # Initialize or sync textarea content
        catalog_hash = hash(str(current_catalog))
        if "ifind_catalog_hash" not in st.session_state:
            st.session_state.ifind_catalog_hash = None
        if st.session_state.ifind_catalog_hash != catalog_hash:
            st.session_state.ifind_catalog_json = json.dumps(current_catalog, ensure_ascii=False, indent=2)
            st.session_state.ifind_catalog_hash = catalog_hash
        # Guard for fresh session state
        if "ifind_catalog_json" not in st.session_state:
            st.session_state.ifind_catalog_json = json.dumps(current_catalog, ensure_ascii=False, indent=2)

        catalog_json = st.text_area(
            "指标配置 JSON",
            height=300,
            key="ifind_catalog_json",
            help="每个指标需包含 id、name、freq、indicator 四个字段。直接编辑后保存即可生效。",
        )

        # Real-time validation
        validation_error = None
        parsed_catalog = None
        try:
            parsed_catalog = json.loads(catalog_json)
            if not isinstance(parsed_catalog, list):
                validation_error = "JSON 根节点必须是数组 []"
            else:
                required_keys = {"id", "name", "freq", "indicator"}
                for idx, item in enumerate(parsed_catalog):
                    if not isinstance(item, dict):
                        validation_error = f"第 {idx + 1} 项必须是对象"
                        break
                    missing = required_keys - set(item.keys())
                    if missing:
                        validation_error = f"第 {idx + 1} 项缺少字段: {', '.join(missing)}"
                        break
        except json.JSONDecodeError as e:
            validation_error = f"JSON 格式错误: {e.msg} (第 {e.lineno} 行, 第 {e.colno} 列)"

        if validation_error:
            st.error(f"❌ {validation_error}")
        else:
            st.success("✅ JSON 格式正确")

        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1:
            if st.button("💾 保存配置", key="ifind_save_catalog", use_container_width=True):
                if validation_error:
                    st.error("请先修正 JSON 格式错误再保存")
                else:
                    save_ifind_catalog(parsed_catalog)
                    if "selected_ifind_catalog" in st.session_state:
                        valid_ids = {c["id"] for c in parsed_catalog}
                        st.session_state.selected_ifind_catalog = {
                            sid for sid in st.session_state.selected_ifind_catalog
                            if sid in valid_ids
                        }
                    st.toast("配置已保存", icon="✅")
                    st.rerun()
        with btn_col2:
            if st.button("🔄 重置为默认", key="ifind_reset_catalog", use_container_width=True):
                reset_ifind_catalog()
                st.session_state.selected_ifind_catalog = set()
                st.toast("已重置为默认配置", icon="🔄")
                st.rerun()
        with btn_col3:
            if st.button("🗑️ 清空Token", key="ifind_clear_token_btn", use_container_width=True):
                clear_ifind_token()
                st.toast("Token 已清除", icon="🗑️")
                st.rerun()

    # ── 搜索与选择 ─────────────────────────────────────────
    with st.container(border=True):
        st.markdown("#### 🔍 搜索宏观数据")
        ifind_keyword = st.text_input(
            "输入关键词搜索",
            value="",
            key="ifind_search",
            placeholder="如 CPI、GDP、PMI...",
        )
        ifind_results = [{**r} for r in search_ifind(ifind_keyword)]
        st.caption(f"找到 **{len(ifind_results)}** 个数据指标")

        if "selected_ifind_catalog" not in st.session_state:
            st.session_state.selected_ifind_catalog = set()

        _render_indicator_selector(
            ifind_results, "selected_ifind_catalog", IFIND_FREQ_MAP, "ifind_catalog", disabled=not api_ready
        )

    # ── 预览区域 ───────────────────────────────────────────
    ifind_catalog_selected = list(st.session_state.selected_ifind_catalog)

    if ifind_catalog_selected:
        with st.container(border=True):
            st.markdown(f"#### ✅ 已选择 {len(ifind_catalog_selected)} 个指标")

            refresh_disabled = not api_ready
            if st.button("🔄 重新拉取", key="ifind_refresh", disabled=refresh_disabled):
                refresh_errors = []
                with st.spinner("正在重新拉取数据..."):
                    for sid in ifind_catalog_selected:
                        try:
                            get_ifind_data(
                                sid,
                                access_token=ifind_token,
                                use_cache=False,
                                start_date=ifind_start,
                                end_date=ifind_end,
                            )
                        except Exception as e:
                            refresh_errors.append(f"{sid}: {e}")
                if refresh_errors:
                    st.error("部分指标拉取失败:\n" + "\n".join(refresh_errors))
                else:
                    st.toast("已重新拉取", icon="✅")
                st.rerun()

            preview_tabs = st.tabs(
                [next((r["name"] for r in ifind_results if r["id"] == sid), sid) for sid in ifind_catalog_selected]
            )
            for tab, sid in zip(preview_tabs, ifind_catalog_selected):
                with tab:
                    with st.spinner("加载中..."):
                        if api_ready:
                            try:
                                df_preview = get_ifind_data(
                                    sid,
                                    access_token=ifind_token,
                                    start_date=ifind_start,
                                    end_date=ifind_end,
                                )
                            except Exception as e:
                                df_preview = None
                                st.error(f"数据加载失败: {e}")
                        else:
                            df_preview = None
                    if df_preview is not None and not df_preview.empty:
                        st.write(f"数据量: {len(df_preview)} 行 × {len(df_preview.columns)} 列")
                        st.dataframe(df_preview.tail(10), use_container_width=True)
                    elif df_preview is None and api_ready:
                        pass  # Error already displayed above
    else:
        st.info("💡 请在上方勾选需要的数据指标", icon="ℹ️")

    # ── 合并导出 ───────────────────────────────────────────
    with st.container(border=True):
        st.markdown("#### ▶️ 合并导出")
        export_disabled = not ifind_catalog_selected
        if st.button(
            "🚀 下载合并后的月度数据",
            type="primary",
            disabled=export_disabled,
            use_container_width=True,
        ):
            with st.spinner("正在处理数据..."):
                if ifind_catalog_selected:
                    merged_df, meta = merge_ifind_selected(
                        ifind_catalog_selected,
                        access_token=ifind_token,
                        output_path="./output/ifind_merged.csv",
                        missing_value_threshold=missing_threshold,
                        start_date=ifind_start,
                        end_date=ifind_end,
                    )

                    if merged_df is not None:
                        st.success(f"✅ 合并完成！{merged_df.shape[0]} 行 × {merged_df.shape[1]} 列")
                        with open("./output/ifind_merged.csv", "rb") as f:
                            st.download_button(
                                label="⬇️ 下载 CSV",
                                data=f,
                                file_name="ifind_merged.csv",
                                mime="text/csv",
                                use_container_width=True,
                            )
                        st.dataframe(merged_df.tail(20), use_container_width=True)
                    else:
                        st.error("合并失败，请检查网络或选择的指标")

    st.caption("数据来源于同花顺 iFinD 数据接口")
