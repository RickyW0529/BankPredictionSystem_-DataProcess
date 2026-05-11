import re
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd



def generate_clean_column_name(col_name: str) -> str:
    """Convert column name to clean snake_case format."""
    clean_name = col_name.lower().strip()
    clean_name = re.sub(r'[\s\(\)\-./]+', '_', clean_name)
    return clean_name.strip('_')


def detect_date_column(df: pd.DataFrame, date_keywords: List[str]) -> Optional[str]:
    """Auto-detect date column from DataFrame."""
    for col in df.columns:
        col_lower = col.lower().strip()
        if col_lower in date_keywords:
            return col
        for keyword in date_keywords:
            if keyword.lower() in col_lower:
                return col
    return None


def parse_date_column(series: pd.Series) -> pd.Series:
    """Parse date column with multiple format support."""
    series_str = series.astype(str)
    
    if series_str.str.match(r'\d{2}-[A-Za-z]{3}').all():
        return pd.to_datetime(series_str, format='%y-%b', errors='coerce')
    
    if series_str.str.match(r'\d{4}-\d{2}-\d{2}').all():
        return pd.to_datetime(series_str, errors='coerce')
    
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_datetime(series.astype(str), format='%Y%m%d', errors='coerce')
    
    if series_str.str.match(r'\d{4}年\d{1,2}月').any():
        return pd.to_datetime(series_str.str.replace('年', '-').str.replace('月', ''), errors='coerce')
    
    return pd.to_datetime(series_str, errors='coerce')


def detect_frequency(df: pd.DataFrame, date_col: str) -> str:
    """Detect data frequency (daily/monthly/quarterly)."""
    if date_col not in df.columns:
        return 'unknown'
    
    dates = pd.to_datetime(df[date_col], errors='coerce').dropna()
    if len(dates) < 2:
        return 'unknown'
    
    diffs = dates.sort_values().diff().dropna()
    median_diff = diffs.median().days
    
    if median_diff <= 1:
        return 'daily'
    elif 28 <= median_diff <= 31:
        return 'monthly'
    elif 88 <= median_diff <= 93:
        return 'quarterly'
    else:
        return 'unknown'


class DataLoader:
    """Universal data loader with auto date detection."""
    
    def __init__(self, date_columns: List[str]):
        self.date_columns = date_columns
    
    def load_file(self, file_path: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """Load a single file and return DataFrame with date column identified."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            if path.suffix == '.csv':
                try:
                    df = pd.read_csv(file_path, encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, encoding='gbk')
            elif path.suffix in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")
        except Exception as e:
            raise RuntimeError(f"Failed to load {file_path}: {e}")
        
        date_col = detect_date_column(df, self.date_columns)
        if date_col is None:
            raise ValueError(f"No date column found in {file_path}. Available columns: {list(df.columns)}")
        
        df[date_col] = parse_date_column(df[date_col])
        df.dropna(subset=[date_col], inplace=True)
        df = df.sort_values(date_col)
        
        freq = detect_frequency(df, date_col)
        
        return df, date_col
    
    def load_directory(self, directory: str, recursive: bool = False) -> List[Tuple[pd.DataFrame, str, str]]:
        """Load all supported files from a directory."""
        path = Path(directory)
        if not path.is_dir():
            raise NotADirectoryError(f"Directory not found: {directory}")
        
        pattern = "**/*" if recursive else "*"
        files = []
        for ext in ['.csv', '.xlsx', '.xls']:
            files.extend(path.glob(f"{pattern}{ext}"))
        
        results = []
        for f in files:
            try:
                df, date_col = self.load_file(str(f))
                freq = detect_frequency(df, date_col)
                results.append((df, date_col, freq))
            except Exception as e:
                print(f"⚠️ Skip {f.name}: {e}")
        
        return results
