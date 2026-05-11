"""
Bank Prediction System - Streamlit Frontend

Usage:
    streamlit run app.py
"""

from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="AkShare 宏观数据浏览器", layout="wide")

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
    "💡 **提示**：搜索并勾选需要的宏观数据指标，然后点击【下载合并后的月度数据】。"
)

# ===== Main: AkShare Macro Data =====
st.title("📡 AkShare 宏观数据同步")
st.markdown("从中国宏观数据库搜索、勾选、预览数据，一键合并导出")

from bank_pipeline.akshare_sync import search_macros, get_macro_data, merge_selected_macros, FREQ_MAP

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

cols_per_row = 2
for i in range(0, len(results), cols_per_row):
    row_items = results[i:i + cols_per_row]
    cols = st.columns(cols_per_row)
    for col, item in zip(cols, row_items):
        with col:
            checked = item["id"] in st.session_state.selected_macros
            freq_label = FREQ_MAP.get(item["freq"], item["freq"])
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
        st.dataframe(merged_df.tail(20), use_container_width=True)
    else:
        st.error("合并失败，请检查网络或选择的指标")

st.markdown("---")
st.caption("数据来源于 AkShare 开源财经数据接口")
