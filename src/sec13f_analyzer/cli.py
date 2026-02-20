"""
命令行工具

提供SEC 13F持仓分析的命令行接口
"""

import sys
from pathlib import Path
from typing import List, Optional

import click
from loguru import logger

from .analyzer import SEC13FAnalyzer
from .data_fetcher import SEC13FDataFetcher
from .exporter import DataExporter
from .visualizer import HoldingsVisualizer


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='启用详细输出')
@click.option('--user-agent', default='SEC13F-Analyzer/0.1.0', help='用户代理字符串')
@click.pass_context
def cli(ctx, verbose, user_agent):
    """SEC 13F持仓分析工具"""
    # 配置日志
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    
    # 保存全局配置
    ctx.ensure_object(dict)
    ctx.obj['user_agent'] = user_agent
    ctx.obj['verbose'] = verbose


@cli.command()
@click.option('--fund-name', '-n', required=True, help='基金名称（用于搜索）')
@click.pass_context
def search(ctx, fund_name):
    """搜索基金CIK编号"""
    user_agent = ctx.obj['user_agent']
    
    try:
        fetcher = SEC13FDataFetcher(user_agent)
        results = fetcher.search_fund_cik(fund_name)
        
        if results:
            click.echo(f"\n找到 {len(results)} 个匹配的基金:")
            click.echo("-" * 60)
            for cik, name in results:
                click.echo(f"CIK: {cik}")
                click.echo(f"名称: {name}")
                click.echo("-" * 60)
        else:
            click.echo("未找到匹配的基金")
            
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        sys.exit(1)


@cli.command()
@click.option('--cik', '-c', required=True, help='基金CIK编号')
@click.option('--quarter', '-q', required=True, help='季度，如 2024Q3')
@click.option('--output', '-o', help='输出文件路径')
@click.option('--format', 'output_format', type=click.Choice(['excel', 'csv', 'json']), 
              default='excel', help='输出格式')
@click.pass_context
def fetch(ctx, cik, quarter, output, output_format):
    """获取13F持仓数据"""
    user_agent = ctx.obj['user_agent']
    
    try:
        analyzer = SEC13FAnalyzer(user_agent)
        
        click.echo(f"正在获取 CIK {cik} 在 {quarter} 的持仓数据...")
        holdings = analyzer.get_holdings(cik, quarter)
        
        if not holdings:
            click.echo("未找到持仓数据")
            sys.exit(1)
        
        # 显示基本信息
        click.echo(f"\n✓ 成功获取持仓数据:")
        click.echo(f"  基金名称: {holdings.fund_name}")
        click.echo(f"  报告季度: {holdings.quarter}")
        click.echo(f"  期末日期: {holdings.period_end_date.strftime('%Y-%m-%d')}")
        click.echo(f"  总持仓价值: ${holdings.total_value:,.0f}")
        click.echo(f"  持仓股票数量: {len(holdings.holdings)}")
        
        # 导出数据
        if output or ctx.obj['verbose']:
            exporter = DataExporter()
            
            if output_format == 'excel':
                filepath = exporter.export_holdings_to_excel(holdings, output)
            elif output_format == 'csv':
                filepath = exporter.export_to_csv(holdings, output)
            elif output_format == 'json':
                filepath = exporter.export_to_json(holdings, output)
            
            click.echo(f"  已导出到: {filepath}")

        # 显示前20大持仓
        top_20 = analyzer.get_top_holdings(cik, quarter, 20)
        if top_20:
            click.echo(f"\n前20大持仓:")
            click.echo("-" * 100)
            for i, holding in enumerate(top_20, 1):
                percentage = (holding.market_value / holdings.total_value) * 100
                security_class = f"({holding.security_class})" if holding.security_class else ""
                click.echo(f"{i:2d}. {holding.issuer_name[:35]:35s} {security_class:20s} ${holding.market_value:>12,.0f} ({percentage:5.2f}%)")
        
    except Exception as e:
        logger.error(f"获取持仓数据失败: {e}")
        sys.exit(1)


@cli.command()
@click.option('--cik', '-c', required=True, help='基金CIK编号')
@click.option('--from-quarter', '-f', required=True, help='起始季度，如 2024Q2')
@click.option('--to-quarter', '-t', required=True, help='结束季度，如 2024Q3')
@click.option('--output', '-o', help='输出文件路径')
@click.option('--format', 'output_format', type=click.Choice(['excel', 'csv', 'json']), 
              default='excel', help='输出格式')
