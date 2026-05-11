from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class DataConfig:
    missing_value_threshold: float = 20.0
    date_columns: List[str] = field(default_factory=lambda: [
        'date', 'time', '日期', '时间', '指标名称',
        'DATA_DATE', 'trans_month', 'stat_month', 'trans_date', 'stat_date'
    ])
    supported_extensions: List[str] = field(default_factory=lambda: ['.csv', '.xlsx', '.xls'])


@dataclass
class FeatureConfig:
    fdr_level: float = 0.05
    max_timeshift: int = 6
    min_timeshift: int = 3
    pca_variance_threshold: float = 0.95
    pca_max_ratio: float = 0.8


@dataclass
class PipelineConfig:
    data_config: DataConfig = field(default_factory=DataConfig)
    feature_config: FeatureConfig = field(default_factory=FeatureConfig)
    output_dir: Path = field(default_factory=lambda: Path("./output"))
    log_level: str = "INFO"


@dataclass
class Settings:
    def __init__(self, **kwargs):
        self.pipeline = PipelineConfig()
        if 'output_dir' in kwargs:
            self.pipeline.output_dir = Path(kwargs['output_dir'])
        if 'missing_value_threshold' in kwargs:
            self.pipeline.data_config.missing_value_threshold = kwargs['missing_value_threshold']
        if 'fdr_level' in kwargs:
            self.pipeline.feature_config.fdr_level = kwargs['fdr_level']
        if 'max_timeshift' in kwargs:
            self.pipeline.feature_config.max_timeshift = kwargs['max_timeshift']
        if 'min_timeshift' in kwargs:
            self.pipeline.feature_config.min_timeshift = kwargs['min_timeshift']
        
        self.pipeline.output_dir.mkdir(parents=True, exist_ok=True)
