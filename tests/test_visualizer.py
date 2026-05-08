"""
测试可视化模块
"""

from datetime import datetime

import pytest
from matplotlib import pyplot as plt

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
                cusip="037833100",
                issuer_name="APPLE INC",
                change_type="increased",
                security_class="COM",
                prev_shares=800000,
                curr_shares=1000000,
                prev_value=120000000.0,
                curr_value=150000000.0,
            ),
            HoldingChange(
                cusip="594918104",
                issuer_name="MICROSOFT CORP",
                change_type="decreased",
                security_class="COM",
                prev_shares=600000,
                curr_shares=500000,
                prev_value=120000000.0,
                curr_value=100000000.0,
            ),
            HoldingChange(
                cusip="88160R101",
                issuer_name="TESLA INC",
                change_type="new",
                security_class="COM",
                prev_shares=0,
                curr_shares=100000,
                prev_value=0.0,
                curr_value=30000000.0,
            ),
            HoldingChange(
                cusip="023135106",
                issuer_name="AMAZON.COM INC",
                change_type="closed",
                security_class="COM",
                prev_shares=200000,
                curr_shares=0,
                prev_value=50000000.0,
                curr_value=0.0,
            ),
            HoldingChange(
                cusip="30303M102",
                issuer_name="META PLATFORMS INC",
                change_type="new",
                security_class="COM",
                prev_shares=0,
                curr_shares=80000,
                prev_value=0.0,
                curr_value=20000000.0,
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

    def test_plot_holdings_changes_with_all_change_types(
        self, visualizer, sample_holdings_change, monkeypatch
    ):
        """测试包含全部变动类型的图表绘制"""
        show_called = False

        def fake_show():
            nonlocal show_called
            show_called = True

        monkeypatch.setattr(plt, "show", fake_show)

        visualizer.plot_holdings_changes(sample_holdings_change, top_n=12)

        assert show_called is True
        assert len(plt.gcf().axes) == 4
        plt.close("all")

    def test_visualizer_seaborn_style_initialization(self):
        """测试seaborn样式初始化"""
        visualizer = HoldingsVisualizer(style="seaborn", figsize=(8, 4))

        assert visualizer.figsize == (8, 4)
        assert len(visualizer.color_palette) == 10