@click.option('--show-plot', is_flag=True, help='显示变动图表')
@click.pass_context
def analyze(ctx, cik, from_quarter, to_quarter, output, output_format, show_plot):
    """分析持仓变动"""
    user_agent = ctx.obj['user_agent']
    
    try:
        analyzer = SEC13FAnalyzer(user_agent)
        
        click.echo(f"正在分析 CIK {cik} 从 {from_quarter} 到 {to_quarter} 的持仓变动...")
        holdings_change = analyzer.analyze_holdings_changes(cik, from_quarter, to_quarter)
        
        if not holdings_change:
            click.echo("无法获取持仓变动数据")
            sys.exit(1)
        
        # 显示变动统计
        click.echo(f"\n✓ 持仓变动分析结果:")
        click.echo(f"  基金名称: {holdings_change.fund_name}")
        click.echo(f"  分析期间: {holdings_change.from_quarter} → {holdings_change.to_quarter}")
        click.echo(f"  期初总价值: ${holdings_change.total_prev_value:,.0f}")
        click.echo(f"  期末总价值: ${holdings_change.total_curr_value:,.0f}")
        click.echo(f"  总价值变动: ${holdings_change.total_value_change:,.0f} ({holdings_change.total_percentage_change:+.2f}%)")
        
        click.echo(f"\n变动统计:")
        click.echo(f"  新增持仓: {len(holdings_change.new_positions)} 个")
        click.echo(f"  清仓持仓: {len(holdings_change.closed_positions)} 个") 
        click.echo(f"  增持股票: {len(holdings_change.increased_positions)} 个")
        click.echo(f"  减持股票: {len(holdings_change.decreased_positions)} 个")
        
        # 显示重大变动
        all_changes = holdings_change.new_positions + holdings_change.closed_positions + \
                     holdings_change.increased_positions + holdings_change.decreased_positions

        # if significant_changes:
        click.echo(f"\n持仓变动")
        click.echo("-" * 110)
        for change in all_changes:
            change_desc = {
                'new': '新增',
                'closed': '清仓',
                'increased': '增持',
                'decreased': '减持'
            }.get(change.change_type, change.change_type)

            security_class = f"({change.security_class})" if change.security_class else ""
            click.echo(f"{change_desc:4s} {change.issuer_name[:35]:35s} {security_class:20s} ${change.value_change:>12,.0f}")
        
        # 导出数据
        if output or ctx.obj['verbose']:
            exporter = DataExporter()
            
            if output_format == 'excel':
                filepath = exporter.export_holdings_changes_to_excel(holdings_change, output)
            elif output_format == 'csv':
                filepath = exporter.export_to_csv(holdings_change, output)
            elif output_format == 'json':
                filepath = exporter.export_to_json(holdings_change, output)
            
            click.echo(f"\n  已导出到: {filepath}")
        
        # 显示图表
        if show_plot:
            try:
                visualizer = HoldingsVisualizer()
                visualizer.plot_holdings_changes(holdings_change)
            except ImportError:
                click.echo("警告: 无法显示图表，请安装 matplotlib 和 seaborn")
        
    except Exception as e:
        logger.error(f"分析持仓变动失败: {e}")
        sys.exit(1)


@cli.command()
@click.option('--cik', '-c', required=True, help='基金CIK编号')
@click.option('--quarters', '-q', required=True, help='季度列表，用逗号分隔，如 2024Q1,2024Q2,2024Q3')
@click.option('--output', '-o', help='输出文件路径')
@click.pass_context
def report(ctx, cik, quarters, output):
    """生成多季度汇总报告"""
    user_agent = ctx.obj['user_agent']
    quarter_list = [q.strip() for q in quarters.split(',')]
    
    try:
        analyzer = SEC13FAnalyzer(user_agent)
        
        click.echo(f"正在生成 CIK {cik} 的多季度汇总报告...")
        click.echo(f"包含季度: {', '.join(quarter_list)}")
        
        # 获取各季度数据
        holdings_list = []
        for quarter in quarter_list:
            click.echo(f"  正在获取 {quarter} 数据...")
            holdings = analyzer.get_holdings(cik, quarter)
            if holdings:
                holdings_list.append(holdings)
            else:
                click.echo(f"    警告: 未找到 {quarter} 的数据")
        
        if not holdings_list:
            click.echo("未获取到任何有效数据")
            sys.exit(1)
        
        # 生成汇总报告
        exporter = DataExporter()
        filepath = exporter.create_summary_report(holdings_list, output)
        
        click.echo(f"\n✓ 汇总报告已生成:")
        click.echo(f"  包含 {len(holdings_list)} 个季度的数据")
        click.echo(f"  已导出到: {filepath}")
        
        # 显示趋势信息
        click.echo(f"\n投资组合价值趋势:")
        click.echo("-" * 50)
        for holdings in sorted(holdings_list, key=lambda x: x.quarter):
            click.echo(f"{holdings.quarter}: ${holdings.total_value:>15,.0f}")
        
    except Exception as e:
        logger.error(f"生成汇总报告失败: {e}")
        sys.exit(1)


