"""
命令行工具

提供SEC 13F持仓分析的命令行接口
"""

import sys

import click
from loguru import logger

from .analyzer import SEC13FAnalyzer
from .data_fetcher import SEC13FDataFetcher
from .exporter import DataExporter
from .logging_config import configure_logging
from .monitor import SEC13FMonitor
from .monitor_config import MonitorConfigLoader
from .visualizer import HoldingsVisualizer


@click.group()
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="启用详细输出（等价于 LOG_LEVEL=DEBUG，优先级高于环境变量）",
)
@click.option("--user-agent", default="SEC13F-Analyzer/0.1.0", help="用户代理字符串")
@click.pass_context
def cli(ctx, verbose, user_agent):
    """SEC 13F持仓分析工具

    日志等级可通过 ``LOG_LEVEL`` 环境变量控制（默认 ``INFO``，可选
    ``TRACE``/``DEBUG``/``INFO``/``SUCCESS``/``WARNING``/``ERROR``/``CRITICAL``）。
    使用 ``-v/--verbose`` 等价于设置 ``LOG_LEVEL=DEBUG``，且优先级高于环境变量。
    """
    configure_logging(level="DEBUG" if verbose else None)

    # 保存全局配置
    ctx.ensure_object(dict)
    ctx.obj["user_agent"] = user_agent
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option("--fund-name", "-n", required=True, help="基金名称（用于搜索）")
@click.pass_context
def search(ctx, fund_name):
    """搜索基金CIK编号"""
    user_agent = ctx.obj["user_agent"]

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
@click.option("--cik", "-c", required=True, help="基金CIK编号")
@click.option("--quarter", "-q", required=True, help="季度，如 2024Q3")
@click.option("--output", "-o", help="输出文件路径")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["excel", "csv", "json"]),
    default="excel",
    help="输出格式",
)
@click.pass_context
def fetch(ctx, cik, quarter, output, output_format):
    """获取13F持仓数据"""
    user_agent = ctx.obj["user_agent"]

    try:
        analyzer = SEC13FAnalyzer(user_agent)

        click.echo(f"正在获取 CIK {cik} 在 {quarter} 的持仓数据...")
        holdings = analyzer.get_holdings(cik, quarter)

        if not holdings:
            click.echo("未找到持仓数据")
            sys.exit(1)

        # 显示基本信息
        click.echo("\n✓ 成功获取持仓数据:")
        click.echo(f"  基金名称: {holdings.fund_name}")
        click.echo(f"  报告季度: {holdings.quarter}")
        click.echo(f"  期末日期: {holdings.period_end_date.strftime('%Y-%m-%d')}")
        click.echo(f"  总持仓价值: ${holdings.total_value:,.0f}")
        click.echo(f"  持仓股票数量: {len(holdings.holdings)}")

        # 导出数据
        if output or ctx.obj["verbose"]:
            exporter = DataExporter()

            if output_format == "excel":
                filepath = exporter.export_holdings_to_excel(holdings, output)
            elif output_format == "csv":
                filepath = exporter.export_to_csv(holdings, output)
            elif output_format == "json":
                filepath = exporter.export_to_json(holdings, output)

            click.echo(f"  已导出到: {filepath}")

        # 显示前20大持仓
        top_20 = analyzer.get_top_holdings(cik, quarter, 20)
        if top_20:
            click.echo("\n前20大持仓:")
            click.echo("-" * 100)
            for i, holding in enumerate(top_20, 1):
                percentage = (holding.market_value / holdings.total_value) * 100
                security_class = (
                    f"({holding.security_class})" if holding.security_class else ""
                )
                click.echo(
                    f"{i:2d}. {holding.issuer_name[:35]:35s} {security_class:20s} ${holding.market_value:>12,.0f} ({percentage:5.2f}%)"
                )

    except Exception as e:
        logger.error(f"获取持仓数据失败: {e}")
        sys.exit(1)


