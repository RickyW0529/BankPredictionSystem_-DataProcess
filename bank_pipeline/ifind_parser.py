"""Robust parser for iFinD exported Excel/CSV files."""

import logging
from typing import Dict, List, Optional

import pandas as pd

from .loader import detect_frequency

logger = logging.getLogger(__name__)

IFIND_FREQ_MAP = {
    "日": "daily",
    "月": "monthly",
    "季": "quarterly",
    "年": "yearly",
    "周": "weekly",
}


def _detect_date_column_by_content(df: pd.DataFrame, threshold: float = 0.7) -> Optional[str]:
    """Detect date column by scanning cell contents.

    Skips leading metadata rows (those containing '频率' or '单位'),
    then checks each column. A column is considered a date column if
    >= threshold fraction of its non-empty values can be parsed as dates
    and there are at least 2 unique dates.

    To avoid misclassifying plain numbers as Unix timestamps, generic date
    parsing is only attempted when values contain date-like characters (-, /, 年, 月).
    """
    skip = 0
    for idx in range(min(3, len(df))):
        if _looks_like_metadata_row(df.iloc[idx]):
            skip += 1
        else:
            break

    data_df = df.iloc[skip:].copy() if skip > 0 else df.copy()
    if len(data_df) < 2:
        data_df = df.copy()

    for col in df.columns:
        series = data_df[col].astype(str).str.strip()
        non_empty = series[series != ""]
        if len(non_empty) < 2:
            continue

        # Try YYYYMMDD first (most common in iFinD exports)
        parsed = pd.to_datetime(non_empty, format="%Y%m%d", errors="coerce")
        valid_ratio = parsed.notna().sum() / len(non_empty)
        if valid_ratio >= threshold:
            unique_dates = parsed.dropna().unique()
            if len(unique_dates) >= 2:
                return col

        # Try Chinese date formats (e.g. 2026年01月, 2026年01月01日)
        for fmt in ("%Y年%m月", "%Y年%m月%d日"):
            parsed_cn = pd.to_datetime(non_empty, format=fmt, errors="coerce")
            valid_ratio_cn = parsed_cn.notna().sum() / len(non_empty)
            if valid_ratio_cn >= threshold:
                unique_dates = parsed_cn.dropna().unique()
                if len(unique_dates) >= 2:
                    return col

        # Fallback: generic date parsing, but only if values look like date strings
        # (contain -, /, or Chinese date characters) to avoid parsing plain numbers
        date_like = non_empty.str.contains(r"[-/年月]", regex=True, na=False)
        if date_like.sum() / len(non_empty) < threshold:
            continue

        parsed_generic = pd.to_datetime(non_empty, errors="coerce")
        valid_ratio_generic = parsed_generic.notna().sum() / len(non_empty)
        if valid_ratio_generic >= threshold:
            unique_dates = parsed_generic.dropna().unique()
            if len(unique_dates) >= 2:
                return col

    return None


def detect_date_column_ifind(df: pd.DataFrame) -> Optional[str]:
    """Auto-detect the date column in an iFinD DataFrame."""
    if "指标名称" in df.columns:
        return "指标名称"
    for col in df.columns:
        if col in ("日期", "date", "Date", "时间"):
            return col
    # Fallback: detect by content
    return _detect_date_column_by_content(df)


def parse_yyyymmdd_date(series: pd.Series) -> pd.Series:
    """Parse YYYYMMDD numeric strings to datetime."""
    return pd.to_datetime(series.astype(str).str.strip(), format="%Y%m%d", errors="coerce")


def _is_default_column_name(name: str) -> bool:
    """Check if a column name is a pandas default (Unnamed: N) or pure numeric."""
    if pd.isna(name):
        return True
    s = str(name).strip()
    if s.startswith("Unnamed:"):
        return True
    # Pure numeric like "0", "1", "0.0"
    try:
        float(s)
        return True
    except ValueError:
        pass
    return False


def fix_column_names(df: pd.DataFrame, date_col: Optional[str] = None) -> pd.DataFrame:
    """Fix default/auto-generated column names using first data row.

    If most column names look like pandas defaults (Unnamed: N) or are numeric,
    construct better names from the first data row.
    For non-default columns, optionally append the first-row value if it provides
    extra context (e.g. indicator description).
    """
    df = df.copy()
    cols = list(df.columns)
    default_count = sum(1 for c in cols if _is_default_column_name(c))

    # If more than half are default names, replace all with first data row
    if default_count > len(cols) // 2 and len(df) > 0:
        first_row = df.iloc[0]
        new_cols = []
        for i, c in enumerate(cols):
            val = first_row.iloc[i]
            val_str = str(val).strip() if pd.notna(val) else ""
            if val_str and val_str not in ("nan", "None", ""):
                new_cols.append(val_str)
            else:
                new_cols.append(f"col_{i}")
        df.columns = new_cols
        df = df.iloc[1:].reset_index(drop=True)
        return df

    # If only a few are default, fix just those (do NOT drop the first row
    # because non-default columns may contain real data there).
    if default_count > 0 and len(df) > 0:
        first_row = df.iloc[0]
        new_cols = []
        for i, c in enumerate(cols):
            if _is_default_column_name(c):
                val = first_row.iloc[i]
                val_str = str(val).strip() if pd.notna(val) else ""
                if val_str and val_str not in ("nan", "None", ""):
                    new_cols.append(val_str)
                else:
                    new_cols.append(f"col_{i}")
            else:
                new_cols.append(c)
        df.columns = new_cols

    return df


