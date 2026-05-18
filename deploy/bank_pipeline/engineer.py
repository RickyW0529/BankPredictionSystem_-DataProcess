from typing import Tuple, Dict, Optional
from pathlib import Path

import pandas as pd
import numpy as np
import logging
import warnings

from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


def handle_spring_festival_split(df: pd.DataFrame) -> pd.DataFrame:
    """Handle spring festival effect: split Jan-Feb cumulative values."""
    df = df.sort_index()
    numeric_cols = df.select_dtypes(include=['number']).columns
    split_count = 0
    
    for col in numeric_cols:
        years = df.index.year.unique()
        for year in years:
            try:
                idx_jan = pd.Timestamp(f'{year}-01-01')
                idx_feb = pd.Timestamp(f'{year}-02-01')
                if idx_jan in df.index and idx_feb in df.index:
                    val_jan = df.at[idx_jan, col]
                    val_feb = df.at[idx_feb, col]
                    if (pd.isna(val_jan) or val_jan == 0) and (pd.notna(val_feb) and val_feb != 0):
                        split_val = val_feb / 2
                        df.at[idx_jan, col] = split_val
                        df.at[idx_feb, col] = split_val
                        split_count += 1
            except:
                continue
    
    if split_count > 0:
        logger.info(f"🧧 Spring festival effect: split {split_count} Jan-Feb cumulative values")
    return df


