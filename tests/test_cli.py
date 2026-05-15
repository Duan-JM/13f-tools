"""
测试CLI命令行工具
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from sec13f_analyzer.cli import cli
from sec13f_analyzer.models import Holding, Holdings


class TestCLI:
    """测试命令行工具"""

    @pytest.fixture
    def runner(self):
        """创建CLI测试运行器"""
        return CliRunner()

    @pytest.fixture
    def sample_holdings(self):
        """创建示例持仓数据"""
        holdings = [
            Holding("037833100", "APPLE INC", "COM", 1000000, 150000000.0, 50.0),
            Holding("594918104", "MICROSOFT CORP", "COM", 500000, 100000000.0, 33.33),
        ]

        return Holdings(
            cik="0001067983",
            fund_name="BERKSHIRE HATHAWAY INC",
            quarter="2024Q3",
            period_end_date=datetime(2024, 9, 30),
            total_value=250000000.0,
            holdings=holdings,
        )

    def test_cli_help(self, runner):
        """测试CLI帮助命令"""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "SEC 13F持仓分析工具" in result.output

    def test_cli_verbose_flag(self, runner):
        """测试详细输出标志"""
        result = runner.invoke(cli, ["--verbose", "--help"])
        assert result.exit_code == 0

    @patch("sec13f_analyzer.cli.SEC13FDataFetcher")
    def test_search_command_success(self, mock_fetcher_class, runner):
        """测试搜索命令成功"""
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.search_fund_cik.return_value = [
            ("0001067983", "BERKSHIRE HATHAWAY INC"),
            ("0001234567", "BERKSHIRE PARTNERS LLC"),
        ]

        result = runner.invoke(cli, ["search", "-n", "Berkshire"])

        assert result.exit_code == 0
        assert "找到 2 个匹配的基金" in result.output
        assert "BERKSHIRE HATHAWAY INC" in result.output
        assert "0001067983" in result.output

    @patch("sec13f_analyzer.cli.SEC13FDataFetcher")
    def test_search_command_no_results(self, mock_fetcher_class, runner):
        """测试搜索命令无结果"""
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.search_fund_cik.return_value = []

        result = runner.invoke(cli, ["search", "-n", "NonexistentFund"])

        assert result.exit_code == 0
        assert "未找到匹配的基金" in result.output

    @patch("sec13f_analyzer.cli.SEC13FAnalyzer")
    def test_fetch_command_no_data(self, mock_analyzer_class, runner):
        """测试获取持仓命令无数据"""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        mock_analyzer.get_holdings.return_value = None

        result = runner.invoke(cli, ["fetch", "-c", "0001067983", "-q", "2024Q3"])

        assert result.exit_code == 1
        assert "未找到持仓数据" in result.output

    @patch("sec13f_analyzer.cli.SEC13FAnalyzer")
    @patch("sec13f_analyzer.cli.DataExporter")
    def test_fetch_command_with_export(
        self, mock_exporter_class, mock_analyzer_class, runner, sample_holdings
    ):
        """测试获取持仓命令并导出"""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        mock_analyzer.get_holdings.return_value = sample_holdings
        mock_analyzer.get_top_holdings.return_value = sample_holdings.holdings[:2]

        mock_exporter = Mock()
        mock_exporter_class.return_value = mock_exporter
        mock_exporter.export_holdings_to_excel.return_value = "/test/output.xlsx"

        result = runner.invoke(
            cli,
            [
                "fetch",
                "-c",
                "0001067983",
                "-q",
                "2024Q3",
                "-o",
                "test_output.xlsx",
                "--format",
                "excel",
            ],
        )

        assert result.exit_code == 0
        assert "已导出到" in result.output
        mock_exporter.export_holdings_to_excel.assert_called_once()

    @patch("sec13f_analyzer.cli.SEC13FAnalyzer")
    def test_analyze_command_no_data(self, mock_analyzer_class, runner):
        """测试分析命令无数据"""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        mock_analyzer.analyze_holdings_changes.return_value = None

        result = runner.invoke(
            cli, ["analyze", "-c", "0001067983", "-f", "2024Q2", "-t", "2024Q3"]
        )

        assert result.exit_code == 1
        assert "无法获取持仓变动数据" in result.output

    @patch("sec13f_analyzer.cli.SEC13FAnalyzer")
    def test_info_command_success(self, mock_analyzer_class, runner, sample_holdings):
        """测试基金信息命令成功"""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer

        # 模拟基金信息
        mock_fund_info = Mock()
        mock_fund_info.cik = "0001067983"
        mock_fund_info.fund_name = "BERKSHIRE HATHAWAY INC"
        mock_fund_info.business_address = "3555 FARNAM ST\nOMAHA NE 68131"

        mock_analyzer.data_fetcher.get_fund_info.return_value = mock_fund_info
        mock_analyzer.get_holdings.return_value = sample_holdings
        mock_analyzer.data_fetcher.get_13f_filings.return_value = [
            {"quarter": "2024Q3", "filing_date": datetime(2024, 11, 14)},
            {"quarter": "2024Q2", "filing_date": datetime(2024, 8, 14)},
        ]

        result = runner.invoke(cli, ["info", "-c", "0001067983", "-q", "2024Q3"])

        assert result.exit_code == 0
        assert "基金基本信息" in result.output
        assert "BERKSHIRE HATHAWAY INC" in result.output
        assert "最近的13F报告" in result.output

    def test_missing_required_arguments(self, runner):
        """测试缺少必需参数"""
        # 测试fetch命令缺少CIK
        result = runner.invoke(cli, ["fetch", "-q", "2024Q3"])
        assert result.exit_code != 0

        # 测试analyze命令缺少季度参数
        result = runner.invoke(cli, ["analyze", "-c", "0001067983"])
        assert result.exit_code != 0

    @patch("sec13f_analyzer.cli.SEC13FAnalyzer")
    def test_error_handling(self, mock_analyzer_class, runner):
        """测试错误处理"""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        mock_analyzer.get_holdings.side_effect = Exception("Network error")

        result = runner.invoke(cli, ["fetch", "-c", "0001067983", "-q", "2024Q3"])

        assert result.exit_code == 1

    @patch("sec13f_analyzer.cli.HoldingsVisualizer")
    @patch("sec13f_analyzer.cli.SEC13FAnalyzer")
    def test_analyze_with_plot(
        self, mock_analyzer_class, mock_visualizer_class, runner
    ):
        """测试分析命令带图表显示"""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer

        mock_holdings_change = Mock()
        # 设置Mock对象的数值属性
        mock_holdings_change.fund_name = "Test Fund"
        mock_holdings_change.from_quarter = "2024Q2"
        mock_holdings_change.to_quarter = "2024Q3"
        mock_holdings_change.total_prev_value = 1000000
        mock_holdings_change.total_curr_value = 1100000
        mock_holdings_change.total_value_change = 100000
        mock_holdings_change.total_percentage_change = 10.0
        mock_holdings_change.new_positions = []
        mock_holdings_change.closed_positions = []
        mock_holdings_change.increased_positions = []
        mock_holdings_change.decreased_positions = []

        mock_analyzer.analyze_holdings_changes.return_value = mock_holdings_change

        mock_visualizer = Mock()
        mock_visualizer_class.return_value = mock_visualizer

        result = runner.invoke(
            cli,
            [
                "analyze",
                "-c",
                "0001067983",
                "-f",
                "2024Q2",
                "-t",
                "2024Q3",
                "--show-plot",
            ],
        )

        assert result.exit_code == 0
        mock_visualizer.plot_holdings_changes.assert_called_once()

    def test_commands_exist(self, runner):
        """测试所有命令都存在"""
        commands = ["search", "fetch", "analyze", "info"]

        for command in commands:
            result = runner.invoke(cli, [command, "--help"])
            assert result.exit_code == 0, f"Command '{command}' failed"
