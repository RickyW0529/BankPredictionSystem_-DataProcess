# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bank prediction system for macroeconomics data processing. The system processes time series data from multiple frequencies (daily, monthly, quarterly) and generates features for bank prediction models.

## Architecture

The codebase has two entry points:

1. **Python Pipeline** (`main.py` + `bank_pipeline/` module) - Production-ready pipeline
2. **Jupyter Notebooks** - Original notebooks for data cleaning and feature engineering

### Pipeline Modules (`bank_pipeline/`)

| File | Purpose |
|------|---------|
| `config.py` | Dataclass configuration (DataConfig, FeatureConfig, PipelineConfig, Settings) |
| `loader.py` | DataLoader class - universal file loading with auto date detection and frequency detection |
| `cleaner.py` | DataCleaner class - resampling, merging, missing value handling |
| `engineer.py` | FeatureEngineer class - tsfresh feature extraction, FDR filtering, PCA dimensionality reduction |

### Data Flow

```
raw_data/ → DataLoader → DataCleaner → FeatureEngineer → output/
     ↓           ↓             ↓              ↓
  CSV/Excel   Parse dates   Resample to   tsfresh features
  files       Detect freq   monthly       → FDR filter
                                          → PCA reduction
```

## Running the Pipeline

### Python API
```python
from main import run_pipeline

result, metadata = run_pipeline(
    data_dir="./raw_data",
    target_file="./target.csv",
    target_col="y",
    output_dir="./output",
    use_tsfresh=True,
    fdr_level=0.05
)
```

### Command Line
```bash
python main.py --data-dir ./raw_data --target-file ./target.csv --target-col y --output-dir ./output
python main.py --no-tsfresh --data-dir ./raw_data --target-file ./target.csv  # Skip tsfresh, use simple merge
```

### Notebooks
```bash
jupyter notebook 数据清理.ipynb
jupyter notebook 特征工程_tsfresh版本.ipynb
```

## Key Conventions

### Data Leakage Prevention
- **ALWAYS** apply `shift(1)` to features before any processing
- Use `bfill()` after shift to handle initial NaN values
- Target variable should NOT be shifted

### Date Handling
- Standardize date column to `Date`
- Supported formats: `YY-MMM`, `YYYY-MM-DD`, `YYYYMMDD` (numeric), `YYYY年MM月`
- Resample everything to monthly end (`'ME'`) for consistency

### File Encoding
- Try `utf-8` first, fallback to `gbk` for Chinese data

### Feature Engineering Pipeline
1. Extract features using `EfficientFCParameters()` with `tsfresh`
2. Apply FDR significance filtering (`fdr_level=0.05`)
3. Remove highly correlated features (>0.85 correlation)
4. Apply PCA (95% variance or 80% of sample count, whichever is smaller)

### Column Naming
- Convert to snake_case: `"GDP (Year-over-Year)"` → `gdp_year_over_year`
- Target variable renamed to `y`

## Output Files

| File | Description |
|------|-------------|
| `output/features_merged.csv` | Merged feature set before feature engineering |
| `output/train_pca.csv` | Final PCA-transformed training data |
| `output/train_no_pca.csv` | Features without PCA (when --no-tsfresh used) |

## Special Processing

### Spring Festival Effect (`engineer.py:handle_spring_festival_split`)
Handles Jan-Feb cumulative values that occur in Chinese macroeconomic data. When January value is 0/NaN but February has a value, splits February value evenly between both months.

### Frequency Detection (`loader.py:detect_frequency`)
- Daily: median diff ≤ 2 days
- Monthly: median diff 20-40 days
- Quarterly: median diff 80-100 days

## Configuration Defaults

| Parameter | Default | Description |
|-----------|---------|-------------|
| `missing_value_threshold` | 20.0 | Drop columns with >X% missing |
| `fdr_level` | 0.05 | False discovery rate for feature selection |
| `max_timeshift` | 6 | Maximum lookback months for tsfresh |
| `min_timeshift` | 3 | Minimum lookback months for tsfresh |
| `pca_variance_threshold` | 0.95 | Variance threshold for PCA |
| `pca_max_ratio` | 0.8 | Max PCA components as ratio of samples |
