"""
pytest配置和共享fixtures
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests_mock

from sec13f_analyzer.models import Holding, HoldingChange, Holdings, HoldingsChange


@pytest.fixture
def sample_holding():
    """创建示例持仓对象"""
    return Holding(
        cusip="037833100",
        issuer_name="Apple Inc.",
        security_class="COM",
        shares_owned=1000000,
        market_value=150000000.0,
        percentage_of_portfolio=5.0,
        voting_authority_sole=1000000,
        voting_authority_shared=0,
        voting_authority_none=0
    )


@pytest.fixture
def sample_holdings(sample_holding):
    """创建示例持仓数据"""
    holdings_list = [
        sample_holding,
        Holding(
            cusip="594918104",
            issuer_name="Microsoft Corporation",
            security_class="COM",
            shares_owned=800000,
            market_value=120000000.0,
            percentage_of_portfolio=4.0
        ),
        Holding(
            cusip="023135106",
            issuer_name="Amazon.com Inc",
            security_class="COM", 
            shares_owned=500000,
            market_value=75000000.0,
            percentage_of_portfolio=2.5
        )
    ]
    
    return Holdings(
        cik="0001234567",
        fund_name="Test Investment Fund",
        quarter="2024Q3",
        period_end_date=datetime(2024, 9, 30),
        total_value=3000000000.0,
        holdings=holdings_list
    )


@pytest.fixture
def sample_prev_holdings():
    """创建上一季度的示例持仓数据"""
    holdings_list = [
        Holding(
            cusip="037833100",  # Apple - 减持
            issuer_name="Apple Inc.",
            security_class="COM",
            shares_owned=1200000,
            market_value=180000000.0,
            percentage_of_portfolio=6.0
        ),
        Holding(
            cusip="594918104",  # Microsoft - 增持
            issuer_name="Microsoft Corporation", 
            security_class="COM",
            shares_owned=600000,
            market_value=90000000.0,
            percentage_of_portfolio=3.0
        ),
        Holding(
            cusip="88160R101",  # Tesla - 清仓
            issuer_name="Tesla Inc",
            security_class="COM",
            shares_owned=100000,
            market_value=20000000.0,
            percentage_of_portfolio=0.7
        )
        # Amazon 是新增的，上季度没有
    ]
    
    return Holdings(
        cik="0001234567",
        fund_name="Test Investment Fund",
        quarter="2024Q2", 
        period_end_date=datetime(2024, 6, 30),
        total_value=2900000000.0,
        holdings=holdings_list
    )


@pytest.fixture
def sample_holdings_change(sample_holdings, sample_prev_holdings):
    """创建示例持仓变动数据"""
    changes = [
        HoldingChange(
            cusip="037833100",
            issuer_name="Apple Inc.",
            change_type="decreased",
            prev_shares=1200000,
            curr_shares=1000000,
            prev_value=180000000.0,
            curr_value=150000000.0
        ),
        HoldingChange(
            cusip="594918104", 
            issuer_name="Microsoft Corporation",
            change_type="increased",
            prev_shares=600000,
            curr_shares=800000,
            prev_value=90000000.0,
            curr_value=120000000.0
        ),
        HoldingChange(
            cusip="023135106",
            issuer_name="Amazon.com Inc",
            change_type="new",
            prev_shares=0,
            curr_shares=500000,
            prev_value=0.0,
            curr_value=75000000.0
        ),
        HoldingChange(
            cusip="88160R101",
            issuer_name="Tesla Inc", 
            change_type="closed",
            prev_shares=100000,
            curr_shares=0,
            prev_value=20000000.0,
            curr_value=0.0
        )
    ]
    
    return HoldingsChange(
        cik="0001234567",
        fund_name="Test Investment Fund",
        from_quarter="2024Q2",
        to_quarter="2024Q3",
        changes=changes,
        total_prev_value=sample_prev_holdings.total_value,
        total_curr_value=sample_holdings.total_value
    )


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_sec_response():
    """模拟SEC API响应"""
    return {
        'search_results': '''
        <table class="tableFile2">
            <tr><th>Company</th><th>CIK</th></tr>
            <tr>
                <td><a href="/cgi-bin/browse-edgar?CIK=0001067983">BERKSHIRE HATHAWAY INC</a></td>
                <td>0001067983</td>
            </tr>
        </table>
        ''',
        'filings_list': '''
        <table class="tableFile2">
            <tr><th>Filing Date</th><th>Documents</th><th>Description</th></tr>
            <tr>
                <td>2024-09-30</td>
                <td><a href="/Archives/edgar/data/1067983/13f-hr.xml">13F-HR</a></td>
                <td>13F-HR - Holdings Report</td>
            </tr>
        </table>
        ''',
        'holdings_xml': '''<?xml version="1.0" encoding="UTF-8"?>
        <informationTable>
            <infoTable>
                <nameOfIssuer>Apple Inc.</nameOfIssuer>
                <titleOfClass>COM</titleOfClass>
                <cusip>037833100</cusip>
                <value>150000</value>
                <sshPrnamt>1000000</sshPrnamt>
                <votingAuthority>
                    <Sole>1000000</Sole>
                    <Shared>0</Shared>
                    <None>0</None>
                </votingAuthority>
            </infoTable>
        </informationTable>'''
    }


@pytest.fixture
def mock_requests():
    """模拟HTTP请求"""
    with requests_mock.Mocker() as m:
        yield m


@pytest.fixture(autouse=True)
def setup_test_environment():
    """设置测试环境"""
    # 设置测试用的环境变量
    os.environ['TESTING'] = '1'
    
    yield
    
    # 清理测试环境
    if 'TESTING' in os.environ:
        del os.environ['TESTING']


@pytest.fixture
def mock_data_fetcher():
    """模拟数据获取器"""
    mock = Mock()
    mock.get_holdings_data.return_value = None
    mock.search_fund_cik.return_value = [("0001067983", "Berkshire Hathaway Inc")]
    mock.get_fund_info.return_value = None
    return mock


@pytest.fixture
def mock_analyzer():
    """模拟分析器"""
    mock = Mock()
    mock.get_holdings.return_value = None
    mock.analyze_holdings_changes.return_value = None
    mock.get_top_holdings.return_value = []
    mock.calculate_concentration.return_value = {}
    return mock


# 测试标记
pytest_plugins = []


def pytest_configure(config):
    """pytest配置"""
    config.addinivalue_line(
        "markers", "unit: 标记单元测试"
    )
    config.addinivalue_line(
        "markers", "integration: 标记集成测试" 
    )
    config.addinivalue_line(
        "markers", "slow: 标记慢速测试"
    )
    config.addinivalue_line(
        "markers", "external_service: 标记需要外部服务的测试"
    )


def pytest_collection_modifyitems(config, items):
    """修改测试项目收集"""
    # 为没有标记的测试添加unit标记
    for item in items:
        if not any(item.iter_markers()):
            item.add_marker(pytest.mark.unit)


@pytest.fixture(scope="session")
def test_data_dir():
    """测试数据目录"""
    return Path(__file__).parent / "test_data"


# 跳过需要网络的测试（在CI环境中）
skip_if_no_network = pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="跳过需要网络的测试在CI环境中"
)