class FeatureEngineer:
    """Feature engineering with tsfresh and PCA."""
    
    def __init__(
        self,
        fdr_level: float = 0.05,
        max_timeshift: int = 6,
        min_timeshift: int = 3,
        pca_variance_threshold: float = 0.95,
        pca_max_ratio: float = 0.8
    ):
        self.fdr_level = fdr_level
        self.max_timeshift = max_timeshift
        self.min_timeshift = min_timeshift
        self.pca_variance_threshold = pca_variance_threshold
        self.pca_max_ratio = pca_max_ratio
    
    def process(
        self,
        df_features: pd.DataFrame,
        df_target: pd.DataFrame,
        target_col: str = 'y',
        output_dir: Optional[str] = None
    ) -> Tuple[pd.DataFrame, Dict]:
        """Main feature engineering pipeline."""
        logger.info("🚀 Starting feature engineering: [Extract -> Filter -> PCA]")
        
        if 'Date' in df_features.columns:
            df_features = df_features.set_index('Date')
        df_features.index = pd.to_datetime(df_features.index)
        df_features.index.name = 'Date'
        
        df_features = handle_spring_festival_split(df_features)
        
        df_features = df_features.dropna(axis=1, how='all')
        df_features = df_features.ffill().bfill().fillna(0)
        
        logger.info("🔄 Applying shift(1) to prevent data leakage...")
        original_index = df_features.index
        df_shifted = df_features.shift(1).bfill().fillna(0)
        
        df_input = df_shifted.reset_index(drop=True)
        df_input['Date'] = original_index
        df_input['id'] = 'macro_series'
        
        logger.info("⏳ Building rolling windows (lookback=6)...")
        try:
            from tsfresh import extract_features
            from tsfresh.utilities.dataframe_functions import roll_time_series, impute
            from tsfresh.feature_extraction import EfficientFCParameters
        except ImportError:
            raise ImportError("tsfresh is required. Install with: pip install tsfresh scikit-learn")
        
        df_rolled = roll_time_series(
            df_input,
            column_id='id',
            column_sort='Date',
            max_timeshift=self.max_timeshift,
            min_timeshift=self.min_timeshift
        )
        
        logger.info("💥 Extracting features (EfficientFCParameters)...")
        extracted_features = extract_features(
            df_rolled,
            column_id='id',
            column_sort='Date',
            default_fc_parameters=EfficientFCParameters(),
            n_jobs=0,
            disable_progressbar=False
        )
        
        extracted_features.index = extracted_features.index.droplevel(0)
        extracted_features.index.name = 'Date'
        impute(extracted_features)
        
        logger.info(f"   📊 Initial features: {extracted_features.shape[1]}")
        
        if 'Date' in df_target.columns:
            df_target = df_target.set_index('Date')
        df_target.index = pd.to_datetime(df_target.index)
        
        if target_col not in df_target.columns:
            raise ValueError(f"Target column '{target_col}' not found. Available: {list(df_target.columns)}")
        
        y = df_target[target_col]
        master_df = y.to_frame().join(extracted_features, how='inner')
        y = master_df[target_col]
        X = master_df.drop(columns=[target_col])
        
        logger.info("🧹 Step 1: FDR significance filtering...")
        from tsfresh import select_features
        X_filtered = select_features(X, y, fdr_level=self.fdr_level)
        logger.info(f"   📉 Significant features: {X_filtered.shape[1]}")
        
        logger.info("🧪 Step 1.5: Removing highly correlated features...")
        corr_matrix = X_filtered.corr().abs()
        upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        to_drop = [column for column in upper.columns if any(upper[column] > 0.85)]
        X_filtered = X_filtered.drop(columns=to_drop)
        logger.info(f"   📉 After correlation filter: {X_filtered.shape[1]} features (dropped {len(to_drop)})")
        
        logger.info("🧪 Step 2: PCA dimensionality reduction...")
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_filtered)
        
        n_samples = len(X_filtered)
        max_components = int(n_samples * self.pca_max_ratio)
        if max_components < 2:
            max_components = 2
        
        pca_test = PCA(n_components=self.pca_variance_threshold)
        pca_test.fit(X_scaled)
        n_95_variance = pca_test.n_components_
        
        final_n_components = min(max_components, n_95_variance)
        logger.info(f"   🎯 Final PCA components: {final_n_components}")
        
        pca = PCA(n_components=final_n_components)
        X_pca = pca.fit_transform(X_scaled)
        
        pca_cols = [f"PCA_{i+1}" for i in range(final_n_components)]
        df_pca = pd.DataFrame(X_pca, columns=pca_cols, index=X_filtered.index)
        
        explained_variance = np.sum(pca.explained_variance_ratio_)
        logger.info(f"   ℹ️ Explained variance: {explained_variance:.2%}")
        
        final_df = pd.concat([df_pca, y], axis=1)
        
        metadata = {
            "generated_features": extracted_features.shape[1],
            "significant_features": X_filtered.shape[1],
            "final_pca_features": final_df.shape[1] - 1,
            "explained_variance": explained_variance
        }

        if output_dir:
            output_path = Path(output_dir) / "train_pca.csv"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            final_df.to_csv(output_path)
            logger.info(f"✅ Saved to {output_path}")
            metadata["output_file"] = str(output_path)

        logger.info(f"✅ Complete. Final shape: {final_df.shape}")
        return final_df, metadata
    
    def process_simple(
        self,
        df_features: pd.DataFrame,
        df_target: pd.DataFrame,
        target_col: str = 'y',
        output_dir: Optional[str] = None
    ) -> Tuple[pd.DataFrame, Dict]:
        """Simple feature engineering without tsfresh (basic stats only)."""
        logger.info("🚀 Starting simple feature engineering")
        
        if 'Date' in df_features.columns:
            df_features = df_features.set_index('Date')
        df_features.index = pd.to_datetime(df_features.index)
        
        df_shifted = df_features.shift(1).bfill().fillna(0)
        
        if 'Date' in df_target.columns:
            df_target = df_target.set_index('Date')
        
        y = df_target[target_col]
        final_df = pd.concat([df_shifted, y], axis=1)
        
        metadata = {"method": "simple", "features": df_shifted.shape[1]}

        if output_dir:
            output_path = Path(output_dir) / "train_simple.csv"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            final_df.to_csv(output_path)
            logger.info(f"✅ Saved to {output_path}")
            metadata["output_file"] = str(output_path)

        return final_df, metadata

    def process_no_pca(
        self,
        df_features: pd.DataFrame,
        df_target: pd.DataFrame,
        target_col: str = 'y',
        max_feature_ratio: float = 0.6,
        output_dir: Optional[str] = None
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Feature engineering without PCA/tsfresh.
        Features are limited to <60% of sample count to prevent overfitting.
        """
        logger.info("🚀 Starting feature engineering: [No PCA/tsfresh, Feature Ratio < 60%]")
        
        if 'Date' in df_features.columns:
            df_features = df_features.set_index('Date')
        df_features.index = pd.to_datetime(df_features.index)
        
        df_shifted = df_features.shift(1).bfill().fillna(0)
        
        if 'Date' in df_target.columns:
            df_target = df_target.set_index('Date')
        df_target.index = pd.to_datetime(df_target.index)
        
        y = df_target[target_col]
        
        master_df = y.to_frame().join(df_shifted, how='inner')
        y = master_df[target_col]
        X = master_df.drop(columns=[target_col])
        
        n_samples = len(X)
        max_features = int(n_samples * max_feature_ratio)
        
        logger.info(f"   📊 Samples: {n_samples}, Max allowed features: {max_features} ({max_feature_ratio:.0%})")
        
        if X.shape[1] <= max_features:
            final_df = pd.concat([X, y], axis=1)
            logger.info(f"   ✅ Using all {X.shape[1]} features (within 60% limit)")
        else:
            logger.info(f"   📉 Selecting top {max_features} features by variance...")
            
            variances = X.var()
            top_features = variances.nlargest(max_features).index.tolist()
            X_selected = X[top_features]
            
            final_df = pd.concat([X_selected, y], axis=1)
            logger.info(f"   ✅ Selected {len(top_features)} features by variance")
        
        metadata = {
            "method": "no_pca",
            "original_features": df_shifted.shape[1],
            "final_features": final_df.shape[1] - 1,
            "n_samples": n_samples,
            "max_feature_ratio": max_feature_ratio
        }

        if output_dir:
            output_path = Path(output_dir) / "train_no_pca.csv"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            final_df.to_csv(output_path)
            logger.info(f"✅ Saved to {output_path}")
            metadata["output_file"] = str(output_path)

        logger.info(f"✅ Complete. Final shape: {final_df.shape}")
        return final_df, metadata
