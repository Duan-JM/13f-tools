"""
测试分析引擎
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from sec13f_analyzer.analyzer import SEC13FAnalyzer
from sec13f_analyzer.models import Holding, HoldingChange, Holdings, HoldingsChange


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
            Holding("023135106", "AMAZON.COM INC", "COM", 200000, 50000000.0, 0.0)
        ]
        
        return Holdings(
            cik="0001067983",
            fund_name="BERKSHIRE HATHAWAY INC",
            quarter="2024Q2",
            period_end_date=datetime(2024, 6, 30),
            total_value=300000000.0,
            holdings=holdings
        )
    
    @pytest.fixture
    def sample_holdings_q3(self):
        """创建Q3示例持仓数据"""
        holdings = [
            Holding("037833100", "APPLE INC", "COM", 1200000, 180000000.0, 0.0),  # 增持
            Holding("594918104", "MICROSOFT CORP", "COM", 300000, 60000000.0, 0.0),   # 减持
            Holding("88160R101", "TESLA INC", "COM", 100000, 20000000.0, 0.0),       # 新增
            # Amazon已清仓
        ]
        
        return Holdings(
            cik="0001067983",
            fund_name="BERKSHIRE HATHAWAY INC",
            quarter="2024Q3",
            period_end_date=datetime(2024, 9, 30),
            total_value=260000000.0,
            holdings=holdings
        )
    
    def test_analyzer_initialization(self, analyzer):
        """测试分析器初始化"""
        assert analyzer.data_fetcher is not None
        assert analyzer._holdings_cache == {}
    
    @patch('sec13f_analyzer.analyzer.SEC13FAnalyzer.get_holdings')
    def test_get_top_holdings(self, mock_get_holdings, analyzer, sample_holdings_q2):
        """测试获取前N大持仓"""
        mock_get_holdings.return_value = sample_holdings_q2
        
        top_3 = analyzer.get_top_holdings("0001067983", "2024Q2", 3)
        
        assert len(top_3) == 3
        assert top_3[0].issuer_name == "APPLE INC"  # 最大持仓
        assert top_3[1].issuer_name == "MICROSOFT CORP"
        assert top_3[2].issuer_name == "AMAZON.COM INC"
    
    @patch('sec13f_analyzer.analyzer.SEC13FAnalyzer.get_holdings')
    def test_analyze_holdings_changes(self, mock_get_holdings, analyzer, sample_holdings_q2, sample_holdings_q3):
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
        
        amazon_change = next(c for c in changes.closed_positions if c.cusip == "023135106")
        assert amazon_change.change_type == "closed"
        assert amazon_change.prev_value == 50000000.0
    
    @patch('sec13f_analyzer.analyzer.SEC13FAnalyzer.get_holdings')
    def test_calculate_concentration(self, mock_get_holdings, analyzer, sample_holdings_q2):
        """测试计算持仓集中度"""
        mock_get_holdings.return_value = sample_holdings_q2
        
        concentration = analyzer.calculate_concentration("0001067983", "2024Q2")
        
        assert concentration is not None
        assert concentration["top_5_percentage"] == 100.0  # 只有3个持仓
        assert concentration["top_10_percentage"] == 100.0
        assert concentration["total_positions"] == 3
        assert concentration["herfindahl_index"] > 0
    
    @patch('sec13f_analyzer.analyzer.SEC13FAnalyzer.get_holdings')
    def test_track_holding_over_time(self, mock_get_holdings, analyzer):
        """测试追踪特定股票的持仓历史"""
        # 模拟不同季度的Apple持仓
        def side_effect(cik, quarter):
            if quarter == "2024Q1":
                holdings = [Holding("037833100", "APPLE INC", "COM", 800000, 120000000.0, 0.0)]
                return Holdings(cik, "Test Fund", quarter, datetime(2024, 3, 31), 200000000.0, holdings)
            elif quarter == "2024Q2":
                holdings = [Holding("037833100", "APPLE INC", "COM", 1000000, 150000000.0, 0.0)]
                return Holdings(cik, "Test Fund", quarter, datetime(2024, 6, 30), 300000000.0, holdings)
            elif quarter == "2024Q3":
                holdings = [Holding("037833100", "APPLE INC", "COM", 1200000, 180000000.0, 0.0)]
                return Holdings(cik, "Test Fund", quarter, datetime(2024, 9, 30), 260000000.0, holdings)
            return None
        
        mock_get_holdings.side_effect = side_effect
        
        timeline_df = analyzer.track_holding_over_time(
            "0001067983", 
            "037833100", 
            ["2024Q1", "2024Q2", "2024Q3"]
        )
        
        assert len(timeline_df) == 3
        assert timeline_df['shares_owned'].tolist() == [800000, 1000000, 1200000]
        assert timeline_df['market_value'].tolist() == [120000000.0, 150000000.0, 180000000.0]
    
    @patch('sec13f_analyzer.analyzer.SEC13FAnalyzer.get_holdings')
    def test_compare_funds(self, mock_get_holdings, analyzer):
        """测试比较多个基金"""
        def side_effect(cik, quarter):
            if cik == "0001067983":
                holdings = [Holding("037833100", "APPLE INC", "COM", 1000000, 150000000.0, 0.0)]
                return Holdings(cik, "BERKSHIRE HATHAWAY", quarter, datetime(2024, 6, 30), 300000000.0, holdings)
            elif cik == "0001086364":
                holdings = [Holding("037833100", "APPLE INC", "COM", 2000000, 300000000.0, 0.0)]
                return Holdings(cik, "BLACKROCK INC", quarter, datetime(2024, 6, 30), 500000000.0, holdings)
            return None
        
        mock_get_holdings.side_effect = side_effect
        
        comparison_df = analyzer.compare_funds(
            ["0001067983", "0001086364"], 
            "2024Q2"
        )
        
        assert len(comparison_df) == 2
        assert comparison_df['total_value'].tolist() == [300000000.0, 500000000.0]
        assert comparison_df['holdings_count'].tolist() == [1, 1]
    
    @patch('sec13f_analyzer.analyzer.SEC13FAnalyzer.get_holdings')
    def test_find_common_holdings(self, mock_get_holdings, analyzer):
        """测试查找共同持仓"""
        def side_effect(cik, quarter):
            if cik == "0001067983":
                holdings = [
                    Holding("037833100", "APPLE INC", "COM", 1000000, 150000000.0, 0.0),
                    Holding("594918104", "MICROSOFT CORP", "COM", 500000, 100000000.0, 0.0)
                ]
                return Holdings(cik, "Fund1", quarter, datetime(2024, 6, 30), 250000000.0, holdings)
            elif cik == "0001086364":
                holdings = [
                    Holding("037833100", "APPLE INC", "COM", 2000000, 300000000.0, 0.0),
                    Holding("023135106", "AMAZON.COM INC", "COM", 200000, 50000000.0, 0.0)
                ]
                return Holdings(cik, "Fund2", quarter, datetime(2024, 6, 30), 350000000.0, holdings)
            return None
        
        mock_get_holdings.side_effect = side_effect
        
        common_holdings = analyzer.find_common_holdings(
            ["0001067983", "0001086364"], 
            "2024Q2", 
            min_funds=2
        )
        
        assert len(common_holdings) == 1
        assert common_holdings[0]['cusip'] == "037833100"
        assert common_holdings[0]['issuer_name'] == "APPLE INC"
        assert common_holdings[0]['holding_funds_count'] == 2
        assert common_holdings[0]['total_market_value'] == 450000000.0
    
    @patch('sec13f_analyzer.analyzer.SEC13FAnalyzer.get_holdings')
    def test_analyze_turnover(self, mock_get_holdings, analyzer, sample_holdings_q2, sample_holdings_q3):
        """测试分析换手率"""
        def side_effect(cik, quarter):
            if quarter == "2024Q2":
                return sample_holdings_q2
            elif quarter == "2024Q3":
                return sample_holdings_q3
            return None
        
        mock_get_holdings.side_effect = side_effect
        
        turnover = analyzer.analyze_turnover("0001067983", "2024Q2", "2024Q3")
        
        assert turnover is not None
        assert "turnover_rate" in turnover
        assert "buy_turnover" in turnover
        assert "sell_turnover" in turnover
        assert turnover["total_buys"] > 0  # Tesla新增 + Apple增持
        assert turnover["total_sells"] > 0  # Amazon清仓 + Microsoft减持
    
    def test_holdings_caching(self, analyzer):
        """测试持仓数据缓存"""
        with patch.object(analyzer.data_fetcher, 'get_holdings_data') as mock_fetch:
            mock_holdings = Mock()
            mock_fetch.return_value = mock_holdings
            
            # 第一次调用应该从网络获取
            result1 = analyzer.get_holdings("0001067983", "2024Q2", use_cache=True)
            assert mock_fetch.call_count == 1
            
            # 第二次调用应该从缓存获取
            result2 = analyzer.get_holdings("0001067983", "2024Q2", use_cache=True)
            assert mock_fetch.call_count == 1  # 没有新的调用
            assert result1 == result2
            
            # 禁用缓存时应该重新获取
            result3 = analyzer.get_holdings("0001067983", "2024Q2", use_cache=False)
            assert mock_fetch.call_count == 2
