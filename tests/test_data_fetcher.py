"""
测试数据获取模块
"""

from datetime import datetime

import pytest
import responses

from sec13f_analyzer.data_fetcher import SEC13FDataFetcher


class TestSEC13FDataFetcher:
    """测试SEC13F数据获取器"""

    @pytest.fixture
    def fetcher(self):
        """创建数据获取器实例"""
        return SEC13FDataFetcher(user_agent="Test-Agent/1.0")

    def test_fetcher_initialization(self, fetcher):
        """测试数据获取器初始化"""
        assert fetcher.session is not None
        assert "Test-Agent/1.0" in fetcher.session.headers["User-Agent"]
        assert fetcher.request_delay == 0.2  # 更新为实际的默认值

    @responses.activate
    def test_search_fund_cik_success(self, fetcher):
        """测试成功搜索基金CIK"""
        # 模拟SEC搜索响应
        mock_response = """
        <html>
        <table class="tableFile2">
            <tr><th>Company</th></tr>
            <tr>
                <td><a href="?CIK=0001067983">BERKSHIRE HATHAWAY INC</a></td>
                <td>Other info</td>
            </tr>
            <tr>
                <td><a href="?CIK=0001234567">BERKSHIRE PARTNERS LLC</a></td>
                <td>Other info</td>
            </tr>
        </table>
        </html>
        """

        responses.add(
            responses.GET,
            "https://www.sec.gov/cgi-bin/browse-edgar",
            body=mock_response,
            status=200,
        )

        results = fetcher.search_fund_cik("Berkshire")

        assert len(results) == 2
        assert results[0] == ("0001067983", "BERKSHIRE HATHAWAY INC")
        assert results[1] == ("0001234567", "BERKSHIRE PARTNERS LLC")

    @responses.activate
    def test_search_fund_cik_no_results(self, fetcher):
        """测试搜索无结果情况"""
        mock_response = """
        <html>
        <table class="tableFile2">
            <tr><th>Company</th></tr>
        </table>
        </html>
        """

        responses.add(
            responses.GET,
            "https://www.sec.gov/cgi-bin/browse-edgar",
            body=mock_response,
            status=200,
        )

        results = fetcher.search_fund_cik("NonexistentFund")
        assert len(results) == 0

    @responses.activate
    def test_get_fund_info_success(self, fetcher):
        """测试成功获取基金信息"""
        mock_response = """
        <html>
        <div class="companyInfo">
            <span class="companyName">BERKSHIRE HATHAWAY INC CIK#: 0001067983</span>
        </div>
        <div class="mailer">
            Business Address
            3555 FARNAM STREET
            OMAHA NE 68131
        </div>
        </html>
        """

        responses.add(
            responses.GET,
            "https://www.sec.gov/cgi-bin/browse-edgar",
            body=mock_response,
            status=200,
        )

        fund_info = fetcher.get_fund_info("0001067983")

        assert fund_info is not None
        assert fund_info.cik == "0001067983"
        assert "BERKSHIRE HATHAWAY INC" in fund_info.fund_name
        assert "3555 FARNAM STREET" in fund_info.business_address

    def test_parse_quarter_from_date(self, fetcher):
        """测试季度解析 - 基于填报日期推断报告季度"""
        # 1月15日填报 -> 上一年Q4
        assert fetcher._parse_quarter_from_date(datetime(2024, 1, 15)) == "2023Q4"
        # 5月15日填报 -> 当年Q1
        assert fetcher._parse_quarter_from_date(datetime(2024, 5, 15)) == "2024Q1"
        # 8月15日填报 -> 当年Q2
        assert fetcher._parse_quarter_from_date(datetime(2024, 8, 15)) == "2024Q2"
        # 11月15日填报 -> 当年Q3
        assert fetcher._parse_quarter_from_date(datetime(2024, 11, 15)) == "2024Q3"

    def test_quarter_to_date(self, fetcher):
        """测试季度到日期转换"""
        assert fetcher._quarter_to_date("2024Q1") == datetime(2024, 3, 31)
        assert fetcher._quarter_to_date("2024Q2") == datetime(2024, 6, 30)
        assert fetcher._quarter_to_date("2024Q3") == datetime(2024, 9, 30)
        assert fetcher._quarter_to_date("2024Q4") == datetime(2024, 12, 31)

    def test_parse_xml_holdings(self, fetcher):
        """测试XML格式的持仓数据解析"""
        xml_content = """<?xml version="1.0"?>
        <informationTable>
            <reportCalendarOrQuarter>09-30-2024</reportCalendarOrQuarter>
            <infoTable>
                <cusip>037833100</cusip>
                <nameOfIssuer>APPLE INC</nameOfIssuer>
                <titleOfClass>COM</titleOfClass>
                <sshPrnamt>1000000</sshPrnamt>
                <value>150000</value>
                <Sole>1000000</Sole>
                <Shared>0</Shared>
                <None>0</None>
            </infoTable>
        </informationTable>"""

        holdings, total_value, period_end_date = fetcher._parse_xml_holdings(
            xml_content
        )

        assert len(holdings) == 1
        assert holdings[0].cusip == "037833100"
        assert holdings[0].issuer_name == "APPLE INC"
        assert holdings[0].shares_owned == 1000000
        assert holdings[0].market_value == 150000000.0  # 乘以1000
        assert total_value == 150000000.0
        assert period_end_date == datetime(2024, 9, 30)

    def test_request_rate_limiting(self, fetcher):
        """测试请求频率限制"""
        import time

        # 测试内部的延迟逻辑
        original_delay = fetcher.request_delay
        fetcher.request_delay = 0.01  # 设置一个很小的延迟用于测试

        # 模拟两次连续请求
        fetcher.last_request_time = time.time() - 0.005  # 上次请求在5ms前

        # 这应该会触发延迟
        before_request = time.time()
        fetcher._wait_if_needed()
        after_request = time.time()

        # 恢复原始延迟
        fetcher.request_delay = original_delay

        # 检查是否有适当的延迟
        elapsed = after_request - before_request
        assert elapsed >= 0.005  # 应该至少延迟了剩余的时间

    @responses.activate
    def test_search_fund_cik_search_results_page(self, fetcher):
        """测试解析EDGAR搜索结果页面（当没有表格结构时）"""
        # 模拟EDGAR搜索结果页面，包含CIK链接但没有标准表格结构
        mock_response = """
        <html>
        <title>EDGAR Search Results for 'Himalaya'</title>
        <body>
        <div class="content">
            <h2>Search Results</h2>
            <p>Found 1 company matching your search:</p>
            <div class="company-link">
                <a href="/cgi-bin/browse-edgar?action=getcompany&CIK=0001709323&type=13F">
                    Himalaya Capital Management LLC
                </a>
            </div>
        </div>
        </body>
        </html>
        """

        responses.add(
            responses.GET,
            "https://www.sec.gov/cgi-bin/browse-edgar",
            body=mock_response,
            status=200,
        )

        results = fetcher.search_fund_cik("Himalaya")

        assert len(results) == 1
        assert results[0] == ("0001709323", "Himalaya Capital Management LLC")

    @responses.activate
    def test_search_fund_cik_fallback_to_link_scanning(self, fetcher):
        """测试当没有标准结构时回退到链接扫描"""
        # 模拟只有链接但没有其他结构的页面
        mock_response = """
        <html>
        <body>
        <p>Some content with a <a href="?CIK=0001234567">Test Fund</a> link.</p>
        </body>
        </html>
        """

        responses.add(
            responses.GET,
            "https://www.sec.gov/cgi-bin/browse-edgar",
            body=mock_response,
            status=200,
        )

        results = fetcher.search_fund_cik("Test")

        assert len(results) == 1
        assert results[0] == ("0001234567", "Test Fund")