def filter_numeric_columns(
    df: pd.DataFrame,
    date_col: str,
    threshold: float = 0.5,
) -> List[str]:
    """Return only columns that are mostly numeric (suitable for time series).

    Parameters
    ----------
    df: DataFrame (already parsed, date column converted to datetime)
    date_col: name of the date column to exclude
    threshold: minimum fraction of non-null numeric values to keep a column

    Returns
    -------
    List of column names that pass the numeric filter.
    """
    numeric_cols = []
    for col in df.columns:
        if col == date_col:
            continue
        # Try to coerce to numeric
        numeric_series = pd.to_numeric(df[col], errors="coerce")
        valid_ratio = numeric_series.notna().sum() / len(df)
        if valid_ratio >= threshold:
            numeric_cols.append(col)
    return numeric_cols


def auto_parse_dataframe(df: pd.DataFrame) -> Dict:
    """Universal auto-parse any macro data DataFrame.

    Steps:
        1. Fix default column names
        2. Detect date column (by name or content)
        3. Detect and skip metadata rows
        4. Parse dates
        5. Filter to numeric columns only
        6. Detect frequency

    Returns dict with same keys as parse_ifind_excel.
    """
    df = df.copy()

    # Step 1: fix column names if they look auto-generated
    df = fix_column_names(df)

    # Step 2: detect date column
    date_col = detect_date_column_ifind(df)
    if date_col is None:
        raise ValueError("No date column found. Expected '指标名称' or similar.")

    # Step 3: detect metadata
    metadata_rows = _count_metadata_rows(df)
    freq = extract_frequency_from_metadata(df)
    unit = extract_unit_from_metadata(df)

    if metadata_rows > 0:
        df = df.iloc[metadata_rows:].reset_index(drop=True)

    # Step 4: parse dates with multiple format attempts
    df[date_col] = parse_yyyymmdd_date(df[date_col])
    if df[date_col].isna().all():
        # Try generic parsing
        df[date_col] = pd.to_datetime(df[date_col].astype(str).str.strip(), errors="coerce")
    df = df.dropna(subset=[date_col])

    # Step 5: filter to numeric columns
    data_cols = filter_numeric_columns(df, date_col)
    if not data_cols:
        raise ValueError("No numeric data columns found after parsing.")

    # Keep only date + numeric data columns
    df = df[[date_col] + data_cols].copy()
    for col in data_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Step 6: detect frequency if not from metadata
    if freq == "unknown" and len(df) >= 2:
        freq = detect_frequency(df, date_col)

    return {
        "date_col": date_col,
        "data_cols": data_cols,
        "freq": freq,
        "unit": unit,
        "data": df,
        "metadata_rows": metadata_rows,
    }


def _looks_like_metadata_row(row: pd.Series) -> bool:
    """Check if a row contains metadata keywords."""
    values = [str(v).strip() for v in row.dropna().tolist()]
    return any(v in ("频率", "单位") for v in values)


def extract_frequency_from_metadata(df: pd.DataFrame) -> str:
    """Extract frequency from iFinD metadata rows."""
    for idx in range(min(3, len(df))):
        row = df.iloc[idx]
        values = [str(v).strip() for v in row.tolist()]
        if "频率" in values:
            for v in values:
                if v in IFIND_FREQ_MAP:
                    return IFIND_FREQ_MAP[v]
    return "unknown"


def extract_unit_from_metadata(df: pd.DataFrame) -> Optional[str]:
    """Extract unit from iFinD metadata rows."""
    for idx in range(min(3, len(df))):
        row = df.iloc[idx]
        values = [str(v).strip() for v in row.tolist()]
        if "单位" in values:
            for i, v in enumerate(values):
                if v == "单位" and i + 1 < len(values):
                    unit = values[i + 1]
                    if unit and unit not in ("nan", "None"):
                        return unit
            for v in values:
                if v not in ("单位", "指标名称", "频率") and v not in IFIND_FREQ_MAP:
                    return v
    return None


def _count_metadata_rows(df: pd.DataFrame) -> int:
    """Count leading metadata rows to skip."""
    count = 0
    for idx in range(min(3, len(df))):
        if _looks_like_metadata_row(df.iloc[idx]):
            count += 1
        else:
            break
    return count


def parse_ifind_excel(df: pd.DataFrame) -> Dict:
    """Parse an iFinD DataFrame and auto-detect structure.

    Returns dict with keys:
        - date_col: str
        - data_cols: List[str]
        - freq: str
        - unit: Optional[str]
        - data: pd.DataFrame (cleaned, with parsed dates)
        - metadata_rows: int
    """
    df = df.copy()

    date_col = detect_date_column_ifind(df)
    if date_col is None:
        raise ValueError("No date column found. Expected '指标名称' or similar.")

    metadata_rows = _count_metadata_rows(df)
    freq = extract_frequency_from_metadata(df)
    unit = extract_unit_from_metadata(df)

    if metadata_rows > 0:
        df = df.iloc[metadata_rows:].reset_index(drop=True)

    df[date_col] = parse_yyyymmdd_date(df[date_col])
    df = df.dropna(subset=[date_col])

    # Filter to numeric columns only (skip text/category columns)
    data_cols = filter_numeric_columns(df, date_col)

    if freq == "unknown" and len(df) >= 2:
        freq = detect_frequency(df, date_col)

    for col in data_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Keep only date + numeric data columns
    df = df[[date_col] + data_cols].copy()

    return {
        "date_col": date_col,
        "data_cols": data_cols,
        "freq": freq,
        "unit": unit,
        "data": df,
        "metadata_rows": metadata_rows,
    }
