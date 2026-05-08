"""
数据可视化模块

提供持仓数据的各种图表和可视化功能
"""

from typing import Tuple

import matplotlib.pyplot as plt

from .models import HoldingsChange


class HoldingsVisualizer:
    """持仓数据可视化器"""

    def __init__(self, style: str = "default", figsize: Tuple[int, int] = (12, 8)):
        """
        初始化可视化器

        Args:
            style: matplotlib样式
            figsize: 图表大小
        """
        # 处理seaborn样式兼容性
        if style == "seaborn":
            try:
                import seaborn as sns

                sns.set_style("whitegrid")
            except ImportError:
                plt.style.use("default")
        else:
            plt.style.use(style)
        self.figsize = figsize

        # 设置中文字体支持
        plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        # 设置颜色主题
        try:
            self.color_palette = sns.color_palette("husl", 10)
        except Exception:
            # 如果seaborn不可用，使用matplotlib默认颜色
            try:
                # 使用新的matplotlib API
                self.color_palette = plt.colormaps["tab10"](range(10))
            except AttributeError:
                # 兼容旧版本matplotlib
                self.color_palette = plt.cm.get_cmap("tab10")(range(10))

    def plot_holdings_changes(
        self, holdings_change: HoldingsChange, top_n: int = 15
    ) -> None:
        """
        绘制持仓变动图表

        Args:
            holdings_change: 持仓变动数据
            top_n: 显示前N大变动
        """
        if not holdings_change.changes:
            print("没有持仓变动数据可绘制")
            return

        # 分类变动数据
        new_positions = [c for c in holdings_change.changes if c.change_type == "new"]
        closed_positions = [
            c for c in holdings_change.changes if c.change_type == "closed"
        ]
        increased_positions = [
            c for c in holdings_change.changes if c.change_type == "increased"
        ]
        decreased_positions = [
            c for c in holdings_change.changes if c.change_type == "decreased"
        ]

        # 创建子图
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

        # 新增持仓
        if new_positions:
            top_new = sorted(
                new_positions, key=lambda x: x.curr_value or 0.0, reverse=True
            )[: top_n // 3]
            names = [
                c.issuer_name[:15] + "..." if len(c.issuer_name) > 15 else c.issuer_name
                for c in top_new
            ]
            values = [(c.curr_value or 0.0) / 1e6 for c in top_new]

            bars = ax1.barh(names, values, color="green", alpha=0.7)
            ax1.set_title(f"新增持仓 (前{len(top_new)}个)", fontweight="bold")
            ax1.set_xlabel("持仓价值 (百万美元)")
            ax1.invert_yaxis()

            for bar, value in zip(bars, values):
                ax1.text(
                    bar.get_width() + 0.1,
                    bar.get_y() + bar.get_height() / 2,
                    f"${value:.1f}M",
                    va="center",
                )

        # 清仓持仓
        if closed_positions:
            top_closed = sorted(
                closed_positions, key=lambda x: x.prev_value or 0.0, reverse=True
            )[: top_n // 3]
            names = [
                c.issuer_name[:15] + "..." if len(c.issuer_name) > 15 else c.issuer_name
                for c in top_closed
            ]
            values = [(c.prev_value or 0.0) / 1e6 for c in top_closed]

            bars = ax2.barh(names, values, color="red", alpha=0.7)
            ax2.set_title(f"清仓持仓 (前{len(top_closed)}个)", fontweight="bold")
            ax2.set_xlabel("原持仓价值 (百万美元)")
            ax2.invert_yaxis()

            for bar, value in zip(bars, values):
                ax2.text(
                    bar.get_width() + 0.1,
                    bar.get_y() + bar.get_height() / 2,
                    f"${value:.1f}M",
                    va="center",
                )

        # 增持
        if increased_positions:
            top_increased = sorted(
                increased_positions,
                key=lambda x: x.value_change or 0.0,
                reverse=True,
            )[: top_n // 3]
            names = [
                c.issuer_name[:15] + "..." if len(c.issuer_name) > 15 else c.issuer_name
                for c in top_increased
            ]
            values = [(c.value_change or 0.0) / 1e6 for c in top_increased]

            bars = ax3.barh(names, values, color="blue", alpha=0.7)
            ax3.set_title(f"增持幅度最大 (前{len(top_increased)}个)", fontweight="bold")
            ax3.set_xlabel("增持价值 (百万美元)")
            ax3.invert_yaxis()

            for bar, value in zip(bars, values):
                ax3.text(
                    bar.get_width() + 0.1,
                    bar.get_y() + bar.get_height() / 2,
                    f"${value:.1f}M",
                    va="center",
                )

        # 减持
        if decreased_positions:
            top_decreased = sorted(
                decreased_positions,
                key=lambda x: abs(x.value_change or 0.0),
                reverse=True,
            )[: top_n // 3]
            names = [
                c.issuer_name[:15] + "..." if len(c.issuer_name) > 15 else c.issuer_name
                for c in top_decreased
            ]
            values = [abs(c.value_change or 0.0) / 1e6 for c in top_decreased]

            bars = ax4.barh(names, values, color="orange", alpha=0.7)
            ax4.set_title(f"减持幅度最大 (前{len(top_decreased)}个)", fontweight="bold")
            ax4.set_xlabel("减持价值 (百万美元)")
            ax4.invert_yaxis()

            for bar, value in zip(bars, values):
                ax4.text(
                    bar.get_width() + 0.1,
                    bar.get_y() + bar.get_height() / 2,
                    f"${value:.1f}M",
                    va="center",
                )

        plt.suptitle(
            f"{holdings_change.fund_name}\n{holdings_change.from_quarter} → {holdings_change.to_quarter} 持仓变动分析",
            fontsize=16,
            fontweight="bold",
        )
        plt.tight_layout()
        plt.show()
