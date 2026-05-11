# Bank Prediction System - 银行预测系统

宏观经济数据处理系统，用于处理多频率（日/月/季）时间序列数据并生成银行预测模型特征。

## 项目结构

```
BankPredictionSystem_ DataProcess/
├── main.py                 # 主入口文件
├── bank_pipeline/          # 核心模块
│   ├── config.py           # 配置类定义
│   ├── loader.py           # 数据加载器
│   ├── cleaner.py          # 数据清洗与合并
│   └── engineer.py         # 特征工程
├── raw_data/               # 原始数据目录
│   ├── daily/              # 日频数据
│   ├── monthly/            # 月频数据
│   └── quarter/            # 季频数据
└── output/                 # 输出目录
```

## 代码逻辑

### 整体流程

```
raw_data/ → DataLoader → DataCleaner → FeatureEngineer → output/
    ↓           ↓             ↓              ↓
  CSV/Excel   日期解析     重采样到月     tsfresh特征提取
  文件        频率检测     合并数据       FDR过滤 → PCA降维
```

### 1. DataLoader（数据加载器）

**文件**: `bank_pipeline/loader.py`

**功能**:
- 自动检测日期列（支持多种格式）
- 自动检测数据频率（日/月/季）
- 统一文件编码处理（UTF-8 → GBK）

**支持的日期格式**:
| 格式 | 示例 |
|------|------|
| `YY-MMM` | 23-Jan |
| `YYYY-MM-DD` | 2023-01-15 |
| `YYYYMMDD`（数字） | 20230115 |
| `YYYY年MM月` | 2023年1月 |

**频率检测逻辑**:
- 日频：相邻日期中位数差 ≤ 1 天
- 月频：相邻日期中位数差 28-31 天
- 季频：相邻日期中位数差 88-93 天

### 2. DataCleaner（数据清洗器）

**文件**: `bank_pipeline/cleaner.py`

**功能**:
- 缺失值处理：删除缺失率超过阈值（默认20%）的列
- 列名标准化：转换为 snake_case 格式
- 日期列重命名为 `Date`
- 统一重采样到月末（`ME`）
- 横向合并多个数据表

**重采样规则**:
| 原始频率 | 处理方式 |
|----------|----------|
| 日频 | 取月均值 |
| 月频 | 取月均值 |
| 季频 | 线性插值后取月频 |

### 3. FeatureEngineer（特征工程）

**文件**: `bank_pipeline/engineer.py`

**功能**:

#### 3.1 tsfresh 特征提取模式（默认）

```
1. shift(1) 防止数据泄露
2. 构建滚动窗口（lookback=6个月）
3. 使用 EfficientFCParameters 提取特征
4. FDR 显著性过滤（默认 FDR=0.05）
5. 删除高相关特征（相关系数>0.85）
6. PCA 降维（保留95%方差，最多80%样本数）
```

#### 3.2 简单模式（--no-tsfresh）

```
1. shift(1) 防止数据泄露
2. 按方差选择特征（限制 ≤60% 样本数）
```

#### 3.3 春节效应处理

当1月值为0/NaN但2月有值时，将2月值平分到1月和2月。

### 4. 数据泄露防护

**重要**: 所有特征在处理前必须应用 `shift(1)`，确保使用历史数据预测未来。

```python
df_features = df_features.shift(1).bfill().fillna(0)
```

目标变量（y）不进行 shift 处理。

## 使用方法

### 命令行

```bash
# 完整模式（使用tsfresh特征提取）
python main.py \
  --data-dir ./raw_data \
  --target-file ./target.csv \
  --target-col y \
  --output-dir ./output

# 简单模式（不使用tsfresh，限制特征比例）
python main.py \
  --data-dir ./raw_data \
  --target-file ./target.csv \
  --target-col y \
  --output-dir ./output \
  --no-tsfresh

# 自定义参数
python main.py \
  --data-dir ./raw_data \
  --target-file ./target.csv \
  --target-col y \
  --output-dir ./output \
  --fdr-level 0.01 \
  --max-timeshift 12 \
  --min-timeshift 6
```

### Python API

```python
from main import run_pipeline

# 完整模式
result, metadata = run_pipeline(
    data_dir="./raw_data",
    target_file="./target.csv",
    target_col="y",
    output_dir="./output",
    use_tsfresh=True,
    fdr_level=0.05
)

# 简单模式
result, metadata = run_pipeline(
    data_dir="./raw_data",
    target_file="./target.csv",
    target_col="y",
    output_dir="./output",
    use_tsfresh=False
)
```

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `missing_value_threshold` | 20.0 | 丢弃缺失率超过此值的列（%） |
| `fdr_level` | 0.05 | FDR显著性水平 |
| `max_timeshift` | 6 | 最大回看月数 |
| `min_timeshift` | 3 | 最小回看月数 |
| `pca_variance_threshold` | 0.95 | PCA保留方差比例 |
| `pca_max_ratio` | 0.8 | PCA主成分不超过样本数的此比例 |

## 输出文件

| 文件 | 说明 |
|------|------|
| `output/features_merged.csv` | 合并后的特征集（中间结果） |
| `output/train_pca.csv` | PCA变换后的最终训练数据（完整模式） |
| `output/train_no_pca.csv` | 未做PCA的特征（简单模式） |

## 依赖安装

```bash
pip install pandas numpy scikit-learn tsfresh openpyxl
```

## 数据格式要求

### 特征数据文件
- 支持格式：CSV、Excel（.xlsx/.xls）
- 必须包含日期列
- 放在 `--data-dir` 指定的目录中

### 目标变量文件
- 必须包含日期列和目标列
- 日期列会自动识别
- 目标列通过 `--target-col` 指定

## metadata 返回信息

```python
{
    "generated_features": 1000,      # tsfresh提取的特征数
    "significant_features": 150,      # FDR过滤后特征数
    "final_pca_features": 20,        # PCA降维后特征数
    "explained_variance": 0.96         # PCA解释方差比例
}
```
# BankPredictionSystem_-DataProcess
