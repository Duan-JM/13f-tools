"""
测试可视化模块
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from sec13f_analyzer.models import Holding, HoldingChange, Holdings, HoldingsChange
from sec13f_analyzer.visualizer import HoldingsVisualizer


class TestHoldingsVisualizer:
    """测试持仓可视化器"""

    @pytest.fixture
    def visualizer(self):
        """创建可视化器实例"""
        return HoldingsVisualizer(style="default", figsize=(10, 6))

    @pytest.fixture
    def sample_holdings(self):
        """创建示例持仓数据"""
        holdings = [
            Holding("037833100", "APPLE INC", "COM", 1000000, 150000000.0, 50.0),
            Holding("594918104", "MICROSOFT CORP", "COM", 500000, 100000000.0, 33.33),
            Holding("023135106", "AMAZON.COM INC", "COM", 200000, 50000000.0, 16.67),
            Holding("88160R101", "TESLA INC", "COM", 100000, 30000000.0, 10.0),
            Holding("30303M102", "META PLATFORMS INC", "COM", 80000, 20000000.0, 6.67),
        ]

        return Holdings(
            cik="0001067983",
            fund_name="BERKSHIRE HATHAWAY INC",
            quarter="2024Q3",
            period_end_date=datetime(2024, 9, 30),
            total_value=350000000.0,
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
            HoldingChange("88160R101", "TESLA INC", "new", 0, 100000, 0.0, 30000000.0),
            HoldingChange(
                "023135106", "AMAZON.COM INC", "closed", 200000, 0, 50000000.0, 0.0
            ),
            HoldingChange(
                "30303M102", "META PLATFORMS INC", "new", 0, 80000, 0.0, 20000000.0
            ),
        ]

        return HoldingsChange(
            cik="0001067983",
            fund_name="BERKSHIRE HATHAWAY INC",
            from_quarter="2024Q2",
            to_quarter="2024Q3",
            changes=changes,
            total_prev_value=290000000.0,
            total_curr_value=300000000.0,
        )

    def test_visualizer_initialization(self, visualizer):
        """测试可视化器初始化"""
        assert visualizer.figsize == (10, 6)
        assert len(visualizer.color_palette) == 10

    def test_plot_holdings_changes_empty_data(self, visualizer):
        """测试空变动数据"""
        empty_changes = HoldingsChange(
            cik="0001067983",
            fund_name="Test Fund",
            from_quarter="2024Q2",
            to_quarter="2024Q3",
            changes=[],
            total_prev_value=0.0,
            total_curr_value=0.0,
        )

        visualizer.plot_holdings_changes(empty_changes)
