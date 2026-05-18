import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd



def generate_clean_column_name(col_name: str) -> str:
    """Convert column name to clean snake_case format."""
    clean_name = col_name.lower().strip()
    clean_name = re.sub(r'[\s\(\)\-./]+', '_', clean_name)
    return clean_name.strip('_')


def _read_broken_xlsx(file_path_or_buffer) -> pd.DataFrame:
    """Read xlsx workbook with invalid XML (e.g. corrupted styles.xml) by manually parsing sheet XML.

    Supports both file path (str) and file-like objects (BytesIO).
    """
    with zipfile.ZipFile(file_path_or_buffer, 'r') as z:
        shared_strings = []
        try:
            with z.open('xl/sharedStrings.xml') as f:
                sst = ET.parse(f).getroot()
                ns_tag = sst.tag
                if ns_tag.startswith('{'):
                    ns_uri = ns_tag.split('}')[0][1:]
                    ns = {'x': ns_uri}
                    for si in sst.findall('.//x:si', ns):
                        t = si.find('.//x:t', ns)
                        shared_strings.append(t.text if t is not None else '')
                else:
                    for si in sst.findall('.//si'):
                        t = si.find('.//t')
                        shared_strings.append(t.text if t is not None else '')
        except KeyError:
            pass

        with z.open('xl/worksheets/sheet1.xml') as f:
            tree = ET.parse(f)
            root = tree.getroot()

            ns_tag = root.tag
            if ns_tag.startswith('{'):
                ns_uri = ns_tag.split('}')[0][1:]
                ns = {'x': ns_uri}
                row_tag = 'x:row'
                c_tag = 'x:c'
                v_tag = 'x:v'
            else:
                ns = {}
                row_tag = 'row'
                c_tag = 'c'
                v_tag = 'v'

            data = defaultdict(dict)
            for row in root.findall(f'.//{row_tag}', ns):
                row_idx = int(row.get('r'))
                for cell in row.findall(f'.//{c_tag}', ns):
                    cell_ref = cell.get('r')
                    col_letters = ''.join([c for c in cell_ref if c.isalpha()])
                    col_idx = 0
                    for c in col_letters:
                        col_idx = col_idx * 26 + (ord(c) - ord('A') + 1)

                    cell_type = cell.get('t', 'n')
                    v_elem = cell.find(v_tag, ns)
                    val = v_elem.text if v_elem is not None else ''

                    if cell_type == 's':
                        idx = int(val) if val else 0
                        val = shared_strings[idx] if 0 <= idx < len(shared_strings) else ''
                    elif cell_type == 'str':
                        val = val
                    elif cell_type == 'n':
                        val = float(val) if val else None

                    data[row_idx][col_idx] = val

            max_row = max(data.keys()) if data else 0
            max_col = max(max(cols.keys()) for cols in data.values()) if data else 0

            result = []
            for r in range(1, max_row + 1):
                row_data = []
                for c in range(1, max_col + 1):
                    row_data.append(data[r].get(c, None))
                result.append(row_data)

    df = pd.DataFrame(result[1:], columns=result[0])
    # Drop duplicate columns, keeping only the first occurrence
    df = df.loc[:, ~df.columns.duplicated(keep='first')]
    return df


def safe_read_excel(file_path_or_buffer, **kwargs) -> pd.DataFrame:
    """Read Excel with automatic fallback to manual XML parsing for corrupted styles.xml."""
    try:
        return pd.read_excel(file_path_or_buffer, **kwargs)
    except Exception:
        # Reset buffer position for file-like objects
        if hasattr(file_path_or_buffer, 'seek'):
            file_path_or_buffer.seek(0)
        return _read_broken_xlsx(file_path_or_buffer)


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

    if series_str.str.match(r'^\d{8}$').any():
        return pd.to_datetime(series_str, format='%Y%m%d', errors='coerce')

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
    
    if median_diff <= 2:
        return 'daily'
    elif 20 <= median_diff <= 40:
        return 'monthly'
    elif 80 <= median_diff <= 100:
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
                try:
                    df = pd.read_excel(file_path)
                except Exception:
                    if path.suffix == '.xlsx':
                        df = _read_broken_xlsx(file_path)
                    else:
                        raise
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
