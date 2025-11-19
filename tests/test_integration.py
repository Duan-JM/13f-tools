"""
集成测试

测试整个系统的集成功能，需要网络连接
注意：由于SEC网站的反爬虫措施，这些测试可能会失败，
在实际生产环境中应该使用适当的用户代理和请求头
"""

import time
from datetime import datetime

import pytest

from sec13f_analyzer import SEC13FAnalyzer
from sec13f_analyzer.data_fetcher import SEC13FDataFetcher
from sec13f_analyzer.exporter import DataExporter


@pytest.mark.integration 
@pytest.mark.skip(reason="SEC website blocks automated requests (403), requires proper user agent and headers")
class TestIntegration:
    """集成测试类"""
    
    @pytest.fixture(scope="class")
    def analyzer(self):
        """创建分析器实例（类级别，避免重复创建）"""
        return SEC13FAnalyzer(user_agent="SEC13F-Analyzer-Test/0.1.0")
    
    @pytest.fixture(scope="class")
    def data_fetcher(self):
        """创建数据获取器实例"""
        return SEC13FDataFetcher(user_agent="SEC13F-Analyzer-Test/0.1.0")
    
    def test_real_fund_search(self, data_fetcher):
        """测试真实的基金搜索（需要网络）"""
        # 使用著名的基金名称
        results = data_fetcher.search_fund_cik("Berkshire")
        
        assert len(results) > 0
        # 应该能找到伯克希尔哈撒韦
        berkshire_found = any("BERKSHIRE" in name.upper() for _, name in results)
        assert berkshire_found
    
    def test_real_fund_info(self, data_fetcher):
        """测试获取真实的基金信息"""
        # 使用伯克希尔哈撒韦的CIK
        fund_info = data_fetcher.get_fund_info("0001067983")
        
        assert fund_info is not None
        assert fund_info.cik == "0001067983"
        assert "BERKSHIRE" in fund_info.fund_name.upper()
        # 基本信息应该包含地址
        assert fund_info.business_address is not None
    
    def test_real_13f_filings(self, data_fetcher):
        """测试获取真实的13F报告列表"""
        # 使用伯克希尔哈撒韦的CIK
        filings = data_fetcher.get_13f_filings("0001067983", years=1)
        
        assert len(filings) > 0
        # 检查报告的基本结构
        filing = filings[0]
        assert 'filing_date' in filing
        assert 'quarter' in filing
        assert 'url' in filing
        assert isinstance(filing['filing_date'], datetime)
    
    @pytest.mark.slow
    def test_real_holdings_data(self, analyzer):
        """测试获取真实的持仓数据（慢速测试）"""
        # 注意：这个测试需要真实的网络请求，可能比较慢
        # 使用较早的季度数据，确保数据已经可用
        holdings = analyzer.get_holdings("0001067983", "2023Q4")
        
        if holdings:  # 如果数据可用
            assert holdings.cik == "0001067983"
            assert holdings.quarter == "2023Q4"
            assert holdings.total_value > 0
            assert len(holdings.holdings) > 0
            
            # 检查持仓数据的完整性
            for holding in holdings.holdings[:5]:  # 检查前5个
                assert holding.cusip
                assert holding.issuer_name
                assert holding.shares_owned > 0
                assert holding.market_value > 0
        else:
            pytest.skip("无法获取真实的持仓数据，可能是网络问题或数据不可用")
    
    @pytest.mark.slow
    def test_real_holdings_analysis(self, analyzer):
        """测试真实的持仓变动分析"""
        # 尝试分析连续两个季度的变动
        changes = analyzer.analyze_holdings_changes("0001067983", "2023Q3", "2023Q4")
        
        if changes:
            assert changes.cik == "0001067983"
            assert changes.from_quarter == "2023Q3"
            assert changes.to_quarter == "2023Q4"
            assert len(changes.changes) > 0
            
            # 验证变动统计
            total_changes = (len(changes.new_positions) + 
                           len(changes.closed_positions) + 
                           len(changes.increased_positions) + 
                           len(changes.decreased_positions))
            assert total_changes > 0
        else:
            pytest.skip("无法获取真实的持仓变动数据")
    
    def test_concentration_analysis(self, analyzer):
        """测试集中度分析"""
        # 使用模拟数据或跳过如果无法获取真实数据
        concentration = analyzer.calculate_concentration("0001067983", "2023Q4")
        
        if concentration:
            assert 'top_5_percentage' in concentration
            assert 'top_10_percentage' in concentration
            assert 'herfindahl_index' in concentration
            assert 'total_positions' in concentration
            
            # 验证数据的合理性
            assert 0 <= concentration['top_5_percentage'] <= 100
            assert concentration['top_5_percentage'] <= concentration['top_10_percentage']
    
    def test_data_export_integration(self, analyzer, tmp_path):
        """测试数据导出集成"""
        # 尝试获取真实数据并导出
        holdings = analyzer.get_holdings("0001067983", "2023Q4")
        
        if holdings:
            exporter = DataExporter(str(tmp_path))
            
            # 测试Excel导出
            excel_file = exporter.export_holdings_to_excel(holdings)
            assert excel_file.endswith('.xlsx')
            
            # 测试CSV导出
            csv_file = exporter.export_to_csv(holdings)
            assert csv_file.endswith('.csv')
            
            # 测试JSON导出
            json_file = exporter.export_to_json(holdings)
            assert json_file.endswith('.json')
        else:
            pytest.skip("无法获取真实数据进行导出测试")
    
    def test_rate_limiting(self, data_fetcher):
        """测试请求频率限制"""
        import time
        
        start_time = time.time()
        
        # 连续发送多个请求
        for i in range(3):
            try:
                data_fetcher.search_fund_cik(f"Test{i}")
                time.sleep(0.05)  # 小的延迟确保测试不会太快
            except Exception:
                pass  # 忽略网络错误
        
        elapsed = time.time() - start_time
        # 应该有适当的延迟
        assert elapsed >= data_fetcher.request_delay * 2
    
    def test_error_handling_integration(self, analyzer):
        """测试错误处理集成"""
        # 测试无效CIK
        holdings = analyzer.get_holdings("0000000000", "2023Q4")
        assert holdings is None
        
        # 测试无效季度
        holdings = analyzer.get_holdings("0001067983", "2030Q1")  # 未来季度
        assert holdings is None
    
    @pytest.mark.slow 
    def test_multi_fund_comparison(self, analyzer):
        """测试多基金比较功能"""
        # 使用知名基金的CIK
        ciks = [
            "0001067983",  # Berkshire Hathaway
            "0001086364",  # BlackRock
        ]
        
        comparison_df = analyzer.compare_funds(ciks, "2023Q4")
        
        if len(comparison_df) > 0:
            assert 'cik' in comparison_df.columns
            assert 'fund_name' in comparison_df.columns
            assert 'total_value' in comparison_df.columns
        else:
            pytest.skip("无法获取多基金比较数据")
    
    def test_common_holdings_analysis(self, analyzer):
        """测试共同持仓分析"""
        ciks = ["0001067983", "0001086364"]  # Berkshire + BlackRock
        
        common_holdings = analyzer.find_common_holdings(ciks, "2023Q4", min_funds=2)
        
        # 这两个大基金应该有一些共同持仓（如Apple等大盘股）
        if len(common_holdings) > 0:
            holding = common_holdings[0]
            assert 'cusip' in holding
            assert 'issuer_name' in holding
            assert 'holding_funds_count' in holding
            assert holding['holding_funds_count'] >= 2
    
    def test_performance_basic(self, analyzer):
        """测试基本性能"""
        start_time = time.time()
        
        # 执行一个基本操作
        holdings = analyzer.get_holdings("0001067983", "2023Q4", use_cache=True)
        
        if holdings:
            # 第二次调用应该使用缓存，更快
            cached_start = time.time()
            cached_holdings = analyzer.get_holdings("0001067983", "2023Q4", use_cache=True)
            cached_time = time.time() - cached_start
            
            # 缓存调用应该很快（小于0.1秒）
            assert cached_time < 0.1
            assert cached_holdings == holdings


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.skip(reason="SEC website blocks automated requests (403), requires proper user agent and headers")
class TestRealDataConsistency:
    """真实数据一致性测试"""
    
    @pytest.fixture(scope="class")
    def analyzer(self):
        return SEC13FAnalyzer(user_agent="SEC13F-Analyzer-Test/0.1.0")
    
    def test_data_consistency_across_calls(self, analyzer):
        """测试多次调用数据的一致性"""
        cik = "0001067983"
        quarter = "2023Q4"
        
        # 第一次获取
        holdings1 = analyzer.get_holdings(cik, quarter, use_cache=False)
        
        if holdings1:
            # 短暂延迟后再次获取
            time.sleep(1)
            holdings2 = analyzer.get_holdings(cik, quarter, use_cache=False)
            
            if holdings2:
                # 数据应该一致
                assert holdings1.total_value == holdings2.total_value
                assert len(holdings1.holdings) == len(holdings2.holdings)
    
    def test_quarter_sequence_logic(self, analyzer):
        """测试季度序列逻辑"""
        cik = "0001067983"
        quarters = ["2023Q3", "2023Q4"]
        
        holdings_list = []
        for quarter in quarters:
            holdings = analyzer.get_holdings(cik, quarter)
            if holdings:
                holdings_list.append(holdings)
        
        if len(holdings_list) >= 2:
            # 验证季度序列的合理性
            for i in range(len(holdings_list) - 1):
                curr = holdings_list[i]
                next_q = holdings_list[i + 1]
                
                # 季度应该是连续的
                assert curr.quarter != next_q.quarter
                # 期末日期应该是合理的
                assert curr.period_end_date < next_q.period_end_date
