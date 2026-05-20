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
        # SEC 13F <value> 单位为美元，禁止乘以 1000。
        # 输入 <value>150000</value> => 150000.0 美元。
        # 历史上此断言曾被错误写为 150_000_000.0（隐含 *1000），
        # 形成"错误代码↔错误测试"互锁，请勿恢复。
        assert holdings[0].market_value == 150000.0
        assert total_value == 150000.0
        assert period_end_date == datetime(2024, 9, 30)

    def test_parse_xml_holdings_rejects_unsafe_entities(self, fetcher):
        """测试不安全XML实体不会被展开"""
        xml_content = """<?xml version="1.0"?>
        <!DOCTYPE informationTable [
          <!ENTITY unsafe "expanded">
        ]>
        <informationTable>
            <infoTable>
                <cusip>&unsafe;</cusip>
                <nameOfIssuer>APPLE INC</nameOfIssuer>
                <titleOfClass>COM</titleOfClass>
                <sshPrnamt>1000000</sshPrnamt>
                <value>150000</value>
            </infoTable>
        </informationTable>"""

        holdings, total_value, period_end_date = fetcher._parse_xml_holdings(
            xml_content
        )

        assert holdings == []
        assert total_value == 0.0
        assert period_end_date is None

    def test_parse_xml_holdings_from_html_script(self, fetcher):
        """测试从HTML script标签中提取XML持仓数据"""
        html_content = """<html><body>
        <script type="text/xml">
        <informationTable>
            <reportCalendarOrQuarter>09-30-2024</reportCalendarOrQuarter>
            <infoTable>
                <cusip>037833100</cusip>
                <nameOfIssuer>APPLE INC</nameOfIssuer>
                <titleOfClass>COM</titleOfClass>
                <sshPrnamt>1000000</sshPrnamt>
                <value>150000</value>
            </infoTable>
        </informationTable>
        </script>
        </body></html>"""

        holdings, total_value, period_end_date = fetcher._parse_xml_holdings(
            html_content
        )

        assert len(holdings) == 1
        assert holdings[0].issuer_name == "APPLE INC"
        # 输入 <value>150000</value> => 150000.0 美元（不缩放）
        assert total_value == 150000.0
        assert period_end_date == datetime(2024, 9, 30)

    def test_parse_xml_holdings_from_html_pre(self, fetcher):
        """测试从HTML pre标签中提取XML持仓数据"""
        html_content = """<html><body>
        <pre>
        &lt;informationTable&gt;
            &lt;infoTable&gt;
                &lt;cusip&gt;594918104&lt;/cusip&gt;
                &lt;nameOfIssuer&gt;MICROSOFT CORP&lt;/nameOfIssuer&gt;
                &lt;titleOfClass&gt;COM&lt;/titleOfClass&gt;
                &lt;sshPrnamt&gt;500&lt;/sshPrnamt&gt;
                &lt;value&gt;120&lt;/value&gt;
            &lt;/infoTable&gt;
        &lt;/informationTable&gt;
        </pre>
        </body></html>"""

        holdings, total_value, period_end_date = fetcher._parse_xml_holdings(
            html_content
        )

        assert len(holdings) == 1
        assert holdings[0].cusip == "594918104"
        # 输入 <value>120</value> => 120.0 美元（不缩放）
        assert total_value == 120.0
        assert period_end_date is None

    def test_parse_html_table_holdings(self, fetcher):
        """测试HTML表格格式的持仓数据解析"""
        html_content = """
        <html>
          <table>
            <tr>
              <th>CUSIP</th><th>Name of Issuer</th><th>Shares</th><th>Value</th>
            </tr>
            <tr>
              <td>037833100</td><td>APPLE INC</td><td>1,000</td><td>$150</td>
            </tr>
          </table>
        </html>
        """

        holdings, total_value, period_end_date = fetcher._parse_html_table(html_content)

        assert len(holdings) == 1
        assert holdings[0].cusip == "037833100"
        assert holdings[0].shares_owned == 1000
        # 输入 "$150" => 150.0 美元（不缩放）
        assert holdings[0].market_value == 150.0
        assert total_value == 150.0
        assert period_end_date is None

    def test_parse_txt_holdings(self, fetcher):
        """测试文本格式的持仓数据解析"""
        txt_content = """
        Report period ended 09/30/2024
        CUSIP       Name of Issuer       Shares       Value
        037833100   APPLE INC            1000         150
        594918104   MICROSOFT CORP       500          120
        """

        holdings, total_value, period_end_date = fetcher._parse_txt_holdings(
            txt_content
        )

        assert len(holdings) == 2
        assert holdings[0].issuer_name == "APPLE INC"
        # 输入 value 列分别为 150 和 120 => 150 + 120 = 270.0 美元（不缩放）
        assert total_value == 270.0
        assert period_end_date == datetime(2024, 9, 30)

    # ------------------------------------------------------------------
    # 单位回归测试 —— 防止 "* 1000" 错误回归
    # ------------------------------------------------------------------
    #
    # 历史背景:
    #   仓库最初版本在三个 parser 路径中错误地把 <value> 字段乘以 1000，
    #   注释写着 "SEC以千美元为单位"。这是错误的：SEC 13F Information Table
    #   的 <value> 字段以 **美元** 为单位填报，用户人工对账确认。
    #
    #   错误一度无法被根除，原因是测试断言里也硬编码了乘 1000 后的值，
    #   形成 "错误代码 ↔ 错误测试" 互锁回路：每次有人去掉 *1000，CI
    #   就因为旧测试断言失败而变红，下一个 AI agent 就把 *1000 加回去。
    #
    # 这些测试用一个不可能被误读为"千美元"的大数值作为不变量，
    # 明确并永久地把"美元单位"约定写入测试。**请勿恢复任何缩放**。

    def test_market_value_is_in_dollars_not_thousands_xml(self, fetcher):
        """XML parser: <value> 字段必须按美元原样使用，不得乘以 1000。"""
        raw_value = 123456789  # 选这个值是因为 *1000 之后会变得明显荒谬
        xml_content = f"""<?xml version="1.0"?>
        <informationTable>
            <reportCalendarOrQuarter>09-30-2024</reportCalendarOrQuarter>
            <infoTable>
                <cusip>037833100</cusip>
                <nameOfIssuer>APPLE INC</nameOfIssuer>
                <titleOfClass>COM</titleOfClass>
                <sshPrnamt>1000</sshPrnamt>
                <value>{raw_value}</value>
            </infoTable>
        </informationTable>"""

        holdings, total_value, _ = fetcher._parse_xml_holdings(xml_content)

        assert len(holdings) == 1
        assert holdings[0].market_value == float(raw_value)
        assert total_value == float(raw_value)
        # 显式断言"未被缩放"
        assert holdings[0].market_value != float(raw_value) * 1000
        # 衍生字段 price_per_share 也应该是基于美元的真实价格
        assert holdings[0].price_per_share == float(raw_value) / 1000

    def test_market_value_is_in_dollars_not_thousands_html_table(self, fetcher):
        """HTML 表格 parser: Value 列必须按美元原样使用，不得乘以 1000。"""
        raw_value = 987654321
        html_content = f"""
        <html>
          <table>
            <tr>
              <th>CUSIP</th><th>Name of Issuer</th><th>Shares</th><th>Value</th>
            </tr>
            <tr>
              <td>037833100</td><td>APPLE INC</td><td>1,000</td>
              <td>${raw_value}</td>
            </tr>
          </table>
        </html>
        """

        holdings, total_value, _ = fetcher._parse_html_table(html_content)

        assert len(holdings) == 1
        assert holdings[0].market_value == float(raw_value)
        assert total_value == float(raw_value)
        assert holdings[0].market_value != float(raw_value) * 1000

    def test_market_value_is_in_dollars_not_thousands_txt(self, fetcher):
        """TXT parser: Value 列必须按美元原样使用，不得乘以 1000。"""
        raw_value = 987654321
        txt_content = f"""
        Report period ended 09/30/2024
        CUSIP       Name of Issuer       Shares       Value
        037833100   APPLE INC            1000         {raw_value}
        """

        holdings, total_value, _ = fetcher._parse_txt_holdings(txt_content)

        assert len(holdings) == 1
        assert holdings[0].market_value == float(raw_value)
        assert total_value == float(raw_value)
        assert holdings[0].market_value != float(raw_value) * 1000

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


