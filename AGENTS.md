# AGENTS.md - BankPredictionSystem Data Processing

## Project Overview
This is a Jupyter Notebook-based bank prediction system for macroeconomics data. It performs:
1. **Data Cleaning** (`数据清理.ipynb`): Standardizes CSV headers, handles missing values, resamples time series
2. **Feature Engineering** (`特征工程_tsfresh版本.ipynb`): Extracts time series features using tsfresh, applies PCA dimensionality reduction

## Dependencies
- pandas
- numpy
- tsfresh
- scikit-learn

## Running the Notebooks

### Data Cleaning
```bash
# Open in Jupyter
jupyter notebook 数据清理.ipynb

# Or run via nbconvert
jupyter nbconvert --to notebook --execute 数据清理.ipynb
```

### Feature Engineering
```bash
jupyter notebook 特征工程_tsfresh版本.ipynb
jupyter nbconvert --to notebook --execute 特征工程_tsfresh版本.ipynb
```

## Code Style Guidelines

### Python Code in Notebooks
- **Imports**: Standard library first, then third-party (pandas, numpy, sklearn, tsfresh)
- **Naming**:
  - Functions: `snake_case` (e.g., `handle_spring_festival_split`)
  - Classes: `PascalCase` (e.g., `MockPaths`)
  - Variables: `snake_case`
- **Types**: Use type hints for function signatures (e.g., `df: pd.DataFrame`)
- **Error Handling**: Use try-except blocks with specific exception types
- **Logging**: Use Python's `logging` module with appropriate levels

### DataFrame Operations
- Use method chaining where possible
- Prefer `inplace=True` for mutations in notebook cells
- Handle encoding: try utf-8 first, fallback to gbk for Chinese data

### Feature Engineering
- Always apply `shift(1)` to prevent data leakage
- Use forward fill (`ffill`) for time series continuity
- Apply PCA after statistical significance filtering (fdr_level)

### Column Naming
- Convert to snake_case: `"GDP (Year-over-Year)"` → `gdp_year_over_year`
- Date column: standardize to `Date`
- Target variable: rename to `y`

## Data Structure
```
raw_data/
  daily/        - Daily frequency data
  monthly/      - Monthly frequency data
  quarterly/   - Quarterly frequency data
  target/       - Target variable

processed_data/
  daily/        - Resampled daily data
  monthly/      - Resampled monthly data
  quarterly/    - Resampled quarterly data
  target/       - Target variable

cleared_data/
  features_cleared.csv
  target_cleared.csv

result_train_data/
  train_set_pca.csv
```

## Common Tasks

### Adding New Data Processing
1. Add raw file to appropriate folder in `raw_data/`
2. Update file paths in the notebook
3. Ensure date column matches expected format

### Modifying Feature Extraction
- Adjust `max_timeshift` and `min_timeshift` in `roll_time_series()` call
- Modify `fdr_level` in `MockModelParams` for significance filtering

### Debugging
- Check intermediate outputs with `print()` statements
- Use `df.shape` to verify dimensions
- Use `df.head()` to preview data

## Output Files
- `cleared_data/features_cleared.csv` - Cleaned feature set
- `cleared_data/target_cleared.csv` - Cleaned target variable
- `result_train_data/train_set_pca.csv` - Final PCA-transformed training data

## Notebook Cell Structure

### Typical Cell Organization
1. **Imports cell**: All library imports at the top
2. **Configuration cell**: Mock config classes and settings
3. **Utility functions**: Helper functions for data processing
4. **Core processing functions**: Main ETL functions
5. **Execution cells**: Run the pipeline with actual data

### Mock Configuration Pattern
Use mock configuration classes to simulate production settings:
```python
class MockPaths:
    def __init__(self):
        self.base = Path("./processed_data")
        self.base.mkdir(exist_ok=True)

class MockModelParams:
    missing_value_threshold = 20.0
    fdr_level = 0.05

class MockSettings:
    paths = MockPaths()
    model_params = MockModelParams()
```

## Date Handling Conventions

### Supported Date Formats
- `"20-Jan"` (YY-MMM): Use `pd.to_datetime(..., format='%y-%b')`
- Numeric (YYYYMMM): Use `pd.to_datetime(..., format='%Y%m%d')`
- Standard formats: Fall back to `pd.to_datetime(..., errors='coerce')`

### Date Column Detection
Search for columns containing: `['date', 'time', '日期', '时间']`

### Resampling
- Daily data: Resample to monthly end (`'ME'`) with `.mean()`
- Quarterly data: Resample to monthly with `.asfreq()` then linear interpolate numeric columns
- Monthly data: Resample to monthly end with `.mean()`

## Feature Engineering Best Practices

### Time Series Feature Extraction (tsfresh)
- Use `EfficientFCParameters()` for balanced feature extraction
- Set `max_timeshift=6` and `min_timeshift=3` for 6-month lookback
- Always use `n_jobs=0` to disable multiprocessing (more stable in notebooks)

### Statistical Significance Filtering
- Use `select_features()` from tsfresh with `fdr_level` parameter
- Default FDR level: 0.05 (5% false discovery rate)
- This step is critical before PCA to remove noise

### PCA Transformation
- Always standardize data before PCA using `StandardScaler()`
- Limit components to min(95% variance, 80% of sample count)
- Use `n_components=0.95` to determine variance threshold first

### Data Leakage Prevention
- ALWAYS apply `shift(1)` to features before any processing
- Use `bfill()` after shift to handle initial NaN values
- Target variable should NOT be shifted

## Error Handling Patterns

### File Encoding
```python
try:
    df = pd.read_csv(input_path, encoding='utf-8')
except UnicodeDecodeError:
    df = pd.read_csv(input_path, encoding='gbk')
```

### Missing Value Handling
```python
# For features: forward fill then backward fill
df = df.ffill().bfill().fillna(0)

# For target: keep original values, no imputation
```

### Exception Types
- Use `ValueError` for invalid data values
- Use `FileNotFoundError` for missing files
- Use `KeyError` for missing DataFrame columns

## Logging and Output

### Logging Configuration
```python
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("ModuleName")
```

### Progress Indicators
- Use emoji prefixes for visual status: ✅ 🎉 🔄 ⏳ 💥 🧹 🧪
- Print shape information: `df.shape`
- Log intermediate results with clear messages

## Configuration Parameters

### Data Cleaning
| Parameter | Default | Description |
|-----------|---------|-------------|
| missing_value_threshold | 20.0 | Drop columns with >X% missing values |

### Feature Engineering
| Parameter | Default | Description |
|-----------|---------|-------------|
| fdr_level | 0.05 | False discovery rate for feature selection |
| max_timeshift | 6 | Maximum lookback months |
| min_timeshift | 3 | Minimum lookback months |

## Testing Guidelines

Since this is a notebook-based project without formal tests:
- Test functions individually in separate cells
- Use `print()` and `display()` to verify intermediate outputs
- Check DataFrame shapes after each transformation step
- Verify date parsing with `df['Date'].head()` before resampling
