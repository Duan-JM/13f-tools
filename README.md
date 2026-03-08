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

### 3. 获取持仓数据

```bash
# 获取2024年第3季度持仓
poetry run sec13f-cli fetch --cik 0001067983 --quarter 2024Q3

# 获取持仓并导出到Excel
poetry run sec13f-cli fetch --cik 0001067983 --quarter 2024Q3 --output berkshire_q3.xlsx

# 导出为CSV格式
poetry run sec13f-cli fetch --cik 0001067983 --quarter 2024Q3 --format csv
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

### 免责声明

本工具仅供学习和研究使用，不构成投资建议。使用者需自行承担使用风险。

## 🔗 相关资源

- [SEC EDGAR数据库](https://www.sec.gov/edgar.shtml)
- [13F报告说明](https://www.sec.gov/divisions/investment/13ffaq.htm)
- [SEC API文档](https://www.sec.gov/edgar/sec-api-documentation)

---

**⭐ 如果这个项目对您有帮助，请给个Star！**
