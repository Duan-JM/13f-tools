# 开发指南

## 🛠️ 开发环境搭建

### 1. 环境要求

- Python 3.8+
- Poetry (推荐) 或 pip
- Git

### 2. 克隆和安装

```bash
# 克隆项目
git clone https://github.com/your-repo/ValueAnalyze.git
cd ValueAnalyze/13f-tools

# 使用Poetry安装
poetry install
```

### 3. 配置开发环境

```bash
# 复制配置文件
cp config.ini.example config.ini

# 编辑配置文件
vim config.ini
```

**配置文件示例:**
```ini
[fetcher]
company_name = YourCompany Research
email = your-email@company.com
request_delay = 0.2
max_retries = 3
timeout = 30
```

## 🏗️ 项目结构

```
13f-tools/
├── src/sec13f_analyzer/        # 源代码
│   ├── __init__.py            # 包初始化
│   ├── models.py              # 数据模型
│   ├── data_fetcher.py        # 数据获取
│   ├── analyzer.py            # 分析引擎
│   ├── visualizer.py          # 可视化
│   ├── exporter.py            # 数据导出
│   ├── cli.py                 # 命令行接口
│   └── config.py              # 配置管理
├── tests/                     # 测试代码
│   ├── test_*.py              # 单元测试
│   ├── conftest.py            # 测试配置
│   └── test_data/             # 测试数据
├── docs/                      # 文档
├── examples.py                # 使用示例
├── pyproject.toml             # Poetry配置
├── pytest.ini                # 测试配置
└── README.md                  # 项目说明
```

## 🧪 测试开发

### 运行测试

```bash
# 运行所有测试
poetry run pytest

# 运行测试并查看覆盖率
poetry run pytest --cov=src/sec13f_analyzer --cov-report=term-missing

# 运行特定测试模块
poetry run pytest tests/test_analyzer.py -v

# 运行特定测试函数
poetry run pytest tests/test_analyzer.py::test_get_holdings -v
```

### 测试结构

```python
# tests/test_analyzer.py
import pytest
from unittest.mock import Mock, patch
from sec13f_analyzer import SEC13FAnalyzer
from sec13f_analyzer.models import Holdings, Holding

class TestSEC13FAnalyzer:
    @pytest.fixture
    def analyzer(self):
        """创建测试用的分析器实例"""
        return SEC13FAnalyzer(
            company_name="Test Company",
            email="test@example.com"
        )
    
    @pytest.fixture
    def sample_holdings(self):
        """创建测试用的持仓数据"""
        holdings = [
            Holding(
                issuer_name="Apple Inc",
                cusip="037833100",
                market_value=1000000,
                shares_or_principal=1000,
                # ... 其他字段
            )
        ]
        return Holdings(
            fund_name="Test Fund",
            cik="0001234567",
            quarter="2024Q3",
            holdings=holdings,
            total_value=1000000
        )
    
    def test_get_holdings(self, analyzer, sample_holdings):
        """测试获取持仓数据"""
        with patch.object(analyzer.data_fetcher, 'get_13f_data') as mock_fetch:
            mock_fetch.return_value = sample_holdings
            
            result = analyzer.get_holdings("0001234567", "2024Q3")
            
            assert result.fund_name == "Test Fund"
            assert len(result.holdings) == 1
            assert result.total_value == 1000000
```

### Mock数据创建

```python
# tests/conftest.py
import pytest
from datetime import datetime
from sec13f_analyzer.models import Holdings, Holding

@pytest.fixture
def sample_holding():
    """创建样本持仓记录"""
    return Holding(
        issuer_name="Apple Inc",
        title_of_class="COM",
        cusip="037833100",
        market_value=1000000,
        shares_or_principal=1000,
        investment_discretion="SOLE",
        voting_authority="SOLE",
        sole_voting_power=1000,
        shared_voting_power=0,
        no_voting_power=0
    )

@pytest.fixture
def sample_holdings(sample_holding):
    """创建样本持仓集合"""
    return Holdings(
        fund_name="Test Fund",
        cik="0001234567",
        quarter="2024Q3",
        period_end_date=datetime(2024, 9, 30),
        holdings=[sample_holding],
        total_value=1000000
    )
```

## 🔧 模块开发

### 1. 添加新的分析功能

在 `analyzer.py` 中添加新方法：

```python
class SEC13FAnalyzer:
    def calculate_sector_allocation(self, cik: str, quarter: str) -> Dict[str, float]:
        """计算行业配置"""
        holdings = self.get_holdings(cik, quarter)
        
        # 实现行业分类逻辑
        sector_allocation = {}
        for holding in holdings.holdings:
            sector = self._get_sector(holding.cusip)  # 需要实现
            if sector in sector_allocation:
                sector_allocation[sector] += holding.market_value
            else:
                sector_allocation[sector] = holding.market_value
        
        # 转换为百分比
        total_value = holdings.total_value
        return {sector: (value / total_value) * 100 
                for sector, value in sector_allocation.items()}
    
    def _get_sector(self, cusip: str) -> str:
        """根据CUSIP获取行业分类"""
        # 实现行业分类逻辑，可能需要外部数据源
        pass
```

