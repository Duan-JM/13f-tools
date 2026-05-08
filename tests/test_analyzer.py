"""
测试分析引擎
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from sec13f_analyzer.analyzer import SEC13FAnalyzer
from sec13f_analyzer.models import Holding, Holdings


class TestSEC13FAnalyzer:
    """测试SEC13F分析器"""

    @pytest.fixture
    def analyzer(self):
        """创建分析器实例"""
        return SEC13FAnalyzer(user_agent="Test-Agent/1.0")

    @pytest.fixture
    def sample_holdings_q2(self):
        """创建Q2示例持仓数据"""
        holdings = [
            Holding("037833100", "APPLE INC", "COM", 1000000, 150000000.0, 0.0),
            Holding("594918104", "MICROSOFT CORP", "COM", 500000, 100000000.0, 0.0),
            Holding("023135106", "AMAZON.COM INC", "COM", 200000, 50000000.0, 0.0),
        ]

        return Holdings(
            cik="0001067983",
            fund_name="BERKSHIRE HATHAWAY INC",
            quarter="2024Q2",
            period_end_date=datetime(2024, 6, 30),
            total_value=300000000.0,
            holdings=holdings,
        )

    @pytest.fixture
    def sample_holdings_q3(self):
        """创建Q3示例持仓数据"""
        holdings = [
            Holding("037833100", "APPLE INC", "COM", 1200000, 180000000.0, 0.0),  # 增持
            Holding(
                "594918104", "MICROSOFT CORP", "COM", 300000, 60000000.0, 0.0
            ),  # 减持
            Holding("88160R101", "TESLA INC", "COM", 100000, 20000000.0, 0.0),  # 新增
            # Amazon已清仓
        ]

        return Holdings(
            cik="0001067983",
            fund_name="BERKSHIRE HATHAWAY INC",
            quarter="2024Q3",
            period_end_date=datetime(2024, 9, 30),
            total_value=260000000.0,
            holdings=holdings,
        )

    def test_analyzer_initialization(self, analyzer):
        """测试分析器初始化"""
        assert analyzer.data_fetcher is not None
        assert analyzer._holdings_cache == {}

    @patch("sec13f_analyzer.analyzer.SEC13FAnalyzer.get_holdings")
    def test_get_top_holdings(self, mock_get_holdings, analyzer, sample_holdings_q2):
        """测试获取前N大持仓"""
        mock_get_holdings.return_value = sample_holdings_q2

        top_3 = analyzer.get_top_holdings("0001067983", "2024Q2", 3)

        assert len(top_3) == 3
        assert top_3[0].issuer_name == "APPLE INC"  # 最大持仓
        assert top_3[1].issuer_name == "MICROSOFT CORP"
        assert top_3[2].issuer_name == "AMAZON.COM INC"

    @patch("sec13f_analyzer.analyzer.SEC13FAnalyzer.get_holdings")
    def test_get_top_holdings_returns_empty_when_missing(
        self, mock_get_holdings, analyzer
    ):
        """测试持仓缺失时返回空列表"""
        mock_get_holdings.return_value = None

        assert analyzer.get_top_holdings("0001067983", "2024Q2") == []

    def test_get_holdings_uses_cache(self, analyzer, sample_holdings_q2):
        """测试持仓缓存命中"""
        analyzer._holdings_cache["0001067983_2024Q2"] = sample_holdings_q2

        holdings = analyzer.get_holdings("0001067983", "2024Q2")

        assert holdings is sample_holdings_q2

    def test_get_holdings_aggregates_duplicate_cusips(self, analyzer):
        """测试重复CUSIP持仓会聚合"""
        duplicate_holdings = Holdings(
            cik="0001067983",
            fund_name="BERKSHIRE HATHAWAY INC",
            quarter="2024Q2",
            period_end_date=datetime(2024, 6, 30),
            total_value=300000000.0,
            holdings=[
                Holding("037833100", "APPLE INC", "COM", 100, 1000.0, 0.0),
                Holding("037833100", "APPLE INC", "COM", 50, 500.0, 0.0),
            ],
        )
        analyzer.data_fetcher.get_holdings_data = (
            lambda cik, quarter: duplicate_holdings
        )

        holdings = analyzer.get_holdings("0001067983", "2024Q2", use_cache=False)

        assert holdings is not None
        assert len(holdings.holdings) == 1
        assert holdings.holdings[0].shares_owned == 150
        assert holdings.holdings[0].market_value == 1500.0

    @patch("sec13f_analyzer.analyzer.SEC13FAnalyzer.get_holdings")
    def test_analyze_holdings_changes(
        self, mock_get_holdings, analyzer, sample_holdings_q2, sample_holdings_q3
    ):
        """测试持仓变动分析"""

        # 模拟获取两个季度的数据
        def side_effect(cik, quarter):
            if quarter == "2024Q2":
                return sample_holdings_q2
            elif quarter == "2024Q3":
                return sample_holdings_q3
            return None

        mock_get_holdings.side_effect = side_effect

        changes = analyzer.analyze_holdings_changes("0001067983", "2024Q2", "2024Q3")

        assert changes is not None
        assert changes.cik == "0001067983"
        assert changes.from_quarter == "2024Q2"
        assert changes.to_quarter == "2024Q3"

        # 检查变动统计
        assert len(changes.new_positions) == 1  # Tesla新增
        assert len(changes.closed_positions) == 1  # Amazon清仓
        assert len(changes.increased_positions) == 1  # Apple增持
        assert len(changes.decreased_positions) == 1  # Microsoft减持

        # 检查具体变动
        tesla_change = next(c for c in changes.new_positions if c.cusip == "88160R101")
        assert tesla_change.change_type == "new"
        assert tesla_change.curr_value == 20000000.0

        amazon_change = next(
            c for c in changes.closed_positions if c.cusip == "023135106"
        )
        assert amazon_change.change_type == "closed"
        assert amazon_change.prev_value == 50000000.0

    @patch("sec13f_analyzer.analyzer.SEC13FAnalyzer.get_holdings")
    def test_analyze_holdings_changes_returns_none_when_missing(
        self, mock_get_holdings, analyzer, sample_holdings_q2
    ):
        """测试任一季度缺失时返回None"""
        mock_get_holdings.side_effect = [sample_holdings_q2, None]

        changes = analyzer.analyze_holdings_changes("0001067983", "2024Q2", "2024Q3")

        assert changes is None
