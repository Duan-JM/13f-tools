# API 参考文档

## 📚 SEC13FAnalyzer - 主分析器

### 类初始化

```python
class SEC13FAnalyzer:
    def __init__(self, user_agent: str = None, company_name: str = None, email: str = None)
```

**参数说明:**
- `user_agent`: 自定义User-Agent字符串
- `company_name`: 公司名称（用于生成User-Agent）
- `email`: 联系邮箱（用于生成User-Agent）

**示例:**
```python
# 使用默认配置
analyzer = SEC13FAnalyzer()

# 自定义配置
analyzer = SEC13FAnalyzer(
    company_name="ValueAnalyze Research",
    email="research@valueanalyze.com"
)
```

### 核心方法

#### `get_holdings(cik: str, quarter: str) -> Holdings`

获取指定基金在指定季度的持仓数据。

**参数:**
- `cik`: 基金的CIK编号（如 "0001067983"）
- `quarter`: 季度字符串（如 "2024Q3"）

**返回:** `Holdings` 对象包含完整持仓信息

**示例:**
```python
holdings = analyzer.get_holdings("0001067983", "2024Q3")
print(f"基金名称: {holdings.fund_name}")
print(f"总持仓价值: ${holdings.total_value:,.0f}")
print(f"持仓数量: {len(holdings.holdings)}")
```

#### `analyze_holdings_changes(cik: str, from_quarter: str, to_quarter: str) -> HoldingsChange`

分析两个季度之间的持仓变动。

**参数:**
- `cik`: 基金CIK编号
- `from_quarter`: 起始季度
- `to_quarter`: 结束季度

**返回:** `HoldingsChange` 对象包含变动分析

**示例:**
```python
changes = analyzer.analyze_holdings_changes("0001067983", "2024Q2", "2024Q3")
print(f"新增持仓: {len(changes.new_positions)}")
print(f"清仓持仓: {len(changes.closed_positions)}")
print(f"总价值变动: ${changes.total_value_change:,.0f}")
```

#### `get_top_holdings(cik: str, quarter: str, top_n: int = 10) -> List[Holding]`

获取前N大持仓。

**参数:**
- `cik`: 基金CIK编号
- `quarter`: 季度
- `top_n`: 返回前N个持仓，默认10

**返回:** 按市值排序的持仓列表

**示例:**
```python
top_10 = analyzer.get_top_holdings("0001067983", "2024Q3", 10)
for i, holding in enumerate(top_10, 1):
    print(f"{i}. {holding.issuer_name}: ${holding.market_value:,.0f}")
```

#### `calculate_concentration(cik: str, quarter: str) -> Dict[str, float]`

计算投资组合集中度指标。

**返回字典键:**
- `top_5_percentage`: 前5大持仓占比
- `top_10_percentage`: 前10大持仓占比
- `top_20_percentage`: 前20大持仓占比
- `herfindahl_index`: 赫芬达尔指数

**示例:**
```python
concentration = analyzer.calculate_concentration("0001067983", "2024Q3")
print(f"前10大持仓占比: {concentration['top_10_percentage']:.1f}%")
print(f"赫芬达尔指数: {concentration['herfindahl_index']:.0f}")
```

#### `find_common_holdings(ciks: List[str], quarter: str, min_funds: int = 2) -> List[Dict]`

查找多个基金的共同持仓。

**参数:**
- `ciks`: 基金CIK列表
- `quarter`: 分析季度
- `min_funds`: 最少持有该股票的基金数量

**返回:** 共同持仓信息列表

**示例:**
```python
common = analyzer.find_common_holdings([
    "0001067983",  # 伯克希尔
    "0001166559",  # 桥水
    "0001364742"   # 先锋
], "2024Q3", min_funds=2)

for holding in common[:10]:
    print(f"{holding['issuer_name']}: {holding['holding_funds_count']} 个基金持有")
```

## 📊 数据模型

### Holding - 单个持仓记录

```python
@dataclass
class Holding:
    issuer_name: str           # 发行人名称
    title_of_class: str        # 证券类别
    cusip: str                 # CUSIP标识符
    market_value: float        # 市场价值（美元）
    shares_or_principal: int   # 持有股数
    investment_discretion: str # 投资决策权
    voting_authority: str      # 投票权描述
    sole_voting_power: int     # 独有投票权股数
    shared_voting_power: int   # 共享投票权股数
    no_voting_power: int       # 无投票权股数
```