@cli.command()
@click.option("--cik", "-c", required=True, help="基金CIK编号")
@click.option("--from-quarter", "-f", required=True, help="起始季度，如 2024Q2")
@click.option("--to-quarter", "-t", required=True, help="结束季度，如 2024Q3")
@click.option("--output", "-o", help="输出文件路径")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["excel", "csv", "json"]),
    default="excel",
    help="输出格式",
)
@click.option("--show-plot", is_flag=True, help="显示变动图表")
@click.pass_context
def analyze(ctx, cik, from_quarter, to_quarter, output, output_format, show_plot):
    """分析持仓变动"""
    user_agent = ctx.obj["user_agent"]

    try:
        analyzer = SEC13FAnalyzer(user_agent)

        click.echo(
            f"正在分析 CIK {cik} 从 {from_quarter} 到 {to_quarter} 的持仓变动..."
        )
        holdings_change = analyzer.analyze_holdings_changes(
            cik, from_quarter, to_quarter
        )

        if not holdings_change:
            click.echo("无法获取持仓变动数据")
            sys.exit(1)

        # 显示变动统计
        click.echo("\n✓ 持仓变动分析结果:")
        click.echo(f"  基金名称: {holdings_change.fund_name}")
        click.echo(
            f"  分析期间: {holdings_change.from_quarter} → {holdings_change.to_quarter}"
        )
        click.echo(f"  期初总价值: ${holdings_change.total_prev_value:,.0f}")
        click.echo(f"  期末总价值: ${holdings_change.total_curr_value:,.0f}")
        click.echo(
            f"  总价值变动: ${holdings_change.total_value_change:,.0f} ({holdings_change.total_percentage_change:+.2f}%)"
        )

        click.echo("\n变动统计:")
        click.echo(f"  新增持仓: {len(holdings_change.new_positions)} 个")
        click.echo(f"  清仓持仓: {len(holdings_change.closed_positions)} 个")
        click.echo(f"  增持股票: {len(holdings_change.increased_positions)} 个")
        click.echo(f"  减持股票: {len(holdings_change.decreased_positions)} 个")

        # 显示重大变动
        all_changes = (
            holdings_change.new_positions
            + holdings_change.closed_positions
            + holdings_change.increased_positions
            + holdings_change.decreased_positions
        )

        # if significant_changes:
        click.echo("\n持仓变动")
        click.echo("-" * 110)
        for change in all_changes:
            change_desc = {
                "new": "新增",
                "closed": "清仓",
                "increased": "增持",
                "decreased": "减持",
            }.get(change.change_type, change.change_type)

            security_class = (
                f"({change.security_class})" if change.security_class else ""
            )
            click.echo(
                f"{change_desc:4s} {change.issuer_name[:35]:35s} {security_class:20s} ${change.value_change:>12,.0f}"
            )

        # 导出数据
        if output or ctx.obj["verbose"]:
            exporter = DataExporter()

            if output_format == "excel":
                filepath = exporter.export_holdings_changes_to_excel(
                    holdings_change, output
                )
            elif output_format == "csv":
                filepath = exporter.export_to_csv(holdings_change, output)
            elif output_format == "json":
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
@click.option("--cik", "-c", required=True, help="基金CIK编号")
@click.option("--quarter", "-q", required=True, help="季度，如 2024Q3")
@click.pass_context
def info(ctx, cik, quarter):
    """显示基金基本信息和持仓概况"""
    user_agent = ctx.obj["user_agent"]

    try:
        analyzer = SEC13FAnalyzer(user_agent)

        # 获取基金信息
        fund_info = analyzer.data_fetcher.get_fund_info(cik)
        if fund_info:
            click.echo("\n基金基本信息:")
            click.echo(f"  CIK编号: {fund_info.cik}")
            click.echo(f"  基金名称: {fund_info.fund_name}")
            if fund_info.business_address:
                click.echo(
                    f"  业务地址: {fund_info.business_address.replace(chr(10), ' ')}"
                )

        # 获取持仓数据
        holdings = analyzer.get_holdings(cik, quarter)
        if holdings:
            click.echo(f"\n{quarter} 持仓概况:")
            click.echo(f"  报告期末: {holdings.period_end_date.strftime('%Y-%m-%d')}")
            click.echo(f"  总持仓价值: ${holdings.total_value:,.0f}")
            click.echo(f"  持仓股票数量: {len(holdings.holdings)}")
        else:
            click.echo(f"未找到 {quarter} 的持仓数据")

        # 获取历史报告列表
        filings = analyzer.data_fetcher.get_13f_filings(cik, years=2)
        if filings:
            click.echo("\n最近的13F报告:")
            click.echo("-" * 50)
            for filing in filings[:10]:  # 显示最近10个
                click.echo(
                    f"  {filing['quarter']} - {filing['filing_date'].strftime('%Y-%m-%d')}"
                )

    except Exception as e:
        logger.error(f"获取基金信息失败: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--config",
    "-c",
    required=True,
    type=click.Path(exists=True),
    help="监控配置文件路径（YAML格式）",
)
@click.pass_context
def monitor(ctx, config):
    """启动 13F 监控服务"""
    try:
        # 加载配置
        click.echo(f"正在加载配置文件: {config}")
        monitor_config = MonitorConfigLoader.load(config)

        click.echo("配置验证通过")
        click.echo("监控的投资组合:")
        for portfolio in monitor_config.enabled_portfolios:
            click.echo(f"  - {portfolio.name} (CIK: {portfolio.cik})")

        click.echo("启用的 webhook:")
        for webhook in monitor_config.enabled_webhooks:
            click.echo(f"  - {webhook.name} ({webhook.type})")

        click.echo("\n准备启动监控服务...")

        # 创建并启动监控服务
        monitor_service = SEC13FMonitor(monitor_config)
        monitor_service.start()

    except FileNotFoundError as e:
        logger.error(f"配置文件不存在: {e}")
        click.echo("请使用 --config 参数指定有效的配置文件")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"配置文件错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"监控服务启动失败: {e}")
        sys.exit(1)
