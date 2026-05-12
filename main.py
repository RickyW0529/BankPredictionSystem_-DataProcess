"""
Bank Prediction Pipeline - Unified Entry Point

Usage:
    from main import run_pipeline
    
    result = run_pipeline(
        data_dir="./your_data_folder",
        target_file="./target.csv",
        target_col="y",
        output_dir="./output"
    )
"""

import argparse
import logging
from pathlib import Path
from typing import Optional, List, Tuple

import pandas as pd

from bank_pipeline.config import Settings
from bank_pipeline.loader import DataLoader
from bank_pipeline.cleaner import DataCleaner
from bank_pipeline.engineer import FeatureEngineer


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)


def detect_target_frequency(df: pd.DataFrame) -> str:
    """Detect target data frequency."""
    if 'Date' not in df.columns:
        return 'monthly'
    dates = pd.to_datetime(df['Date'], errors='coerce').dropna()
    if len(dates) < 2:
        return 'monthly'
    diffs = dates.sort_values().diff().dropna()
    median_diff = diffs.median().days
    if median_diff <= 1:
        return 'daily'
    elif 28 <= median_diff <= 31:
        return 'monthly'
    elif 88 <= median_diff <= 93:
        return 'quarterly'
    return 'monthly'


def run_pipeline(
    data_dir: Optional[str] = None,
    data_list: Optional[List[Tuple[pd.DataFrame, str, str]]] = None,
    target_file: Optional[str] = None,
    target_col: str = "y",
    output_dir: str = "./output",
    use_tsfresh: bool = True,
    missing_value_threshold: float = 20.0,
    fdr_level: float = 0.05,
    max_timeshift: int = 6,
    min_timeshift: int = 3,
    save_intermediate: bool = True,
    max_feature_ratio: float = 0.6
):
    """
    Run the complete pipeline: load -> clean -> merge -> feature engineering.

    Args:
        data_dir: Directory containing feature data files (CSV/Excel)
        target_file: Path to target variable file (CSV/Excel). If None, only merge features.
        target_col: Name of target column in target file
        output_dir: Directory to save output files
        use_tsfresh: Whether to use tsfresh for feature extraction (True) or simple merge (False)
        missing_value_threshold: Drop columns with >X% missing values
        fdr_level: False discovery rate for feature selection
        max_timeshift: Maximum lookback months for tsfresh
        min_timeshift: Minimum lookback months for tsfresh
        save_intermediate: Whether to save intermediate merged features
        max_feature_ratio: Max features as ratio of sample count (default 0.6 = 60%)

    Returns:
        Tuple of (final DataFrame, metadata dict)
    """
    settings = Settings(
        output_dir=output_dir,
        missing_value_threshold=missing_value_threshold,
        fdr_level=fdr_level,
        max_timeshift=max_timeshift,
        min_timeshift=min_timeshift
    )

    logger.info("=" * 50)
    logger.info("🏦 Bank Prediction Pipeline Started")
    logger.info("=" * 50)

    logger.info("📂 Step 1: Loading data...")

    loader = DataLoader(date_columns=settings.pipeline.data_config.date_columns)

    if data_list is None:
        if data_dir is None:
            raise ValueError("Either data_dir or data_list must be provided")
        data_list = loader.load_directory(data_dir, recursive=True)

    logger.info(f"   Loaded {len(data_list)} feature files")

    logger.info("🧹 Step 2: Cleaning and merging...")
    cleaner = DataCleaner(missing_value_threshold=settings.pipeline.data_config.missing_value_threshold)
    df_features = cleaner.merge_dataframes(data_list)
    logger.info(f"   Merged features shape: {df_features.shape}")

    if save_intermediate or target_file is None:
        output_path = Path(output_dir) / "features_merged.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_features.to_csv(output_path, index=False)
        logger.info(f"   💾 Saved merged features to {output_path}")

    if target_file is None:
        logger.info("=" * 50)
        logger.info("✅ Merge-only mode complete!")
        logger.info("=" * 50)
        return df_features, {"mode": "merge_only", "shape": df_features.shape}

    logger.info("📊 Step 3: Loading target variable...")
    target_df, target_date_col = loader.load_file(target_file)
    target_df = cleaner.clean_dataframe(target_df, target_date_col)
    target_df = cleaner.resample_to_monthly(target_df, detect_target_frequency(target_df))

    if target_col not in target_df.columns:
        target_df = target_df.rename(columns={target_df.columns[1]: target_col})

    logger.info(f"   Target shape: {target_df.shape}")

    logger.info("⚙️  Step 4: Feature engineering...")
    engineer = FeatureEngineer(
        fdr_level=settings.pipeline.feature_config.fdr_level,
        max_timeshift=settings.pipeline.feature_config.max_timeshift,
        min_timeshift=settings.pipeline.feature_config.min_timeshift,
        pca_variance_threshold=settings.pipeline.feature_config.pca_variance_threshold,
        pca_max_ratio=settings.pipeline.feature_config.pca_max_ratio
    )

    if use_tsfresh:
        final_df, metadata = engineer.process(
            df_features=df_features,
            df_target=target_df,
            target_col=target_col,
            output_dir=output_dir
        )
    else:
        final_df, metadata = engineer.process_no_pca(
            df_features=df_features,
            df_target=target_df,
            target_col=target_col,
            max_feature_ratio=max_feature_ratio,
            output_dir=output_dir
        )

    logger.info("=" * 50)
    logger.info("✅ Pipeline Complete!")
    logger.info(f"   Final shape: {final_df.shape}")
    logger.info("=" * 50)

    return final_df, metadata


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(description="Bank Prediction Pipeline")
    parser.add_argument("--data-dir", required=True, help="Directory containing feature files")
    parser.add_argument("--target-file", default=None, help="Path to target variable file (omit for merge-only mode)")
    parser.add_argument("--target-col", default="y", help="Target column name")
    parser.add_argument("--output-dir", default="./output", help="Output directory")
    parser.add_argument("--no-tsfresh", action="store_true", help="Skip tsfresh, use simple merge with feature ratio limit")
    parser.add_argument("--fdr-level", type=float, default=0.05, help="FDR level for feature selection")
    parser.add_argument("--max-timeshift", type=int, default=6, help="Max lookback months")
    parser.add_argument("--min-timeshift", type=int, default=3, help="Min lookback months")
    parser.add_argument("--max-feature-ratio", type=float, default=0.6, help="Max feature to sample ratio (default 0.6)")
    parser.add_argument("--missing-value-threshold", type=float, default=20.0, help="Drop columns with >X%% missing values (default 20.0)")

    args = parser.parse_args()

    run_pipeline(
        data_dir=args.data_dir,
        target_file=args.target_file,
        target_col=args.target_col,
        output_dir=args.output_dir,
        use_tsfresh=not args.no_tsfresh,
        fdr_level=args.fdr_level,
        max_timeshift=args.max_timeshift,
        min_timeshift=args.min_timeshift,
        max_feature_ratio=args.max_feature_ratio,
        missing_value_threshold=args.missing_value_threshold
    )


if __name__ == "__main__":
    main()
