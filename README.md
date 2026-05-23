# SEC 13F持仓分析工具 📊

一个专业的SEC 13F报告分析工具，专注于机构投资者持仓变动追踪和深度分析。通过命令行界面，轻松获取和分析美国机构投资者的持仓数据。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![Poetry](https://img.shields.io/badge/Poetry-managed-success)](https://python-poetry.org)
[![Coverage](https://img.shields.io/badge/Coverage-70%25%2B-green)](https://pytest.org)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue)](LICENSE)

## ✨ 核心功能

- 🔍 **基金搜索**: 根据基金名称快速查找CIK编号
- 📊 **持仓获取**: 实时获取SEC 13F报告持仓数据
- 📈 **变动分析**: 精确追踪季度间持仓变化
- 📋 **数据导出**: 支持Excel、CSV、JSON多种格式
- 🔔 **监控服务**: 自动监控投资组合的13F报告更新并发送通知

## 📦 快速安装

### 环境要求

- Python 3.10+
- Poetry (推荐) 或 pip

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/Duan-JM/13f-tools.git
cd 13f-tools

# 2. 使用Poetry安装 (推荐)
poetry install

# 3. 验证安装
poetry run sec13f-cli --help
```

## 🚀 CLI使用指南

### 日志等级

通过 `LOG_LEVEL` 环境变量控制日志输出（默认 `INFO`，大小写不敏感），
可选值：`TRACE` / `DEBUG` / `INFO` / `SUCCESS` / `WARNING` / `ERROR` / `CRITICAL`。

```bash
# 临时设置（仅对当前命令生效）
LOG_LEVEL=DEBUG poetry run sec13f-cli fetch -c 0001067983 -q 2024Q3

# 在当前 shell 会话中设置
export LOG_LEVEL=WARNING
poetry run sec13f-cli search -n "Berkshire"
```

`--verbose` / `-v` 等价于 `LOG_LEVEL=DEBUG`，且优先级高于环境变量。
未设置 `LOG_LEVEL` 时使用默认值 `INFO`。

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

### 5. 启动监控服务

监控服务可以自动检测投资组合的13F报告更新，并通过飞书等平台发送通知。

#### 5.1 创建配置文件

首先复制示例配置文件并编辑:

```bash
# 复制示例配置
cp monitor_config.example.yml monitor_config.yml

# 编辑配置文件
vim monitor_config.yml
```

配置文件示例:

```yaml
service:
  check_interval: 60  # 检查间隔（分钟）
  user_agent: "SEC13F-Monitor/1.0.0"
  state_file: ".monitor_state.json"

portfolios:
  - name: "伯克希尔哈撒韦"
    cik: "0001067983"
    enabled: true
    min_report_days: 30

  - name: "桥水基金"
    cik: "0001350694"
    enabled: true
    min_report_days: 30

webhooks:
  - name: "飞书通知"
    type: "feishu"
    url: "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_TOKEN"
    enabled: true
    send_test_on_start: false

notification:
  include_holdings_summary: true
  max_holdings_in_summary: 10
  include_report_link: true
```

#### 5.2 启动监控

```bash
# 启动监控服务
poetry run sec13f-cli monitor --config monitor_config.yml
```

服务将:
- 定期检查配置的投资组合的13F报告
- 发现新报告时自动发送通知到飞书
- 保存检查状态，避免重复通知
- 可通过 Ctrl+C 优雅停止

### 免责声明

本工具仅供学习和研究使用，不构成投资建议。使用者需自行承担使用风险。

## 🔗 相关资源

- [SEC EDGAR数据库](https://www.sec.gov/edgar.shtml)
- [13F报告说明](https://www.sec.gov/divisions/investment/13ffaq.htm)
- [SEC API文档](https://www.sec.gov/edgar/sec-api-documentation)

---

**⭐ 如果这个项目对您有帮助，请给个Star！**