**示例使用:**
```python
for holding in holdings.holdings:
    print(f"股票: {holding.issuer_name}")
    print(f"CUSIP: {holding.cusip}")
    print(f"市值: ${holding.market_value:,.0f}")
    print(f"股数: {holding.shares_or_principal:,}")
```

### Holdings - 持仓集合

```python
@dataclass
class Holdings:
    fund_name: str                  # 基金名称
    cik: str                       # CIK编号
    quarter: str                   # 季度
    period_end_date: datetime      # 期末日期
    holdings: List[Holding]        # 持仓列表
    total_value: float            # 总持仓价值
    
    @property
    def holdings_count(self) -> int:
        return len(self.holdings)
```

### HoldingChange - 持仓变动记录

```python
@dataclass
class HoldingChange:
    issuer_name: str      # 发行人名称
    cusip: str           # CUSIP标识符
    change_type: str     # 变动类型: 'new', 'closed', 'increased', 'decreased'
    prev_value: float    # 之前价值
    curr_value: float    # 当前价值
    value_change: float  # 价值变动
    prev_shares: int     # 之前股数
    curr_shares: int     # 当前股数
    shares_change: int   # 股数变动
```

### HoldingsChange - 持仓变动集合

```python
@dataclass
class HoldingsChange:
    fund_name: str                      # 基金名称
    cik: str                           # CIK编号
    from_quarter: str                  # 起始季度
    to_quarter: str                    # 结束季度
    total_prev_value: float            # 期初总价值
    total_curr_value: float            # 期末总价值
    total_value_change: float          # 总价值变动
    total_percentage_change: float     # 总变动百分比
    new_positions: List[HoldingChange]      # 新增持仓
    closed_positions: List[HoldingChange]   # 清仓持仓
    increased_positions: List[HoldingChange] # 增持
    decreased_positions: List[HoldingChange] # 减持
```

## 🔍 SEC13FDataFetcher - 数据获取器

### 初始化

```python
class SEC13FDataFetcher:
    def __init__(self, company_name: str = None, email: str = None)
```

### 核心方法

#### `search_fund_cik(fund_name: str) -> List[Tuple[str, str]]`

根据基金名称搜索CIK编号。

**返回:** (CIK, 基金名称) 元组列表

**示例:**
```python
fetcher = SEC13FDataFetcher()
results = fetcher.search_fund_cik("Berkshire")
for cik, name in results:
    print(f"CIK: {cik}, 名称: {name}")
```

#### `get_fund_info(cik: str) -> Optional[FundInfo]`

获取基金基本信息。

**示例:**
```python
fund_info = fetcher.get_fund_info("0001067983")
if fund_info:
    print(f"基金名称: {fund_info.fund_name}")
    print(f"业务地址: {fund_info.business_address}")
```

#### `get_13f_filings(cik: str, years: int = 3) -> List[Dict]`

获取基金的13F报告列表。

**返回:** 包含报告信息的字典列表

**示例:**
```python
filings = fetcher.get_13f_filings("0001067983", years=2)
for filing in filings[:5]:
    print(f"季度: {filing['quarter']}, 日期: {filing['filing_date']}")
```

## 📈 HoldingsVisualizer - 可视化器

### 静态图表方法

#### `plot_holdings_distribution(holdings: Holdings, chart_type: str = "pie", top_n: int = 10)`

绘制持仓分布图。

**参数:**
- `chart_type`: "pie" 或 "bar"
- `top_n`: 显示前N个持仓

#### `plot_holdings_changes(holdings_change: HoldingsChange)`

绘制持仓变动图。

#### `plot_portfolio_value_trend(historical_data: Dict[str, Holdings])`

绘制投资组合价值趋势。

**示例:**
```python
visualizer = HoldingsVisualizer()

# 持仓分布饼图
visualizer.plot_holdings_distribution(holdings, "pie", 10)

# 持仓变动图
visualizer.plot_holdings_changes(changes)

# 价值趋势图
historical = {
    "2024Q1": analyzer.get_holdings("0001067983", "2024Q1"),
    "2024Q2": analyzer.get_holdings("0001067983", "2024Q2"),
    "2024Q3": analyzer.get_holdings("0001067983", "2024Q3")
}
visualizer.plot_portfolio_value_trend(historical)
```

