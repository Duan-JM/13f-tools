"""
数据导出模块

提供多种格式的数据导出功能
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Union

import pandas as pd
from loguru import logger

from .models import Holdings, HoldingsChange


class DataExporter:
    """数据导出器"""
    
    def __init__(self, output_dir: str = "./output"):
        """
        初始化导出器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def export_holdings_to_excel(
        self, 
        holdings: Holdings, 
        filename: Optional[str] = None,
        include_summary: bool = True
    ) -> str:
        """
        导出持仓数据到Excel文件
        
        Args:
            holdings: 持仓数据
            filename: 文件名（可选）
            include_summary: 是否包含汇总表
            
        Returns:
            导出文件的完整路径
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"holdings_{holdings.cik}_{holdings.quarter}_{timestamp}.xlsx"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # 创建Excel写入器
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            
            # 主要持仓数据
            holdings_df = holdings.to_dataframe()
            holdings_df.to_excel(writer, sheet_name='持仓详情', index=False)
            
            if include_summary:
                # 创建汇总信息
                summary_data = {
                    '项目': [
                        '基金名称',
                        'CIK编号', 
                        '报告季度',
                        '期末日期',
                        '总持仓价值 (美元)',
                        '持仓股票数量',
                        '前5大持仓占比 (%)',
                        '前10大持仓占比 (%)',
                        '前20大持仓占比 (%)',
                    ],
                    '数值': [
                        holdings.fund_name,
                        holdings.cik,
                        holdings.quarter,
                        holdings.period_end_date.strftime('%Y-%m-%d'),
                        f"{holdings.total_value:,.0f}",
                        len(holdings.holdings),
                        self._calculate_top_n_percentage(holdings, 5),
                        self._calculate_top_n_percentage(holdings, 10),
                        self._calculate_top_n_percentage(holdings, 20),
                    ]
                }
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='汇总信息', index=False)
                
                # 前20大持仓
                top_holdings = sorted(holdings.holdings, key=lambda x: x.market_value, reverse=True)[:20]
                top_data = []
                for i, holding in enumerate(top_holdings, 1):
                    top_data.append({
                        '排名': i,
                        'CUSIP': holding.cusip,
                        '发行人': holding.issuer_name,
                        '股票类型': holding.security_class,
                        '持股数量': holding.shares_owned,
                        '市值 (美元)': holding.market_value,
                        '占投资组合比例 (%)': f"{holding.percentage_of_portfolio:.2f}",
                        '每股价格 (美元)': f"{holding.price_per_share:.2f}"
                    })
                
                top_df = pd.DataFrame(top_data)
                top_df.to_excel(writer, sheet_name='前20大持仓', index=False)
        
        logger.info(f"持仓数据已导出到: {filepath}")
        return filepath
    
    def export_holdings_changes_to_excel(
        self, 
        holdings_change: HoldingsChange,
        filename: Optional[str] = None
    ) -> str:
        """
        导出持仓变动数据到Excel文件
        
        Args:
            holdings_change: 持仓变动数据
            filename: 文件名（可选）
            
        Returns:
            导出文件的完整路径
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"holdings_changes_{holdings_change.cik}_{holdings_change.from_quarter}_to_{holdings_change.to_quarter}_{timestamp}.xlsx"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            
            # 全部变动数据
            changes_df = holdings_change.to_dataframe()
            changes_df.to_excel(writer, sheet_name='全部变动', index=False)
            
            # 新增持仓
            if holdings_change.new_positions:
                new_df = pd.DataFrame([{
                    'CUSIP': c.cusip,
                    '发行人': c.issuer_name,
                    '证券类别': c.security_class,
                    '持股数量': c.curr_shares,
                    '市值 (美元)': c.curr_value,
                } for c in holdings_change.new_positions])
                new_df.to_excel(writer, sheet_name='新增持仓', index=False)

            # 清仓持仓
            if holdings_change.closed_positions:
                closed_df = pd.DataFrame([{
                    'CUSIP': c.cusip,
                    '发行人': c.issuer_name,
                    '证券类别': c.security_class,
                    '原持股数量': c.prev_shares,
                    '原市值 (美元)': c.prev_value,
                } for c in holdings_change.closed_positions])
                closed_df.to_excel(writer, sheet_name='清仓持仓', index=False)
            
            # 增持减持（排序后的前20）
            position_changes = holdings_change.increased_positions + holdings_change.decreased_positions
            if position_changes:
                # 按变动金额绝对值排序
                position_changes.sort(key=lambda x: abs(x.value_change or 0), reverse=True)
                
                change_df = pd.DataFrame([{
                    'CUSIP': c.cusip,
                    '发行人': c.issuer_name,
                    '证券类别': c.security_class,
                    '变动类型': c.change_type,
                    '原持股数量': c.prev_shares,
                    '当前持股数量': c.curr_shares,
                    '股数变动': c.shares_change,
                    '原市值 (美元)': c.prev_value,
                    '当前市值 (美元)': c.curr_value,
                    '市值变动 (美元)': c.value_change,
                    '变动比例 (%)': f"{c.percentage_change:.2f}" if c.percentage_change else "N/A"
                } for c in position_changes[:20]])
                
                change_df.to_excel(writer, sheet_name='重大调仓', index=False)
            
            # 汇总统计
            summary_data = {
                '项目': [
                    '基金名称',
                    'CIK编号',
                    '比较期间',
                    '期初总价值 (美元)',
                    '期末总价值 (美元)',
                    '总价值变动 (美元)',
                    '总价值变动比例 (%)',
                    '新增持仓数量',
                    '清仓持仓数量',
                    '增持持仓数量',
                    '减持持仓数量',
                    '不变持仓数量'
                ],
                '数值': [
                    holdings_change.fund_name,
                    holdings_change.cik,
                    f"{holdings_change.from_quarter} → {holdings_change.to_quarter}",
                    f"{holdings_change.total_prev_value:,.0f}",
                    f"{holdings_change.total_curr_value:,.0f}",
                    f"{holdings_change.total_value_change:,.0f}",
                    f"{holdings_change.total_percentage_change:.2f}",
                    len(holdings_change.new_positions),
                    len(holdings_change.closed_positions),
                    len(holdings_change.increased_positions),
                    len(holdings_change.decreased_positions),
                    len([c for c in holdings_change.changes if c.change_type == 'unchanged'])
                ]
            }
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='变动统计', index=False)
        
        logger.info(f"持仓变动数据已导出到: {filepath}")
        return filepath
    
    def export_to_csv(
        self, 
        data: Union[Holdings, HoldingsChange], 
        filename: Optional[str] = None
    ) -> str:
        """
        导出数据到CSV文件
        
        Args:
            data: 要导出的数据对象
            filename: 文件名（可选）
            
        Returns:
            导出文件的完整路径
        """
        if isinstance(data, Holdings):
            df = data.to_dataframe()
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"holdings_{data.cik}_{data.quarter}_{timestamp}.csv"
        elif isinstance(data, HoldingsChange):
            df = data.to_dataframe()
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"holdings_changes_{data.cik}_{data.from_quarter}_to_{data.to_quarter}_{timestamp}.csv"
        else:
            raise ValueError("不支持的数据类型")
        
        filepath = os.path.join(self.output_dir, filename)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')  # 使用utf-8-sig以支持中文
        
        logger.info(f"数据已导出到CSV: {filepath}")
        return filepath
    
    def export_to_json(
        self, 
        data: Union[Holdings, HoldingsChange], 
        filename: Optional[str] = None,
        indent: int = 2
    ) -> str:
        """
        导出数据到JSON文件
        
        Args:
            data: 要导出的数据对象
            filename: 文件名（可选）
            indent: JSON缩进
            
        Returns:
            导出文件的完整路径
        """
        if isinstance(data, Holdings):
            export_data = {
                'fund_info': {
                    'cik': data.cik,
                    'fund_name': data.fund_name,
                    'quarter': data.quarter,
                    'period_end_date': data.period_end_date.isoformat(),
                    'total_value': data.total_value,
                    'holdings_count': len(data.holdings)
                },
                'holdings': [
                    {
                        'cusip': h.cusip,
                        'issuer_name': h.issuer_name,
                        'security_class': h.security_class,
                        'shares_owned': h.shares_owned,
                        'market_value': h.market_value,
                        'percentage_of_portfolio': h.percentage_of_portfolio,
                        'price_per_share': h.price_per_share,
                        'voting_authority_sole': h.voting_authority_sole,
                        'voting_authority_shared': h.voting_authority_shared,
                        'voting_authority_none': h.voting_authority_none
                    } for h in data.holdings
                ]
            }
            
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"holdings_{data.cik}_{data.quarter}_{timestamp}.json"
                
        elif isinstance(data, HoldingsChange):
            export_data = {
                'change_info': {
                    'cik': data.cik,
                    'fund_name': data.fund_name,
                    'from_quarter': data.from_quarter,
                    'to_quarter': data.to_quarter,
                    'total_prev_value': data.total_prev_value,
                    'total_curr_value': data.total_curr_value,
                    'total_value_change': data.total_value_change,
                    'total_percentage_change': data.total_percentage_change
                },
                'statistics': {
                    'new_positions_count': len(data.new_positions),
                    'closed_positions_count': len(data.closed_positions),
                    'increased_positions_count': len(data.increased_positions),
                    'decreased_positions_count': len(data.decreased_positions)
                },
                'changes': [
                    {
                        'cusip': c.cusip,
                        'issuer_name': c.issuer_name,
                        'security_class': c.security_class,
                        'change_type': c.change_type,
                        'prev_shares': c.prev_shares,
                        'curr_shares': c.curr_shares,
                        'prev_value': c.prev_value,
                        'curr_value': c.curr_value,
                        'shares_change': c.shares_change,
                        'value_change': c.value_change,
                        'percentage_change': c.percentage_change
                    } for c in data.changes
                ]
            }
            
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"holdings_changes_{data.cik}_{data.from_quarter}_to_{data.to_quarter}_{timestamp}.json"
        else:
            raise ValueError("不支持的数据类型")
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=indent, ensure_ascii=False)
        
        logger.info(f"数据已导出到JSON: {filepath}")
        return filepath
    
    def create_summary_report(
        self, 
        holdings_list: List[Holdings],
        filename: Optional[str] = None
    ) -> str:
        """
        创建多季度汇总报告
        
        Args:
            holdings_list: 多个季度的持仓数据列表
            filename: 文件名（可选）
            
        Returns:
            导出文件的完整路径
        """
        if not holdings_list:
            raise ValueError("持仓数据列表不能为空")
        
        if not filename:
            cik = holdings_list[0].cik
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"summary_report_{cik}_{timestamp}.xlsx"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            
            # 投资组合价值趋势
            trend_data = []
            for holdings in sorted(holdings_list, key=lambda x: x.quarter):
                trend_data.append({
                    '季度': holdings.quarter,
                    '总价值 (美元)': holdings.total_value,
                    '持仓数量': len(holdings.holdings),
                    '期末日期': holdings.period_end_date.strftime('%Y-%m-%d')
                })
            
            trend_df = pd.DataFrame(trend_data)
            trend_df.to_excel(writer, sheet_name='价值趋势', index=False)
            
            # 各季度前10大持仓对比
            top_holdings_data = []
            for holdings in holdings_list:
                top_10 = sorted(holdings.holdings, key=lambda x: x.market_value, reverse=True)[:10]
                for i, holding in enumerate(top_10, 1):
                    top_holdings_data.append({
                        '季度': holdings.quarter,
                        '排名': i,
                        'CUSIP': holding.cusip,
                        '发行人': holding.issuer_name,
                        '市值 (美元)': holding.market_value,
                        '占比 (%)': f"{holding.percentage_of_portfolio:.2f}"
                    })
            
            top_holdings_df = pd.DataFrame(top_holdings_data)
            top_holdings_df.to_excel(writer, sheet_name='历史前10大持仓', index=False)
            
            # 持仓集中度趋势
            concentration_data = []
            for holdings in holdings_list:
                concentration_data.append({
                    '季度': holdings.quarter,
                    '前5大占比 (%)': self._calculate_top_n_percentage(holdings, 5),
                    '前10大占比 (%)': self._calculate_top_n_percentage(holdings, 10),
                    '前20大占比 (%)': self._calculate_top_n_percentage(holdings, 20),
                })
            
            concentration_df = pd.DataFrame(concentration_data)
            concentration_df.to_excel(writer, sheet_name='集中度趋势', index=False)
        
        logger.info(f"汇总报告已导出到: {filepath}")
        return filepath
    
    def _calculate_top_n_percentage(self, holdings: Holdings, n: int) -> float:
        """计算前N大持仓占比"""
        if not holdings.holdings:
            return 0.0
        
        top_n = sorted(holdings.holdings, key=lambda x: x.market_value, reverse=True)[:n]
        top_n_value = sum(h.market_value for h in top_n)
        
        return (top_n_value / holdings.total_value) * 100 if holdings.total_value > 0 else 0.0