对应的测试：

```python
def test_calculate_sector_allocation(self, analyzer, sample_holdings):
    """测试行业配置计算"""
    with patch.object(analyzer, '_get_sector') as mock_sector:
        mock_sector.return_value = "Technology"
        
        result = analyzer.calculate_sector_allocation("0001234567", "2024Q3")
        
        assert "Technology" in result
        assert result["Technology"] == 100.0  # 只有一个科技股
```

### 2. 添加新的可视化功能

在 `visualizer.py` 中添加：

```python
class HoldingsVisualizer:
    def plot_sector_allocation(self, sector_data: Dict[str, float]) -> None:
        """绘制行业配置图"""
        import matplotlib.pyplot as plt
        
        sectors = list(sector_data.keys())
        percentages = list(sector_data.values())
        
        plt.figure(figsize=(10, 6))
        plt.pie(percentages, labels=sectors, autopct='%1.1f%%')
        plt.title('投资组合行业配置')
        plt.show()
```

### 3. 添加新的导出格式

在 `exporter.py` 中添加：

```python
class DataExporter:
    def export_to_pdf(self, holdings: Holdings, filepath: str = None) -> str:
        """导出PDF报告"""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        if not filepath:
            filepath = f"{holdings.fund_name}_{holdings.quarter}_report.pdf"
        
        c = canvas.Canvas(filepath, pagesize=letter)
        
        # 添加标题
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 750, f"{holdings.fund_name} - {holdings.quarter} 持仓报告")
        
        # 添加内容...
        c.save()
        
        return filepath
```

## 🔄 CLI扩展

### 添加新的CLI命令

在 `cli.py` 中添加：

```python
@cli.command()
@click.option('--cik', '-c', required=True, help='基金CIK编号')
@click.option('--quarter', '-q', required=True, help='季度')
@click.pass_context
def sector(ctx, cik, quarter):
    """分析投资组合行业配置"""
    user_agent = ctx.obj['user_agent']
    
    try:
        analyzer = SEC13FAnalyzer(user_agent)
        sector_allocation = analyzer.calculate_sector_allocation(cik, quarter)
        
        click.echo(f"\n{quarter} 行业配置分析:")
        click.echo("-" * 50)
        for sector, percentage in sorted(sector_allocation.items(), 
                                       key=lambda x: x[1], reverse=True):
            click.echo(f"{sector:<20} {percentage:>6.1f}%")
            
    except Exception as e:
        logger.error(f"行业配置分析失败: {e}")
        sys.exit(1)
```

## 📊 配置管理

### 扩展配置项

在 `config.py` 中添加新的配置节：

```python
class Config:
    def get_sector_config(self) -> dict:
        """获取行业分类配置"""
        return {
            'data_source': self.config.get('sector', 'data_source', fallback='internal'),
            'cache_duration': self.config.getint('sector', 'cache_duration', fallback=86400),
            'api_key': self.config.get('sector', 'api_key', fallback=''),
        }
```

在 `config.ini` 中添加：

```ini
[sector]
data_source = sic_mapping
cache_duration = 86400
api_key = your_api_key_here
```

## 🚨 错误处理

### 自定义异常

```python
# 在 models.py 或单独的 exceptions.py 中
class SectorAnalysisError(SEC13FError):
    """行业分析异常"""
    pass

class DataSourceError(SEC13FError):
    """数据源异常"""
    pass
```

### 异常处理装饰器

```python
# utils.py
import functools
from loguru import logger

def handle_api_errors(func):
    """API错误处理装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败: {e}")
            raise DataFetchError(f"网络请求失败: {e}")
        except Exception as e:
            logger.error(f"未知错误: {e}")
            raise SEC13FError(f"未知错误: {e}")
    return wrapper

# 使用装饰器
class SEC13FDataFetcher:
    @handle_api_errors
    def get_13f_data(self, cik: str, quarter: str) -> Optional[Holdings]:
        # 实现...
        pass
```

## 📝 文档更新

### 代码文档

```python
def calculate_sector_allocation(self, cik: str, quarter: str) -> Dict[str, float]:
    """
    计算投资组合的行业配置。
    
    Args:
        cik: 基金的CIK编号
        quarter: 分析季度，格式为 "YYYYQN"
        
    Returns:
        Dict[str, float]: 行业名称到百分比的映射
        
    Raises:
        DataFetchError: 数据获取失败
        SectorAnalysisError: 行业分析失败
        
    Example:
        >>> analyzer = SEC13FAnalyzer()
        >>> sectors = analyzer.calculate_sector_allocation("0001067983", "2024Q3")
        >>> print(sectors)
        {'Technology': 45.2, 'Financial': 23.1, 'Healthcare': 15.7}
    """
```