### 交互式图表方法

#### `create_interactive_dashboard(holdings: Holdings)`

创建交互式仪表板。

#### `create_interactive_pie_chart(holdings: Holdings) -> str`

创建交互式饼图，返回HTML字符串。

## 💾 DataExporter - 数据导出器

### 导出方法

#### `export_holdings_to_excel(holdings: Holdings, filepath: str = None) -> str`

导出持仓数据到Excel。

**示例:**
```python
exporter = DataExporter()
filepath = exporter.export_holdings_to_excel(holdings, "berkshire_2024q3.xlsx")
print(f"已导出到: {filepath}")
```

#### `export_holdings_changes_to_excel(changes: HoldingsChange, filepath: str = None) -> str`

导出持仓变动到Excel。

#### `export_to_csv(data: Union[Holdings, HoldingsChange], filepath: str = None) -> str`

导出到CSV格式。

#### `export_to_json(data: Union[Holdings, HoldingsChange], filepath: str = None) -> str`

导出到JSON格式。

#### `create_summary_report(holdings_list: List[Holdings], filepath: str = None) -> str`

创建多季度汇总报告。

**示例:**
```python
quarters_data = [
    analyzer.get_holdings("0001067983", "2024Q1"),
    analyzer.get_holdings("0001067983", "2024Q2"),
    analyzer.get_holdings("0001067983", "2024Q3")
]
filepath = exporter.create_summary_report(quarters_data, "summary_2024.xlsx")
```

## ⚙️ 配置管理

### Config 类

```python
class Config:
    def __init__(self, config_file: str = "config.ini")
    
    def get_fetcher_config(self) -> dict
    def get_visualization_config(self) -> dict  
    def get_export_config(self) -> dict
```

**配置文件示例 (config.ini):**
```ini
[fetcher]
company_name = ValueAnalyze Research
email = research@valueanalyze.com
request_delay = 0.2
max_retries = 3
timeout = 30

[visualization]
style = seaborn
figure_size = 12,8
color_palette = Set2

[export]
default_format = xlsx
include_charts = true
```

## 🚨 异常处理

### 自定义异常

```python
class SEC13FError(Exception):
    """SEC 13F分析工具基础异常"""
    pass

class DataFetchError(SEC13FError):
    """数据获取异常"""
    pass

class ParseError(SEC13FError):
    """数据解析异常"""  
    pass

class ValidationError(SEC13FError):
    """数据验证异常"""
    pass
```

### 异常处理示例

```python
try:
    holdings = analyzer.get_holdings("0001067983", "2024Q3")
except DataFetchError as e:
    print(f"数据获取失败: {e}")
except ParseError as e:
    print(f"数据解析失败: {e}")
except SEC13FError as e:
    print(f"分析工具错误: {e}")
```

## 🔒 最佳实践

### 1. 请求频率控制

```python
# 推荐配置
config = {
    'request_delay': 0.2,  # 每个请求间隔0.2秒
    'max_retries': 3,      # 最多重试3次
    'timeout': 30          # 请求超时30秒
}
```

### 2. 错误处理

```python
def safe_get_holdings(analyzer, cik, quarter, max_attempts=3):
    """安全获取持仓数据"""
    for attempt in range(max_attempts):
        try:
            return analyzer.get_holdings(cik, quarter)
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            print(f"第{attempt + 1}次尝试失败: {e}")
            time.sleep(2 ** attempt)  # 指数退避
```

### 3. 内存管理

```python
# 处理大量数据时
def process_multiple_quarters(analyzer, cik, quarters):
    """分批处理多个季度数据"""
    results = []
    for quarter in quarters:
        holdings = analyzer.get_holdings(cik, quarter)
        # 处理数据...
        results.append(holdings)
        # 清理不需要的对象
        del holdings
    return results
```

### 4. 配置管理

```python
# 推荐的初始化方式
def create_analyzer():
    """创建配置好的分析器"""
    config = Config()
    fetcher_config = config.get_fetcher_config()
    
    return SEC13FAnalyzer(
        company_name=fetcher_config['company_name'],
        email=fetcher_config['email']
    )
```

这个API参考文档提供了完整的接口说明和使用示例，帮助开发者快速上手和深入使用SEC 13F分析工具。