class TestAccessionNumberExtraction:
    """测试 ``_extract_accession_number`` 工具方法。

    accession_number 是监控服务做幂等去重的稳定 key，提取必须能覆盖
    EDGAR URL 在实际网页里出现的两种主要形式（dashed 与 18 位无连字符
    目录名）。
    """

    @pytest.mark.parametrize(
        "url,expected",
        [
            (
                "https://www.sec.gov/Archives/edgar/data/1067983/"
                "000095012324012345/0000950123-24-012345-index.htm",
                "0000950123-24-012345",
            ),
            (
                "/Archives/edgar/data/1067983/0000950123-24-012345/"
                "0000950123-24-012345-index.htm",
                "0000950123-24-012345",
            ),
            (
                "https://www.sec.gov/Archives/edgar/data/1067983/000095012324012345/",
                "0000950123-24-012345",
            ),
            ("https://example.com/no/accession/here", None),
            ("", None),
        ],
    )
    def test_extract_accession_number(self, url, expected):
        assert SEC13FDataFetcher._extract_accession_number(url) == expected


class TestQuarterFromPeriodEnd:
    """``_quarter_from_period_end`` 必须把任意月份映射到正确季度。"""

    @pytest.mark.parametrize(
        "period_end,expected",
        [
            (datetime(2024, 3, 31), "2024Q1"),
            (datetime(2024, 6, 30), "2024Q2"),
            (datetime(2024, 9, 30), "2024Q3"),
            (datetime(2024, 12, 31), "2024Q4"),
            (datetime(2025, 1, 15), "2025Q1"),
        ],
    )
    def test_quarter_from_period_end(self, period_end, expected):
        assert SEC13FDataFetcher._quarter_from_period_end(period_end) == expected


