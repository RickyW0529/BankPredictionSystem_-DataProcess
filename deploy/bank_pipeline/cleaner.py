from typing import List, Tuple, Optional
from pathlib import Path

import pandas as pd
import logging

from .loader import generate_clean_column_name

logger = logging.getLogger(__name__)


class DataCleaner:
    """Data cleaning and merging module."""
    
    def __init__(self, missing_value_threshold: float = 20.0):
        self.missing_value_threshold = missing_value_threshold
    
    def clean_dataframe(self, df: pd.DataFrame, date_col: str) -> pd.DataFrame:
        """Clean a single DataFrame: standardize columns, handle missing values."""
        df = df.copy()
        
        missing_pct = (df.isnull().sum() / len(df)) * 100
        cols_to_drop = missing_pct[missing_pct >= self.missing_value_threshold].index.tolist()
        if cols_to_drop:
            df.drop(columns=cols_to_drop, inplace=True)
            logger.info(f"Dropped {len(cols_to_drop)} columns with >{self.missing_value_threshold}% missing values")
        
        new_mapper = {date_col: 'Date'}
        df.rename(columns=new_mapper, inplace=True)

        return df
    
    def resample_to_monthly(self, df: pd.DataFrame, freq: str) -> pd.DataFrame:
        """Resample data to monthly end frequency."""
        df = df.set_index('Date')
        df = df.sort_index()

        # Convert all non-date columns to numeric (coerce errors to NaN)
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        if freq == 'daily':
            last_date = df.index[-1]
            df = df.resample('ME').mean()
            if not last_date.is_month_end:
                df = df.iloc[:-1]
        elif freq == 'quarterly':
            df = df.resample('ME').mean()
            numeric_cols = df.select_dtypes(include=['number']).columns
            df[numeric_cols] = df[numeric_cols].interpolate(method='linear')
        elif freq == 'monthly':
            df = df.resample('ME').mean()
        else:
            logger.warning(f"Unknown frequency: {freq}, trying monthly resample")
            df = df.resample('ME').mean()

        df = df.reset_index()
        return df
    
    def merge_dataframes(self, data_list: List[Tuple[pd.DataFrame, str, str]]) -> pd.DataFrame:
        """Merge multiple DataFrames by Date using outer join."""
        if not data_list:
            raise ValueError("No data to merge")

        suffix_map = {'daily': '日度', 'monthly': '月度', 'quarterly': '季度'}

        processed = []
        for df, date_col, freq in data_list:
            df = self.clean_dataframe(df, date_col)
            df = self.resample_to_monthly(df, freq)
            suffix = suffix_map.get(freq, '')
            if suffix:
                rename_map = {c: f"{c}_{suffix}" for c in df.columns if c != 'Date'}
                df = df.rename(columns=rename_map)
            processed.append(df)

        if len(processed) == 1:
            return processed[0]

        merged = processed[0].set_index('Date')
        for df in processed[1:]:
            df_indexed = df.set_index('Date')
            merged = merged.join(df_indexed, how='outer')

        merged = merged.reset_index()
        merged.ffill(inplace=True)
        merged.bfill(inplace=True)

        logger.info(f"Merged {len(processed)} files into {merged.shape}")
        return merged
    
    def save_merged_features(self, df: pd.DataFrame, output_path: str) -> str:
        """Save merged features to CSV."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        logger.info(f"Saved merged features to {path}")
        return str(path)
