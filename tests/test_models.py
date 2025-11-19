"""
测试数据模型
"""

from datetime import datetime

import pytest

from sec13f_analyzer.models import (
    FundInfo,
    Holding,
    HoldingChange,
    Holdings,
    HoldingsChange,
)


class TestHolding:
    """测试Holding类"""
    
    def test_holding_creation(self):
        """测试创建Holding对象"""
        holding = Holding(
            cusip="12345678",
            issuer_name="Apple Inc.",
            security_class="COM",
            shares_owned=1000,
            market_value=150000.0,
            percentage_of_portfolio=5.0
        )
        
        assert holding.cusip == "12345678"
        assert holding.issuer_name == "Apple Inc."
        assert holding.shares_owned == 1000
        assert holding.market_value == 150000.0
        assert holding.price_per_share == 150.0
    
    def test_holding_price_calculation(self):
        """测试每股价格计算"""
        holding = Holding(
            cusip="12345678",
            issuer_name="Test Company",
            security_class="COM",
            shares_owned=500,
            market_value=75000.0,
            percentage_of_portfolio=2.5
        )
        
        assert holding.price_per_share == 150.0
    
    def test_holding_zero_shares(self):
        """测试零股数的情况"""
        holding = Holding(
            cusip="12345678", 
            issuer_name="Test Company",
            security_class="COM",
            shares_owned=0,
            market_value=0.0,
            percentage_of_portfolio=0.0
        )
        
        assert holding.price_per_share == 0.0


class TestHoldings:
    """测试Holdings类"""
    
    def create_sample_holdings(self):
        """创建示例持仓数据"""
        holdings = [
            Holding("12345678", "Apple Inc.", "COM", 1000, 150000.0, 0.0),
            Holding("87654321", "Microsoft Corp.", "COM", 500, 100000.0, 0.0),
            Holding("11111111", "Amazon.com Inc.", "COM", 200, 50000.0, 0.0)
        ]
        
        return Holdings(
            cik="0001234567",
            fund_name="Test Fund",
            quarter="2024Q3",
            period_end_date=datetime(2024, 9, 30),
            total_value=300000.0,
            holdings=holdings
        )
    
    def test_holdings_creation(self):
        """测试创建Holdings对象"""
        holdings = self.create_sample_holdings()
        
        assert holdings.cik == "0001234567"
        assert holdings.fund_name == "Test Fund"
        assert holdings.quarter == "2024Q3"
        assert holdings.total_value == 300000.0
        assert len(holdings.holdings) == 3
    
    def test_percentage_calculation(self):
        """测试投资组合占比计算"""
        holdings = self.create_sample_holdings()
        
        # 检查占比计算
        assert holdings.holdings[0].percentage_of_portfolio == 50.0  # 150000/300000
        assert holdings.holdings[1].percentage_of_portfolio == pytest.approx(33.33, rel=1e-2)
        assert holdings.holdings[2].percentage_of_portfolio == pytest.approx(16.67, rel=1e-2)
    
    def test_holdings_count_property(self):
        """测试holdings_count属性"""
        holdings = self.create_sample_holdings()
        assert holdings.holdings_count == 3
    
    def test_top_holdings_property(self):
        """测试top_holdings属性"""
        holdings = self.create_sample_holdings()
        top_2 = holdings.top_holdings(2)
        
        assert len(top_2) == 2
        assert top_2[0].issuer_name == "Apple Inc."  # 最大持仓
        assert top_2[1].issuer_name == "Microsoft Corp."  # 第二大持仓
    
    def test_to_dataframe(self):
        """测试转换为DataFrame"""
        holdings = self.create_sample_holdings()
        df = holdings.to_dataframe()
        
        assert len(df) == 3
        assert 'cusip' in df.columns
        assert 'issuer_name' in df.columns
        assert 'market_value' in df.columns
        assert df['fund_name'].iloc[0] == "Test Fund"


class TestHoldingChange:
    """测试HoldingChange类"""
    
    def test_holding_change_creation(self):
        """测试创建HoldingChange对象"""
        change = HoldingChange(
            cusip="12345678",
            issuer_name="Apple Inc.",
            change_type="increased",
            prev_shares=1000,
            curr_shares=1500,
            prev_value=150000.0,
            curr_value=225000.0
        )
        
        assert change.cusip == "12345678"
        assert change.change_type == "increased"
        assert change.shares_change == 500
        assert change.value_change == 75000.0
        assert change.percentage_change == 50.0
    
    def test_new_position(self):
        """测试新增持仓"""
        change = HoldingChange(
            cusip="12345678",
            issuer_name="New Stock",
            change_type="new",
            prev_shares=0,
            curr_shares=1000,
            prev_value=0.0,
            curr_value=100000.0
        )
        
        assert change.shares_change == 1000
        assert change.value_change == 100000.0
        assert change.percentage_change == 100.0
    
    def test_closed_position(self):
        """测试清仓持仓"""
        change = HoldingChange(
            cusip="12345678",
            issuer_name="Closed Stock", 
            change_type="closed",
            prev_shares=1000,
            curr_shares=0,
            prev_value=50000.0,
            curr_value=0.0
        )
        
        assert change.shares_change == -1000
        assert change.value_change == -50000.0
        assert change.percentage_change == -100.0


class TestHoldingsChange:
    """测试HoldingsChange类"""
    
    def create_sample_holdings_change(self):
        """创建示例持仓变动数据"""
        changes = [
            HoldingChange("12345678", "Apple Inc.", "increased", 1000, 1500, 150000.0, 225000.0),
            HoldingChange("87654321", "Microsoft Corp.", "decreased", 500, 300, 100000.0, 60000.0),
            HoldingChange("11111111", "New Stock", "new", 0, 200, 0.0, 40000.0),
            HoldingChange("22222222", "Old Stock", "closed", 100, 0, 20000.0, 0.0)
        ]
        
        return HoldingsChange(
            cik="0001234567",
            fund_name="Test Fund",
            from_quarter="2024Q2",
            to_quarter="2024Q3",
            changes=changes,
            total_prev_value=270000.0,
            total_curr_value=325000.0
        )
    
    def test_holdings_change_creation(self):
        """测试创建HoldingsChange对象"""
        holdings_change = self.create_sample_holdings_change()
        
        assert holdings_change.cik == "0001234567"
        assert holdings_change.from_quarter == "2024Q2"
        assert holdings_change.to_quarter == "2024Q3"
        assert len(holdings_change.changes) == 4
    
    def test_total_change_calculation(self):
        """测试总体变化计算"""
        holdings_change = self.create_sample_holdings_change()
        
        assert holdings_change.total_value_change == 55000.0  # 325000 - 270000
        assert holdings_change.total_percentage_change == pytest.approx(20.37, rel=1e-2)
    
    def test_change_type_properties(self):
        """测试变动类型属性"""
        holdings_change = self.create_sample_holdings_change()
        
        assert len(holdings_change.new_positions) == 1
        assert len(holdings_change.closed_positions) == 1
        assert len(holdings_change.increased_positions) == 1
        assert len(holdings_change.decreased_positions) == 1
        
        assert holdings_change.new_positions[0].issuer_name == "New Stock"
        assert holdings_change.closed_positions[0].issuer_name == "Old Stock"
    
    def test_to_dataframe(self):
        """测试转换为DataFrame"""
        holdings_change = self.create_sample_holdings_change()
        df = holdings_change.to_dataframe()
        
        assert len(df) == 4
        assert 'change_type' in df.columns
        assert 'value_change' in df.columns
        assert df['from_quarter'].iloc[0] == "2024Q2"