@cli.command()
@click.option('--ciks', '-c', required=True, help='基金CIK列表，用逗号分隔')
@click.option('--quarter', '-q', required=True, help='比较季度，如 2024Q3')
@click.option('--min-funds', default=2, help='最少持有该股票的基金数量')
@click.pass_context
def compare(ctx, ciks, quarter, min_funds):
    """比较多个基金的共同持仓"""
    user_agent = ctx.obj['user_agent']
    cik_list = [cik.strip() for cik in ciks.split(',')]
    
    try:
        analyzer = SEC13FAnalyzer(user_agent)
        
        click.echo(f"正在比较 {len(cik_list)} 个基金在 {quarter} 的共同持仓...")
        
        # 查找共同持仓
        common_holdings = analyzer.find_common_holdings(cik_list, quarter, min_funds)
        
        if common_holdings:
            click.echo(f"\n找到 {len(common_holdings)} 个共同持仓:")
            click.echo("-" * 100)
            click.echo(f"{'股票名称':<40} {'持有基金数':<10} {'总市值 (百万美元)':<15}")
            click.echo("-" * 100)
            
            for holding in common_holdings[:20]:  # 显示前20个
                click.echo(f"{holding['issuer_name'][:39]:<40} {holding['holding_funds_count']:<10} ${holding['total_market_value']/1e6:>12.1f}")
        else:
            click.echo(f"未找到至少被 {min_funds} 个基金持有的共同持仓")
        
    except Exception as e:
        logger.error(f"比较基金失败: {e}")
        sys.exit(1)


@cli.command()
@click.option('--cik', '-c', required=True, help='基金CIK编号')
@click.option('--quarter', '-q', required=True, help='季度，如 2024Q3')
@click.pass_context
def info(ctx, cik, quarter):
    """显示基金基本信息和持仓概况"""
    user_agent = ctx.obj['user_agent']
    
    try:
        analyzer = SEC13FAnalyzer(user_agent)
        
        # 获取基金信息
        fund_info = analyzer.data_fetcher.get_fund_info(cik)
        if fund_info:
            click.echo(f"\n基金基本信息:")
            click.echo(f"  CIK编号: {fund_info.cik}")
            click.echo(f"  基金名称: {fund_info.fund_name}")
            if fund_info.business_address:
                click.echo(f"  业务地址: {fund_info.business_address.replace(chr(10), ' ')}")
        
        # 获取持仓数据
        holdings = analyzer.get_holdings(cik, quarter)
        if holdings:
            click.echo(f"\n{quarter} 持仓概况:")
            click.echo(f"  报告期末: {holdings.period_end_date.strftime('%Y-%m-%d')}")
            click.echo(f"  总持仓价值: ${holdings.total_value:,.0f}")
            click.echo(f"  持仓股票数量: {len(holdings.holdings)}")
            
            # 集中度分析
            concentration = analyzer.calculate_concentration(cik, quarter)
            if concentration:
                click.echo(f"\n持仓集中度:")
                click.echo(f"  前5大持仓占比: {concentration.get('top_5_percentage', 0):.1f}%")
                click.echo(f"  前10大持仓占比: {concentration.get('top_10_percentage', 0):.1f}%")
                click.echo(f"  前20大持仓占比: {concentration.get('top_20_percentage', 0):.1f}%")
                click.echo(f"  赫芬达尔指数: {concentration.get('herfindahl_index', 0):.0f}")
        else:
            click.echo(f"未找到 {quarter} 的持仓数据")
        
        # 获取历史报告列表
        filings = analyzer.data_fetcher.get_13f_filings(cik, years=2)
        if filings:
            click.echo(f"\n最近的13F报告:")
            click.echo("-" * 50)
            for filing in filings[:10]:  # 显示最近10个
                click.echo(f"  {filing['quarter']} - {filing['filing_date'].strftime('%Y-%m-%d')}")
        
    except Exception as e:
        logger.error(f"获取基金信息失败: {e}")
        sys.exit(1)


def main():
    """主函数入口"""
    cli()


if __name__ == '__main__':
    main()
