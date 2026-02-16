# SEC 13F持仓分析工具 📊

一个专业的SEC 13F报告分析工具，专注于机构投资者持仓变动追踪和深度分析。通过命令行界面，轻松获取和分析美国机构投资者的持仓数据。

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)
[![Poetry](https://img.shields.io/badge/Poetry-managed-success)](https://python-poetry.org)
[![Tests](https://img.shields.io/badge/Tests-84%25%20coverage-green)](https://pytest.org)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

## ✨ 核心功能

- � **基金搜索**: 根据基金名称快速查找CIK编号
- 📊 **持仓获取**: 实时获取SEC 13F报告持仓数据
- 📈 **变动分析**: 精确追踪季度间持仓变化
- 📋 **数据导出**: 支持Excel、CSV、JSON多种格式
- 🏦 **多基金比较**: 横向比较不同机构投资策略
- � **综合报告**: 生成多季度汇总分析报告

## 📦 快速安装

### 环境要求

- Python 3.8+
- Poetry (推荐) 或 pip

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/ValueAnalyze.git
cd ValueAnalyze/13f-tools

# 2. 使用Poetry安装 (推荐)
poetry install

# 3. 验证安装
poetry run sec13f-cli --help
```

## 🚀 CLI使用指南

### 1. 搜索基金CIK

```bash
# 搜索伯克希尔哈撒韦
poetry run sec13f-cli search --fund-name "Berkshire"

# 搜索桥水基金
poetry run sec13f-cli search --fund-name "Bridgewater"

# 搜索先锋集团
poetry run sec13f-cli search --fund-name "Vanguard"
```

**输出示例:**

```
找到 10 个匹配的基金:
------------------------------------------------------------
CIK: 0001067983
名称: BERKSHIRE HATHAWAY INC
------------------------------------------------------------
```

### 2. 获取基金信息

```bash
# 获取伯克希尔哈撒韦基本信息
poetry run sec13f-cli info --cik 0001067983 --quarter 2024Q3
```

**输出示例:**

```
基金基本信息:
  CIK编号: 0001067983
  基金名称: BERKSHIRE HATHAWAY INC
  业务地址: 3555 FARNAM STREET OMAHA NE 68131

2024Q3 持仓概况:
  报告期末: 2024-09-30
  总持仓价值: $279,969,100,000
  持仓股票数量: 129

持仓集中度:
  前5大持仓占比: 56.2%
  前10大持仓占比: 78.1%
  赫芬达尔指数: 892
```

## 🔄 13F-HR/A 修订处理

本工具支持智能处理SEC 13F-HR/A修订报告，根据修订类型自动选择正确的数据处理策略：

### 修订类型说明

#### 1. RESTATEMENT（完全重述）
- **含义**: 完全替换原始13F-HR报告的所有数据
- **处理**: 使用最新的RESTATEMENT修订数据，忽略原始13F-HR
- **示例**: 发现原始报告有重大错误，需要重新提交所有持仓数据

#### 2. NEW HOLDINGS（新增持仓）
- **含义**: 在原始报告基础上添加遗漏的持仓条目
- **处理**: 将NEW HOLDINGS中的持仓合并到原始13F-HR数据
- **示例**: 遗漏了某些股票持仓，通过修订补充

#### 3. 混合情况
- **处理**: 先使用RESTATEMENT数据，然后合并所有NEW HOLDINGS条目
- **警告**: 系统会记录WARNING日志提醒用户同时存在两种修订类型

### 使用示例

```bash
# 获取包含修订的季度数据 - 自动处理RESTATEMENT
poetry run sec13f-cli fetch --cik 0002036346 --quarter 2025Q4
# 输出: ✓ 发现 1 个RESTATEMENT修订
#       → 使用RESTATEMENT数据 (提交日期: 2026-02-12)

# 获取NEW HOLDINGS修订 - 自动合并数据
poetry run sec13f-cli fetch --cik 0002036346 --quarter 2025Q1
# 输出: ✓ 发现 1 个NEW HOLDINGS修订
#       → 使用原始13F-HR数据 (提交日期: 2025-05-09)
#       → 合并NEW HOLDINGS修订 (提交日期: 2025-05-22)
```

### 技术细节

工具会自动：
1. 解析`primary_doc.xml`文件确定修订类型
2. 根据修订类型选择合适的数据处理策略
3. 处理重复CUSIP（使用修订版本数据）
4. 重新计算总价值和持仓百分比
5. 记录所有修订的元数据到`amendment_metadata`字段

### Python API使用

```python
from sec13f_analyzer import SEC13FDataFetcher

fetcher = SEC13FDataFetcher()
holdings = fetcher.get_holdings_data('0002036346', '2025Q4')

# 检查是否为修订版本
if holdings.is_amendment:
    print(f"修订类型: {holdings.amendment_info.amendment_type.value}")
    
# 检查是否为合并数据
if holdings.is_merged:
    print("数据已从多个修订合并")
    
# 查看所有修订历史
for meta in holdings.amendment_metadata:
    print(f"{meta.amendment_type.value} - {meta.filing_date}")
```

### 3. 获取持仓数据

```bash
# 获取2024年第3季度持仓
poetry run sec13f-cli fetch --cik 0001067983 --quarter 2024Q3

# 获取持仓并导出到Excel
poetry run sec13f-cli fetch --cik 0001067983 --quarter 2024Q3 --output berkshire_q3.xlsx

# 导出为CSV格式
poetry run sec13f-cli fetch --cik 0001067983 --quarter 2024Q3 --format csv
```

**输出示例:**

```
✓ 成功获取持仓数据:
  基金名称: BERKSHIRE HATHAWAY INC
  报告季度: 2024Q3
  期末日期: 2024-09-30
  总持仓价值: $279,969,100,000
  持仓股票数量: 129

前20大持仓:
--------------------------------------------------------------------------------
 1. APPLE INC                             $45,903,400,000 (16.40%)
 2. AMERICAN EXPRESS CO                    $34,515,100,000 (12.33%)
 3. COCA COLA CO                          $17,995,300,000 ( 6.43%)
 4. OCCIDENTAL PETE CORP                  $16,090,400,000 ( 5.75%)
 5. BANK AMER CORP                        $15,986,200,000 ( 5.71%)
```

### 4. 分析持仓变动

```bash
# 分析Q2到Q3的持仓变动
poetry run sec13f-cli analyze --cik 0001067983 --from-quarter 2024Q2 --to-quarter 2024Q3

# 分析变动并导出报告
poetry run sec13f-cli analyze --cik 0001067983 --from-quarter 2024Q2 --to-quarter 2024Q3 --output changes_q2_q3.xlsx

# 分析变动并显示图表
poetry run sec13f-cli analyze --cik 0001067983 --from-quarter 2024Q2 --to-quarter 2024Q3 --show-plot
```

**输出示例:**

```
✓ 持仓变动分析结果:
  基金名称: BERKSHIRE HATHAWAY INC
  分析期间: 2024Q2 → 2024Q3
  期初总价值: $285,400,000,000
  期末总价值: $279,969,100,000
  总价值变动: -$5,430,900,000 (-1.90%)

变动统计:
  新增持仓: 2 个
  清仓持仓: 3 个
  增持股票: 8 个
  减持股票: 15 个

持仓变动
------------------------------------------------------------------------------------------
新增 LIBERTY MEDIA CORP-LIBERTY FORMULA ONE  $5,427,000
清仓 PARAMOUNT GLOBAL                        -$2,596,100,000
减持 APPLE INC                              -$3,077,400,000
增持 OCCIDENTAL PETE CORP                     $398,200,000
```

### 5. 生成综合报告

```bash
# 生成多季度汇总报告
poetry run sec13f-cli report --cik 0001067983 --quarters 2024Q1,2024Q2,2024Q3 --output annual_report.xlsx

# 生成单季度报告
poetry run sec13f-cli report --cik 0001067983 --quarters 2024Q3 --output q3_report.xlsx
```

**输出示例:**

```
✓ 汇总报告已生成:
  包含 3 个季度的数据
  已导出到: annual_report.xlsx

投资组合价值趋势:
--------------------------------------------------
2024Q1: $   267,500,000,000
2024Q2: $   285,400,000,000
2024Q3: $   279,969,100,000
```

### 6. 比较多个基金

```bash
# 比较三大基金的共同持仓
poetry run sec13f-cli compare --ciks 0001067983,0001166559,0001364742 --quarter 2024Q3

# 设置最少持有基金数量
poetry run sec13f-cli compare --ciks 0001067983,0001166559 --quarter 2024Q3 --min-funds 2
```

**输出示例:**

```
找到 25 个共同持仓:
----------------------------------------------------------------------------------------------------
股票名称                                持有基金数    总市值 (百万美元)
----------------------------------------------------------------------------------------------------
APPLE INC                               3          89,234.5
MICROSOFT CORP                          3          45,678.2
AMAZON COM INC                          2          23,456.7
```

## 📋 CLI命令参考

### 全局选项

```bash
--verbose, -v       # 启用详细输出
--user-agent        # 自定义User-Agent字符串
--help              # 显示帮助信息
```

### 命令列表

| 命令      | 功能             | 主要参数                                     |
| --------- | ---------------- | -------------------------------------------- |
| `search`  | 搜索基金CIK编号  | `--fund-name`                                |
| `info`    | 获取基金基本信息 | `--cik`, `--quarter`                         |
| `fetch`   | 获取持仓数据     | `--cik`, `--quarter`, `--output`, `--format` |
| `analyze` | 分析持仓变动     | `--cik`, `--from-quarter`, `--to-quarter`    |
| `compare` | 比较多个基金     | `--ciks`, `--quarter`, `--min-funds`         |
| `report`  | 生成汇总报告     | `--cik`, `--quarters`, `--output`            |

### 常用CIK代码

| 基金名称                            | CIK编号    |
| ----------------------------------- | ---------- |
| 伯克希尔哈撒韦 (Berkshire Hathaway) | 0001067983 |
| 桥水基金 (Bridgewater Associates)   | 0001166559 |
| 先锋集团 (Vanguard Group)           | 0001364742 |
| 贝莱德 (BlackRock)                  | 0001393818 |

## 🎯 使用示例

### 分析巴菲特的投资策略

```bash
# 1. 获取伯克希尔哈撒韦最新持仓
poetry run sec13f-cli fetch --cik 0001067983 --quarter 2024Q3

# 2. 分析最近的持仓变动
poetry run sec13f-cli analyze --cik 0001067983 --from-quarter 2024Q2 --to-quarter 2024Q3

# 3. 生成年度汇总报告
poetry run sec13f-cli report --cik 0001067983 --quarters 2024Q1,2024Q2,2024Q3 --output berkshire_2024.xlsx
```

### 比较顶级基金投资策略

```bash
# 找出三大基金的共同持仓
poetry run sec13f-cli compare --ciks 0001067983,0001166559,0001364742 --quarter 2024Q3
```

### 批量分析多个季度

```bash
# 分析连续三个季度的变动
for quarter in 2024Q1 2024Q2 2024Q3; do
    poetry run sec13f-cli fetch --cik 0001067983 --quarter $quarter --output berkshire_$quarter.xlsx
done
```

## ⚙️ 配置说明

### 创建配置文件

```bash
# 复制示例配置文件
cp config.ini.example config.ini

# 编辑配置文件
vim config.ini
```

### 配置文件示例

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

### 配置说明

- `company_name`: 公司名称（用于User-Agent）
- `email`: 联系邮箱（用于User-Agent）
- `request_delay`: 请求间隔时间（秒）
- `max_retries`: 最大重试次数
- `timeout`: 请求超时时间（秒）

## 🧪 运行测试

```bash
# 运行所有测试
poetry run pytest

# 运行测试并查看覆盖率
poetry run pytest --cov=src/sec13f_analyzer --cov-report=term-missing

# 运行特定测试模块
poetry run pytest tests/test_analyzer.py -v

# 运行官方示例
poetry run python examples.py
```

**测试结果:**

```
================================= 81 passed, 14 skipped =================================
Coverage: 84% (1091/1304 lines covered)
```

## 📚 文档

- [系统架构说明](docs/architecture.md) - 详细的代码架构和模块设计
- [API参考文档](docs/api-reference.md) - 完整的API接口说明
- [开发指南](docs/development.md) - 开发环境搭建和贡献指南

## ⚠️ 重要说明

### 使用限制

- **请求频率**: SEC对API请求有频率限制，建议间隔0.2秒以上
- **User-Agent**: 必须设置包含真实联系信息的User-Agent
- **数据延迟**: 13F报告通常在季度结束后45天内提交
- **数据准确性**: 工具已通过测试验证，但建议人工审核重要决策

### 免责声明

本工具仅供学习和研究使用，不构成投资建议。使用者需自行承担使用风险。

## 🔗 相关资源

- [SEC EDGAR数据库](https://www.sec.gov/edgar.shtml)
- [13F报告说明](https://www.sec.gov/divisions/investment/13ffaq.htm)
- [SEC API文档](https://www.sec.gov/edgar/sec-api-documentation)

---

**⭐ 如果这个项目对您有帮助，请给个Star！**