### API文档更新

在 `docs/api-reference.md` 中添加新方法的文档。

### README更新

在主README中添加新功能的使用示例。

## 🔧 性能优化

### 1. 缓存机制

```python
import functools
from typing import Optional
import pickle
import os

def cache_result(cache_dir: str = "cache", expire_hours: int = 24):
    """结果缓存装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存key
            cache_key = f"{func.__name__}_{hash(str(args) + str(kwargs))}"
            cache_file = os.path.join(cache_dir, f"{cache_key}.pkl")
            
            # 检查缓存
            if os.path.exists(cache_file):
                mtime = os.path.getmtime(cache_file)
                if time.time() - mtime < expire_hours * 3600:
                    with open(cache_file, 'rb') as f:
                        return pickle.load(f)
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            os.makedirs(cache_dir, exist_ok=True)
            with open(cache_file, 'wb') as f:
                pickle.dump(result, f)
            
            return result
        return wrapper
    return decorator
```

### 2. 异步处理

```python
import asyncio
import aiohttp
from typing import List

class AsyncSEC13FDataFetcher:
    """异步数据获取器"""
    
    async def fetch_multiple_quarters(self, cik: str, quarters: List[str]) -> List[Holdings]:
        """异步获取多个季度的数据"""
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_quarter_async(session, cik, quarter) 
                    for quarter in quarters]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        return [r for r in results if not isinstance(r, Exception)]
    
    async def _fetch_quarter_async(self, session: aiohttp.ClientSession, 
                                  cik: str, quarter: str) -> Holdings:
        """异步获取单个季度数据"""
        # 实现异步HTTP请求...
        pass
```

## 🔍 调试工具

### 调试配置

```python
# debug.py
import logging
from loguru import logger

def setup_debug_logging():
    """设置调试日志"""
    logger.remove()
    logger.add(
        "debug.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        rotation="1 MB"
    )
    logger.add(
        lambda msg: print(msg, end=""),
        level="INFO",
        colorize=True
    )

def debug_holdings(holdings: Holdings):
    """调试持仓数据"""
    logger.debug(f"基金: {holdings.fund_name}")
    logger.debug(f"CIK: {holdings.cik}")
    logger.debug(f"季度: {holdings.quarter}")
    logger.debug(f"持仓数量: {len(holdings.holdings)}")
    logger.debug(f"总价值: ${holdings.total_value:,.0f}")
    
    # 显示前5个持仓
    for i, holding in enumerate(holdings.holdings[:5]):
        logger.debug(f"  {i+1}. {holding.issuer_name}: ${holding.market_value:,.0f}")
```

### 性能分析

```python
import time
import functools

def timing(func):
    """性能计时装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logger.info(f"{func.__name__} 执行时间: {end - start:.2f}秒")
        return result
    return wrapper

# 使用
@timing
def get_holdings(self, cik: str, quarter: str) -> Holdings:
    # 实现...
    pass
```

## 📦 构建和发布

### 构建包

```bash
# 使用Poetry构建
poetry build

# 生成的文件在 dist/ 目录
ls dist/
# sec13f_analyzer-0.1.0-py3-none-any.whl
# sec13f_analyzer-0.1.0.tar.gz
```

### 发布到PyPI

```bash
# 配置PyPI凭据
poetry config pypi-token.pypi your-token-here

# 发布
poetry publish
```

### 版本管理

```bash
# 更新版本号
poetry version patch    # 0.1.0 -> 0.1.1
poetry version minor    # 0.1.1 -> 0.2.0
poetry version major    # 0.2.0 -> 1.0.0
```

## 🤝 贡献流程

### 1. Fork和分支

```bash
# Fork项目并克隆
git clone https://github.com/your-username/ValueAnalyze.git
cd ValueAnalyze/13f-tools

# 创建功能分支
git checkout -b feature/sector-analysis
```

### 2. 开发和测试

```bash
# 安装开发依赖
poetry install --with dev

# 运行测试
poetry run pytest

# 代码格式化
poetry run black src/ tests/
poetry run isort src/ tests/

# 类型检查
poetry run mypy src/
```

### 3. 提交和推送

```bash
# 提交更改
git add .
git commit -m "feat: 添加行业配置分析功能"

# 推送分支
git push origin feature/sector-analysis
```

### 4. 创建Pull Request

在GitHub上创建Pull Request，包含：
- 清晰的功能描述
- 测试结果截图
- 相关文档更新

## 📋 代码规范

### Python代码风格

- 使用Black进行代码格式化
- 使用isort整理导入
- 遵循PEP 8规范
- 类型注解覆盖率 > 90%

### 提交信息规范

```
type(scope): description

body

footer
```

类型包括：
- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建和工具

这个开发指南涵盖了从环境搭建到贡献代码的完整流程，为开发者提供了详细的指导。
