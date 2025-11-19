"""
数据可视化模块

提供持仓数据的各种图表和可视化功能
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
from plotly.subplots import make_subplots

from .models import Holdings, HoldingsChange


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
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
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
        
    def plot_holdings_distribution(
        self, 
        holdings: Holdings, 
        top_n: int = 10,
        chart_type: str = "pie"
    ) -> None:
        """
        绘制持仓分布图
        
        Args:
            holdings: 持仓数据
            top_n: 显示前N大持仓
            chart_type: 图表类型 ("pie", "bar", "treemap")
        """
        if not holdings.holdings:
            print("没有持仓数据可绘制")
            return
        
        # 获取前N大持仓
        top_holdings = sorted(holdings.holdings, key=lambda x: x.market_value, reverse=True)[:top_n]
        
        # 计算其他持仓总和
        other_value = holdings.total_value - sum(h.market_value for h in top_holdings)
        
        if chart_type == "pie":
            self._plot_pie_chart(top_holdings, other_value, holdings)
        elif chart_type == "bar":
            self._plot_bar_chart(top_holdings, holdings)
        elif chart_type == "treemap":
            self._plot_treemap(top_holdings, other_value, holdings)
        else:
            raise ValueError(f"不支持的图表类型: {chart_type}")
    
    def _plot_pie_chart(self, top_holdings: List, other_value: float, holdings: Holdings) -> None:
        """绘制饼图"""
        labels = [h.issuer_name for h in top_holdings]
        values = [h.market_value for h in top_holdings]
        
        if other_value > 0:
            labels.append("其他")
            values.append(other_value)
        
        fig, ax = plt.subplots(figsize=self.figsize)
        wedges, texts, autotexts = ax.pie(
            values, 
            labels=labels, 
            autopct='%1.1f%%',
            startangle=90,
            colors=self.color_palette
        )
        
        # 美化文本
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        
        ax.set_title(f"{holdings.fund_name} - {holdings.quarter}\n持仓分布 (总价值: ${holdings.total_value:,.0f})", 
                    fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        plt.show()
    
    def _plot_bar_chart(self, top_holdings: List, holdings: Holdings) -> None:
        """绘制柱状图"""
        names = [h.issuer_name[:20] + "..." if len(h.issuer_name) > 20 else h.issuer_name 
                for h in top_holdings]
        values = [h.market_value / 1e6 for h in top_holdings]  # 转为百万美元
        
        fig, ax = plt.subplots(figsize=self.figsize)
        bars = ax.barh(names, values, color=self.color_palette)
        
        # 添加数值标签
        for i, (bar, value) in enumerate(zip(bars, values)):
            ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2, 
                   f'${value:.1f}M', va='center', fontweight='bold')
        
        ax.set_xlabel('持仓价值 (百万美元)', fontweight='bold')
        ax.set_title(f"{holdings.fund_name} - {holdings.quarter}\n前{len(top_holdings)}大持仓", 
                    fontsize=14, fontweight='bold')
        
        # 反转y轴，使最大持仓在顶部
        ax.invert_yaxis()
        
        plt.tight_layout()
        plt.show()
    
    def _plot_treemap(self, top_holdings: List, other_value: float, holdings: Holdings) -> None:
        """绘制树状图（使用plotly）"""
        labels = [h.issuer_name for h in top_holdings]
        values = [h.market_value for h in top_holdings]
        
        if other_value > 0:
            labels.append("其他")
            values.append(other_value)
        
        fig = px.treemap(
            names=labels,
            values=values,
            title=f"{holdings.fund_name} - {holdings.quarter} 持仓分布"
        )
        
        fig.update_traces(
            texttemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percentParent}",
            textposition="middle center"
        )
        
        fig.show()
    
    def plot_holdings_changes(self, holdings_change: HoldingsChange, top_n: int = 15) -> None:
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
        closed_positions = [c for c in holdings_change.changes if c.change_type == "closed"]
        increased_positions = [c for c in holdings_change.changes if c.change_type == "increased"]
        decreased_positions = [c for c in holdings_change.changes if c.change_type == "decreased"]
        
        # 创建子图
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # 新增持仓
        if new_positions:
            top_new = sorted(new_positions, key=lambda x: x.curr_value, reverse=True)[:top_n//3]
            names = [c.issuer_name[:15] + "..." if len(c.issuer_name) > 15 else c.issuer_name 
                    for c in top_new]
            values = [c.curr_value / 1e6 for c in top_new]
            
            bars = ax1.barh(names, values, color='green', alpha=0.7)
            ax1.set_title(f"新增持仓 (前{len(top_new)}个)", fontweight='bold')
            ax1.set_xlabel("持仓价值 (百万美元)")
            ax1.invert_yaxis()
            
            for bar, value in zip(bars, values):
                ax1.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2, 
                        f'${value:.1f}M', va='center')
        
        # 清仓持仓
        if closed_positions:
            top_closed = sorted(closed_positions, key=lambda x: x.prev_value, reverse=True)[:top_n//3]
            names = [c.issuer_name[:15] + "..." if len(c.issuer_name) > 15 else c.issuer_name 
                    for c in top_closed]
            values = [c.prev_value / 1e6 for c in top_closed]
            
            bars = ax2.barh(names, values, color='red', alpha=0.7)
            ax2.set_title(f"清仓持仓 (前{len(top_closed)}个)", fontweight='bold')
            ax2.set_xlabel("原持仓价值 (百万美元)")
            ax2.invert_yaxis()
            
            for bar, value in zip(bars, values):
                ax2.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2, 
                        f'${value:.1f}M', va='center')
        
        # 增持
        if increased_positions:
            top_increased = sorted(increased_positions, key=lambda x: x.value_change, reverse=True)[:top_n//3]
            names = [c.issuer_name[:15] + "..." if len(c.issuer_name) > 15 else c.issuer_name 
                    for c in top_increased]
            values = [c.value_change / 1e6 for c in top_increased]
            
            bars = ax3.barh(names, values, color='blue', alpha=0.7)
            ax3.set_title(f"增持幅度最大 (前{len(top_increased)}个)", fontweight='bold')
            ax3.set_xlabel("增持价值 (百万美元)")
            ax3.invert_yaxis()
            
            for bar, value in zip(bars, values):
                ax3.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2, 
                        f'${value:.1f}M', va='center')
        
        # 减持
        if decreased_positions:
            top_decreased = sorted(decreased_positions, key=lambda x: abs(x.value_change), reverse=True)[:top_n//3]
            names = [c.issuer_name[:15] + "..." if len(c.issuer_name) > 15 else c.issuer_name 
                    for c in top_decreased]
            values = [abs(c.value_change) / 1e6 for c in top_decreased]
            
            bars = ax4.barh(names, values, color='orange', alpha=0.7)
            ax4.set_title(f"减持幅度最大 (前{len(top_decreased)}个)", fontweight='bold')
            ax4.set_xlabel("减持价值 (百万美元)")
            ax4.invert_yaxis()
            
            for bar, value in zip(bars, values):
                ax4.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2, 
                        f'${value:.1f}M', va='center')
        
        plt.suptitle(f"{holdings_change.fund_name}\n{holdings_change.from_quarter} → {holdings_change.to_quarter} 持仓变动分析", 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.show()
    
    def plot_portfolio_value_trend(self, data: List[Tuple[str, float]], title: str = "投资组合价值趋势") -> None:
        """
        绘制投资组合价值趋势图
        
        Args:
            data: [(季度, 总价值)] 列表
            title: 图表标题
        """
        if not data:
            print("没有数据可绘制")
            return
        
        quarters, values = zip(*data)
        values_m = [v / 1e6 for v in values]  # 转为百万美元
        
        fig, ax = plt.subplots(figsize=self.figsize)
        
        ax.plot(quarters, values_m, marker='o', linewidth=3, markersize=8, color='steelblue')
        ax.fill_between(quarters, values_m, alpha=0.3, color='steelblue')
        
        # 添加数值标签
        for quarter, value in zip(quarters, values_m):
            ax.annotate(f'${value:.0f}M', 
                       xy=(quarter, value), 
                       xytext=(0, 10), 
                       textcoords='offset points',
                       ha='center', 
                       fontweight='bold')
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('季度', fontweight='bold')
        ax.set_ylabel('投资组合价值 (百万美元)', fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # 旋转x轴标签
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
    
    def plot_concentration_metrics(self, concentration_data: Dict[str, float]) -> None:
        """
        绘制集中度指标图
        
        Args:
            concentration_data: 集中度数据字典
        """
        if not concentration_data:
            print("没有集中度数据可绘制")
            return
        
        # 提取前N大持仓占比数据
        metrics = ['top_5_percentage', 'top_10_percentage', 'top_20_percentage']
        values = [concentration_data.get(metric, 0) for metric in metrics]
        labels = ['前5大持仓', '前10大持仓', '前20大持仓']
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # 柱状图显示集中度
        bars = ax1.bar(labels, values, color=['red', 'orange', 'yellow'], alpha=0.7)
        ax1.set_title('持仓集中度分析', fontweight='bold')
        ax1.set_ylabel('占比 (%)', fontweight='bold')
        
        # 添加数值标签
        for bar, value in zip(bars, values):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, 
                    f'{value:.1f}%', ha='center', fontweight='bold')
        
        # 显示其他指标
        hhi = concentration_data.get('herfindahl_index', 0)
        total_positions = concentration_data.get('total_positions', 0)
        
        info_text = f"赫芬达尔指数: {hhi:.0f}\n总持仓数量: {total_positions}"
        ax2.text(0.1, 0.5, info_text, fontsize=12, fontweight='bold', 
                transform=ax2.transAxes, verticalalignment='center')
        ax2.set_title('其他指标', fontweight='bold')
        ax2.axis('off')
        
        plt.tight_layout()
        plt.show()
    
    def plot_holding_timeline(self, timeline_df: pd.DataFrame, cusip: str) -> None:
        """
        绘制单个股票的持仓时间线
        
        Args:
            timeline_df: 包含持仓历史的DataFrame
            cusip: 股票CUSIP
        """
        if timeline_df.empty:
            print("没有时间线数据可绘制")
            return
        
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        
        quarters = timeline_df['quarter']
        
        # 持股数量
        ax1.plot(quarters, timeline_df['shares_owned'], marker='o', linewidth=2, color='blue')
        ax1.set_title(f"{timeline_df['issuer_name'].iloc[0]} 持股数量变化", fontweight='bold')
        ax1.set_ylabel('持股数量', fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # 持仓价值
        ax2.plot(quarters, timeline_df['market_value'] / 1e6, marker='s', linewidth=2, color='green')
        ax2.set_title('持仓价值变化', fontweight='bold')
        ax2.set_ylabel('持仓价值 (百万美元)', fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        # 投资组合占比
        ax3.plot(quarters, timeline_df['percentage_of_portfolio'], marker='^', linewidth=2, color='red')
        ax3.set_title('投资组合占比变化', fontweight='bold')
        ax3.set_ylabel('占比 (%)', fontweight='bold')
        ax3.set_xlabel('季度', fontweight='bold')
        ax3.grid(True, alpha=0.3)
        
        # 旋转x轴标签
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
    
    def plot_turnover_analysis(self, turnover_data: Dict[str, float]) -> None:
        """
        绘制换手率分析图
        
        Args:
            turnover_data: 换手率数据字典
        """
        if not turnover_data:
            print("没有换手率数据可绘制")
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # 换手率组成
        labels = ['买入换手率', '卖出换手率']
        values = [turnover_data.get('buy_turnover', 0), turnover_data.get('sell_turnover', 0)]
        colors = ['green', 'red']
        
        bars = ax1.bar(labels, values, color=colors, alpha=0.7)
        ax1.set_title('换手率组成分析', fontweight='bold')
        ax1.set_ylabel('换手率 (%)', fontweight='bold')
        
        for bar, value in zip(bars, values):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, 
                    f'{value:.1f}%', ha='center', fontweight='bold')
        
        # 交易金额
        buys = turnover_data.get('total_buys', 0) / 1e6
        sells = turnover_data.get('total_sells', 0) / 1e6
        
        transaction_labels = ['总买入金额', '总卖出金额']
        transaction_values = [buys, sells]
        
        bars2 = ax2.bar(transaction_labels, transaction_values, color=colors, alpha=0.7)
        ax2.set_title('交易金额分析', fontweight='bold')
        ax2.set_ylabel('金额 (百万美元)', fontweight='bold')
        
        for bar, value in zip(bars2, transaction_values):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 10, 
                    f'${value:.0f}M', ha='center', fontweight='bold')
        
        plt.tight_layout()
        plt.show()
    
    def create_interactive_dashboard(self, holdings: Holdings) -> None:
        """
        创建交互式持仓仪表板（使用plotly）
        
        Args:
            holdings: 持仓数据
        """
        # 创建子图
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=['持仓分布', '前20大持仓', '行业分布', '持仓统计'],
            specs=[[{"type": "pie"}, {"type": "bar"}],
                   [{"type": "bar"}, {"type": "table"}]]
        )
        
        # 持仓分布饼图
        top_10 = sorted(holdings.holdings, key=lambda x: x.market_value, reverse=True)[:10]
        other_value = holdings.total_value - sum(h.market_value for h in top_10)
        
        labels = [h.issuer_name for h in top_10] + ['其他']
        values = [h.market_value for h in top_10] + [other_value]
        
        fig.add_trace(
            go.Pie(labels=labels, values=values, name="持仓分布"),
            row=1, col=1
        )
        
        # 前20大持仓柱状图
        top_20 = sorted(holdings.holdings, key=lambda x: x.market_value, reverse=True)[:20]
        fig.add_trace(
            go.Bar(
                x=[h.market_value / 1e6 for h in top_20],
                y=[h.issuer_name for h in top_20],
                orientation='h',
                name="前20大持仓"
            ),
            row=1, col=2
        )
        
        # 更新布局
        fig.update_layout(
            title=f"{holdings.fund_name} - {holdings.quarter} 持仓仪表板",
            height=800,
            showlegend=False
        )
        
        fig.show()
