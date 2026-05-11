"""
Bank Prediction System - Streamlit Frontend

Usage:
    streamlit run app.py
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="银行预测数据处理系统", layout="wide")


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


# Page navigation
page = st.sidebar.radio("页面", ["本地数据处理", "AkShare 宏观数据同步"])

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
    "💡 **提示**：本地数据处理页：将数据文件放入 `raw_data` 文件夹中然后点击【开始处理】。"
    "AkShare 页：搜索并勾选需要的宏观数据指标，然后点击【下载合并后的月度数据】。"
)

if page == "本地数据处理":
    # ===== Main: Data Preparation =====
    st.title("🏦 银行预测数据处理系统")
    st.markdown("零命令行操作，放数据 → 点按钮 → 下载结果")

    data_dir = "./raw_data"
    output_dir = "./output"
    raw_path = Path(data_dir)

    st.header("📂 数据准备")

    col1, col2 = st.columns([2, 1])
    with col1:
        if raw_path.exists():
            files = find_data_files(data_dir)
            st.success(f"✅ 检测到 `{data_dir}` 目录，共 {len(files)} 个数据文件")
            for f in files:
                st.write(f"- `{f.relative_to('.')}`")
        else:
            st.warning(f"⚠️ 未检测到 `{data_dir}` 目录")
            st.info("请创建 `raw_data` 文件夹，并在其中建立 `daily`、`monthly`、`quarter` 子文件夹存放数据。")

    with col2:
        if st.button("📁 打开 raw_data 文件夹"):
            if raw_path.exists():
                open_folder(str(raw_path.resolve()))
            else:
                raw_path.mkdir(parents=True, exist_ok=True)
                (raw_path / "daily").mkdir(exist_ok=True)
                (raw_path / "monthly").mkdir(exist_ok=True)
                (raw_path / "quarter").mkdir(exist_ok=True)
                open_folder(str(raw_path.resolve()))
                st.rerun()

    # Preview data files
    if raw_path.exists():
        files = find_data_files(data_dir)
        if files:
            st.subheader("数据预览（前5行）")
            tabs = st.tabs([str(f.relative_to(".")) for f in files])
            for tab, f in zip(tabs, files):
                with tab:
                    df_preview = preview_csv(str(f), nrows=5)
                    if not df_preview.empty:
                        st.dataframe(df_preview, use_container_width=True)
                    else:
                        st.error("无法读取该文件，请检查格式")

    # ===== Main: Execution =====
    st.header("▶️ 运行处理")

    run_clicked = st.button("🚀 开始处理", type="primary", use_container_width=True)

    log_container = st.empty()

    if run_clicked:
        if not raw_path.exists() or not find_data_files(data_dir):
            st.error("❌ 没有找到数据文件，请先把数据放入 raw_data 目录")
            st.stop()

        # Build command
        cmd = [
            sys.executable, "main.py",
            "--data-dir", data_dir,
            "--output-dir", output_dir,
            "--missing-value-threshold", str(missing_threshold),
        ]

        logs = []
        with st.spinner("正在处理，请稍候..."):
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=".",
            )
            for line in process.stdout:
                logs.append(line)
                # Keep last 80 lines
                display = "".join(logs[-80:])
                log_container.text(display)
            process.wait()

        if process.returncode == 0:
            st.success("✅ 处理完成！")
        else:
            st.error(f"❌ 处理失败，返回码: {process.returncode}")

        # Show results
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