class TestGet13FFilingsEnrichment:
    """``get_13f_filings`` 应当总是填 ``accession_number``，并在显式
    开启 ``resolve_period_of_report`` 时填 ``report_quarter``。"""

    @pytest.fixture
    def fetcher(self):
        return SEC13FDataFetcher(user_agent="Test-Agent/1.0")

    @responses.activate
    def test_get_13f_filings_populates_accession_number(self, fetcher):
        recent_year = datetime.now().year - 1
        filing_date = f"{recent_year}-11-14"
        mock_response = f"""
        <html>
        <table class="tableFile2">
            <tr><th>1</th><th>2</th><th>3</th><th>4</th></tr>
            <tr>
                <td>13F-HR</td>
                <td><a href="/Archives/edgar/data/1067983/000095012324012345/0000950123-24-012345-index.htm">Documents</a></td>
                <td>Quarterly report filed by institutional managers</td>
                <td>{filing_date}</td>
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

        filings = fetcher.get_13f_filings("0001067983", years=2)

        assert len(filings) == 1
        assert filings[0]["accession_number"] == "0000950123-24-012345"
        # 默认不解析 periodOfReport
        assert "report_quarter" not in filings[0]

    @responses.activate
    def test_get_13f_filings_resolves_report_quarter(self, fetcher):
        recent_year = datetime.now().year - 1
        filing_date = f"{recent_year}-11-14"
        mock_response = f"""
        <html>
        <table class="tableFile2">
            <tr><th>1</th><th>2</th><th>3</th><th>4</th></tr>
            <tr>
                <td>13F-HR</td>
                <td><a href="/Archives/edgar/data/1067983/000095012324012345/0000950123-24-012345-index.htm">Documents</a></td>
                <td>Quarterly report filed by institutional managers</td>
                <td>{filing_date}</td>
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

        # filing 详情页（含 primary_doc.xml 链接）
        responses.add(
            responses.GET,
            "https://www.sec.gov/Archives/edgar/data/1067983/000095012324012345/"
            "0000950123-24-012345-index.htm",
            body="""
            <html>
            <table class="tableFile">
                <tr><th>1</th><th>2</th><th>3</th></tr>
                <tr>
                    <td>1</td><td>primary_doc</td>
                    <td><a href="/Archives/edgar/data/1067983/000095012324012345/primary_doc.xml">primary_doc.xml</a></td>
                </tr>
            </table>
            </html>
            """,
            status=200,
        )

        # primary_doc.xml — periodOfReport 指向 2024Q3
        responses.add(
            responses.GET,
            "https://www.sec.gov/Archives/edgar/data/1067983/000095012324012345/primary_doc.xml",
            body=f"""<?xml version="1.0" encoding="UTF-8"?>
            <edgarSubmission xmlns="http://www.sec.gov/edgar/thirteenffiler">
                <headerData>
                    <filerInfo>
                        <periodOfReport>09-30-{recent_year}</periodOfReport>
                    </filerInfo>
                </headerData>
            </edgarSubmission>
            """,
            status=200,
            content_type="application/xml",
        )

        filings = fetcher.get_13f_filings(
            "0001067983", years=2, resolve_period_of_report=True
        )

        assert len(filings) == 1
        assert filings[0]["report_quarter"] == f"{recent_year}Q3"
        assert filings[0]["period_end_date"] == datetime(recent_year, 9, 30)
