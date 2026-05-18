from pathlib import Path

import pandas as pd
import pytest

from bank_pipeline.loader import DataLoader

TESTS_DIR = Path(__file__).parent


@pytest.mark.parametrize(
    "filename, expected_freq, expected_shape_min",
    [
        ("日度宏观数据_20260518_134443.xlsx", "daily", (100, 2)),
        ("月度宏观数据_20260518_134527.xlsx", "monthly", (50, 2)),
        ("季度宏观数据_20260518_134602.xlsx", "quarterly", (10, 2)),
    ],
)
def test_load_broken_xlsx(filename, expected_freq, expected_shape_min):
    """DataLoader should fall back to manual XML parsing when openpyxl fails."""
    file_path = TESTS_DIR / filename
    loader = DataLoader(date_columns=["指标名称", "date", "日期"])
    df, date_col = loader.load_file(str(file_path))

    assert isinstance(df, pd.DataFrame)
    assert df.shape[0] >= expected_shape_min[0]
    assert df.shape[1] >= expected_shape_min[1]
    assert date_col == "指标名称"

    # Date column should be parsed and the "指标ID" row dropped
    assert df[date_col].notna().all()
    assert pd.api.types.is_datetime64_any_dtype(df[date_col])

    # Detected frequency should match expected
    from bank_pipeline.loader import detect_frequency
    freq = detect_frequency(df, date_col)
    assert freq == expected_freq
