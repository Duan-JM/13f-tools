"""
测试数据导出模块
"""

import json
import os
from datetime import datetime
from unittest.mock import mock_open, patch

import pandas as pd
import pytest

from sec13f_analyzer.exporter import DataExporter
from sec13f_analyzer.models import Holding, HoldingChange, Holdings, HoldingsChange


class TestDataExporter:
    """测试数据导出器"""

    @pytest.fixture
    def exporter(self, tmp_path):
        """创建导出器实例，使用临时目录"""
        return DataExporter(str(tmp_path))

    @pytest.fixture
    def sample_holdings(self):
        """创建示例持仓数据"""
        holdings = [
            Holding("037833100", "APPLE INC", "COM", 1000000, 150000000.0, 50.0),
            Holding("594918104", "MICROSOFT CORP", "COM", 500000, 100000000.0, 33.33),
            Holding("023135106", "AMAZON.COM INC", "COM", 200000, 50000000.0, 16.67),
        ]

        return Holdings(
            cik="0001067983",
            fund_name="BERKSHIRE HATHAWAY INC",
            quarter="2024Q3",
            period_end_date=datetime(2024, 9, 30),
            total_value=300000000.0,
            holdings=holdings,
        )

    @pytest.fixture
    def sample_holdings_change(self):
        """创建示例持仓变动数据"""
        changes = [
            HoldingChange(
                "037833100",
                "APPLE INC",
                "increased",
                800000,
                1000000,
                120000000.0,
                150000000.0,
            ),
            HoldingChange(
                "594918104",
                "MICROSOFT CORP",
                "decreased",
                600000,
                500000,
                120000000.0,
                100000000.0,
            ),
            HoldingChange("88160R101", "TESLA INC", "new", 0, 100000, 0.0, 20000000.0),
            HoldingChange(
                "023135106", "AMAZON.COM INC", "closed", 200000, 0, 50000000.0, 0.0
            ),
        ]

        return HoldingsChange(
            cik="0001067983",
            fund_name="BERKSHIRE HATHAWAY INC",
            from_quarter="2024Q2",
            to_quarter="2024Q3",
            changes=changes,
            total_prev_value=290000000.0,
            total_curr_value=270000000.0,
        )

    def test_exporter_initialization(self, tmp_path):
        """测试导出器初始化"""
        output_dir = str(tmp_path / "test_output")
        exporter = DataExporter(output_dir)

        assert exporter.output_dir == output_dir
        assert os.path.exists(output_dir)

    def test_export_holdings_to_excel(self, exporter, sample_holdings):
        """测试导出持仓数据到Excel"""
        filepath = exporter.export_holdings_to_excel(
            sample_holdings, "test_holdings.xlsx"
        )

        assert os.path.exists(filepath)
        assert filepath.endswith("test_holdings.xlsx")

        # 验证Excel文件内容
        with pd.ExcelFile(filepath) as excel_file:
            # 检查工作表
            assert "持仓详情" in excel_file.sheet_names
            assert "汇总信息" in excel_file.sheet_names
            assert "前20大持仓" in excel_file.sheet_names

            # 验证持仓详情数据
            holdings_df = pd.read_excel(excel_file, sheet_name="持仓详情")
            assert len(holdings_df) == 3
            assert "cusip" in holdings_df.columns
            assert "issuer_name" in holdings_df.columns
            assert holdings_df["fund_name"].iloc[0] == "BERKSHIRE HATHAWAY INC"

            # 验证汇总信息
            summary_df = pd.read_excel(excel_file, sheet_name="汇总信息")
            assert len(summary_df) >= 5  # 至少5行汇总信息

    def test_export_holdings_changes_to_excel(self, exporter, sample_holdings_change):
        """测试导出持仓变动到Excel"""
        filepath = exporter.export_holdings_changes_to_excel(
            sample_holdings_change, "test_changes.xlsx"
        )

        assert os.path.exists(filepath)

        with pd.ExcelFile(filepath) as excel_file:
            # 检查工作表
            assert "全部变动" in excel_file.sheet_names
            assert "新增持仓" in excel_file.sheet_names
            assert "清仓持仓" in excel_file.sheet_names
            assert "重大调仓" in excel_file.sheet_names
            assert "变动统计" in excel_file.sheet_names

            # 验证新增持仓数据
            new_df = pd.read_excel(excel_file, sheet_name="新增持仓")
            assert len(new_df) == 1
            assert new_df["发行人"].iloc[0] == "TESLA INC"

    def test_export_to_csv(self, exporter, sample_holdings):
        """测试导出到CSV"""
        filepath = exporter.export_to_csv(sample_holdings, "test_holdings.csv")

        assert os.path.exists(filepath)
        assert filepath.endswith(".csv")

        # 验证CSV内容
        df = pd.read_csv(filepath)
        assert len(df) == 3
        assert "cusip" in df.columns
        assert "issuer_name" in df.columns

    def test_export_to_json(self, exporter, sample_holdings):
        """测试导出到JSON"""
        filepath = exporter.export_to_json(sample_holdings, "test_holdings.json")

        assert os.path.exists(filepath)
        assert filepath.endswith(".json")

        # 验证JSON内容
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "fund_info" in data
        assert "holdings" in data
        assert data["fund_info"]["cik"] == "0001067983"
        assert len(data["holdings"]) == 3

    def test_export_holdings_change_to_json(self, exporter, sample_holdings_change):
        """测试导出持仓变动到JSON"""
        filepath = exporter.export_to_json(sample_holdings_change, "test_changes.json")

        assert os.path.exists(filepath)

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "change_info" in data
        assert "statistics" in data
        assert "changes" in data
        assert data["change_info"]["cik"] == "0001067983"
        assert data["statistics"]["new_positions_count"] == 1
        assert len(data["changes"]) == 4

    def test_calculate_top_n_percentage(self, exporter, sample_holdings):
        """测试计算前N大持仓占比"""
        top_2_pct = exporter._calculate_top_n_percentage(sample_holdings, 2)
        expected = (150000000.0 + 100000000.0) / 300000000.0 * 100  # 83.33%
        assert abs(top_2_pct - expected) < 0.01

        top_5_pct = exporter._calculate_top_n_percentage(sample_holdings, 5)
        assert top_5_pct == 100.0  # 只有3个持仓

    def test_export_unsupported_data_type(self, exporter):
        """测试导出不支持的数据类型"""
        with pytest.raises(ValueError, match="不支持的数据类型"):
            exporter.export_to_csv("invalid_data")

        with pytest.raises(ValueError, match="不支持的数据类型"):
            exporter.export_to_json("invalid_data")

    def test_automatic_filename_generation(self, exporter, sample_holdings):
        """测试自动生成文件名"""
        # 不提供文件名，应该自动生成
        filepath = exporter.export_to_csv(sample_holdings)

        assert os.path.exists(filepath)
        filename = os.path.basename(filepath)
        assert "holdings_0001067983_2024Q3" in filename
        assert filename.endswith(".csv")

    @patch("builtins.open", new_callable=mock_open)
    def test_json_export_encoding(self, mock_file, exporter, sample_holdings):
        """测试JSON导出的编码处理"""
        exporter.export_to_json(sample_holdings, "test.json")

        # 验证文件以UTF-8编码打开
        mock_file.assert_called_once()
        args, kwargs = mock_file.call_args
        assert kwargs.get("encoding") == "utf-8"
