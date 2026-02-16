"""
Tests for 13F-HR/A amendment handling
"""

import pytest
from datetime import datetime
from sec13f_analyzer.data_fetcher import SEC13FDataFetcher
from sec13f_analyzer.models import AmendmentType, AmendmentInfo, Holding, Holdings


class TestAmendmentHandling:
    """测试13F-HR/A修订处理功能"""
    
    def test_parse_primary_document_restatement(self, data_fetcher):
        """测试解析RESTATEMENT类型的primary_doc.xml"""
        # This is an integration test that requires network access
        # Skip if no network or SEC rate limiting
        pytest.skip("Integration test - requires network access")
    
    def test_parse_primary_document_new_holdings(self, data_fetcher):
        """测试解析NEW HOLDINGS类型的primary_doc.xml"""
        pytest.skip("Integration test - requires network access")
    
    def test_categorize_amendments(self, data_fetcher):
        """测试修订版本分类"""
        # Mock filings data
        filings = [
            {
                'is_amendment': False,
                'filing_date': datetime(2025, 5, 9),
                'quarter': '2025Q1'
            },
            {
                'is_amendment': True,
                'filing_date': datetime(2025, 5, 22),
                'quarter': '2025Q1',
                'amendment_info': AmendmentInfo(
                    filing_date=datetime(2025, 5, 21),
                    amendment_type=AmendmentType.NEW_HOLDINGS,
                    amendment_number=1
                )
            }
        ]
        
        categorized = data_fetcher._categorize_amendments(filings)
        
        assert len(categorized['original']) == 1
        assert len(categorized['new_holdings']) == 1
        assert len(categorized['restatement']) == 0
        assert len(categorized['unknown']) == 0
    
    def test_merge_holdings_no_duplicates(self, data_fetcher):
        """测试合并持仓 - 无重复CUSIP"""
        base_holdings = Holdings(
            cik='0001234567',
            fund_name='Test Fund',
            quarter='2025Q1',
            period_end_date=datetime(2025, 3, 31),
            total_value=1000000,
            holdings=[
                Holding(
                    cusip='AAAA',
                    issuer_name='Company A',
                    security_class='Common Stock',
                    shares_owned=100,
                    market_value=500000,
                    percentage_of_portfolio=50.0
                )
            ]
        )
        
        additional_holdings = Holdings(
            cik='0001234567',
            fund_name='Test Fund',
            quarter='2025Q1',
            period_end_date=datetime(2025, 3, 31),
            total_value=500000,
            holdings=[
                Holding(
                    cusip='BBBB',
                    issuer_name='Company B',
                    security_class='Common Stock',
                    shares_owned=200,
                    market_value=500000,
                    percentage_of_portfolio=100.0
                )
            ]
        )
        
        merged = data_fetcher._merge_holdings(base_holdings, additional_holdings)
        
        assert len(merged.holdings) == 2
        assert merged.total_value == 1000000  # 500k + 500k
        assert merged.is_merged is True
        
        # Check percentages are recalculated
        cusips = {h.cusip: h for h in merged.holdings}
        assert cusips['AAAA'].percentage_of_portfolio == pytest.approx(50.0)
        assert cusips['BBBB'].percentage_of_portfolio == pytest.approx(50.0)
    
    def test_merge_holdings_with_duplicates(self, data_fetcher):
        """测试合并持仓 - 有重复CUSIP（修订版本优先）"""
        base_holdings = Holdings(
            cik='0001234567',
            fund_name='Test Fund',
            quarter='2025Q1',
            period_end_date=datetime(2025, 3, 31),
            total_value=1000000,
            holdings=[
                Holding(
                    cusip='AAAA',
                    issuer_name='Company A',
                    security_class='Common Stock',
                    shares_owned=100,
                    market_value=500000,
                    percentage_of_portfolio=50.0
                )
            ]
        )
        
        additional_holdings = Holdings(
            cik='0001234567',
            fund_name='Test Fund',
            quarter='2025Q1',
            period_end_date=datetime(2025, 3, 31),
            total_value=600000,
            holdings=[
                Holding(
                    cusip='AAAA',  # Duplicate - should replace
                    issuer_name='Company A',
                    security_class='Common Stock',
                    shares_owned=150,
                    market_value=600000,
                    percentage_of_portfolio=100.0
                )
            ]
        )
        
        merged = data_fetcher._merge_holdings(base_holdings, additional_holdings)
        
        # Should have only 1 holding (duplicate replaced)
        assert len(merged.holdings) == 1
        assert merged.total_value == 600000
        assert merged.holdings[0].shares_owned == 150  # Use amended value
        assert merged.holdings[0].market_value == 600000
    
    def test_amendment_metadata_tracking(self, data_fetcher):
        """测试修订元数据跟踪"""
        base_holdings = Holdings(
            cik='0001234567',
            fund_name='Test Fund',
            quarter='2025Q1',
            period_end_date=datetime(2025, 3, 31),
            total_value=1000000,
            holdings=[],
            amendment_metadata=[
                AmendmentInfo(
                    filing_date=datetime(2025, 5, 9),
                    amendment_type=AmendmentType.RESTATEMENT,
                    amendment_number=1
                )
            ]
        )
        
        additional_holdings = Holdings(
            cik='0001234567',
            fund_name='Test Fund',
            quarter='2025Q1',
            period_end_date=datetime(2025, 3, 31),
            total_value=500000,
            holdings=[],
            amendment_metadata=[
                AmendmentInfo(
                    filing_date=datetime(2025, 5, 22),
                    amendment_type=AmendmentType.NEW_HOLDINGS,
                    amendment_number=2
                )
            ]
        )
        
        merged = data_fetcher._merge_holdings(base_holdings, additional_holdings)
        
        # Should track both amendments
        assert len(merged.amendment_metadata) == 2
        assert merged.amendment_metadata[0].amendment_type == AmendmentType.RESTATEMENT
        assert merged.amendment_metadata[1].amendment_type == AmendmentType.NEW_HOLDINGS


@pytest.fixture
def data_fetcher():
    """创建数据获取器实例"""
    return SEC13FDataFetcher()
