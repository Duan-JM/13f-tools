"""
SEC 13F持仓分析引擎

提供持仓变动分析、统计和比较功能
"""

from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
from loguru import logger

from .data_fetcher import SEC13FDataFetcher
from .models import Holding, HoldingChange, Holdings, HoldingsChange


class SEC13FAnalyzer:
    """SEC 13F持仓分析器"""

    def __init__(
        self,
        user_agent: str = None,
        company_name: str = None,
        email: str = None,
        config_file: str = None,
    ):
        """
        初始化分析器

        Args:
            user_agent: 用户代理字符串，如果不提供会自动生成
            company_name: 公司名称，用于生成User-Agent
            email: 联系邮箱，用于生成User-Agent
            config_file: 配置文件路径
        """
        self.data_fetcher = SEC13FDataFetcher(
            user_agent, company_name, email, config_file
        )
        self._holdings_cache: Dict[str, Holdings] = {}

    def _if_contain_duplicated_cusip(self, holdings: Holdings) -> bool:
        """
        检查持仓中是否存在重复的CUSIP

        Args:
            holdings: Holdings对象

        Returns:
            bool: 是否存在重复CUSIP
        """
        cusip_set: Set[str] = set()
        for holding in holdings.holdings:
            if holding.cusip in cusip_set:
                logger.warning(f"发现重复CUSIP: {holding.cusip}")
                return True
            cusip_set.add(holding.cusip)
        return False

    def get_holdings(
        self, cik: str, quarter: str, use_cache: bool = True
    ) -> Optional[Holdings]:
        """
        获取指定季度的持仓数据

        Args:
            cik: 基金CIK编号
            quarter: 季度，如 "2024Q3"
            use_cache: 是否使用缓存

        Returns:
            Holdings对象或None
        """
        cache_key = f"{cik}_{quarter}"

        if use_cache and cache_key in self._holdings_cache:
            return self._holdings_cache[cache_key]

        holdings = self.data_fetcher.get_holdings_data(cik, quarter)

        if self._if_contain_duplicated_cusip(holdings):
            # 以求和逻辑处理 holdings.holdings 中的 Holding
            # 求和 Holding 中的 shares_owned: int
            # 求和 Holding 中的 market_value: float
            logger.warning(f"处理重复CUSIP: {cik} {quarter}")
            aggregated_holdings: Dict[str, Holding] = {}
            for holding in holdings.holdings:
                if holding.cusip in aggregated_holdings:
                    aggregated_holdings[
                        holding.cusip
                    ].shares_owned += holding.shares_owned
                    aggregated_holdings[
                        holding.cusip
                    ].market_value += holding.market_value
                else:
                    aggregated_holdings[holding.cusip] = holding
            holdings.holdings = list(aggregated_holdings.values())

        if holdings and use_cache:
            self._holdings_cache[cache_key] = holdings

        return holdings

    def analyze_holdings_changes(
        self, cik: str, from_quarter: str, to_quarter: str
    ) -> Optional[HoldingsChange]:
        """
        分析两个季度之间的持仓变动

        Args:
            cik: 基金CIK编号
            from_quarter: 起始季度
            to_quarter: 结束季度

        Returns:
            HoldingsChange对象或None
        """
        # 获取两个季度的持仓数据
        prev_holdings = self.get_holdings(cik, from_quarter)
        curr_holdings = self.get_holdings(cik, to_quarter)

        if not prev_holdings or not curr_holdings:
            logger.error(
                f"无法获取 CIK {cik} 在 {from_quarter} 或 {to_quarter} 的持仓数据"
            )
            return None

        # 创建CUSIP到持仓的映射
        prev_holdings_map = {h.cusip: h for h in prev_holdings.holdings}
        curr_holdings_map = {h.cusip: h for h in curr_holdings.holdings}

        # 获取所有CUSIP
        all_cusips = set(prev_holdings_map.keys()) | set(curr_holdings_map.keys())

        changes = []

        for cusip in all_cusips:
            prev_holding = prev_holdings_map.get(cusip)
            curr_holding = curr_holdings_map.get(cusip)

            # 确定变动类型
            if prev_holding and curr_holding:
                # 持续持有
                if prev_holding.shares_owned == curr_holding.shares_owned:
                    change_type = "unchanged"
                elif prev_holding.shares_owned < curr_holding.shares_owned:
                    change_type = "increased"
                else:
                    change_type = "decreased"

                change = HoldingChange(
                    cusip=cusip,
                    issuer_name=curr_holding.issuer_name,
                    change_type=change_type,
                    prev_shares=prev_holding.shares_owned,
                    curr_shares=curr_holding.shares_owned,
                    prev_value=prev_holding.market_value,
                    curr_value=curr_holding.market_value,
                )

            elif prev_holding and not curr_holding:
                # 清仓
                change = HoldingChange(
                    cusip=cusip,
                    issuer_name=prev_holding.issuer_name,
                    change_type="closed",
                    prev_shares=prev_holding.shares_owned,
                    curr_shares=0,
                    prev_value=prev_holding.market_value,
                    curr_value=0.0,
                )

            elif not prev_holding and curr_holding:
                # 新增
                change = HoldingChange(
                    cusip=cusip,
                    issuer_name=curr_holding.issuer_name,
                    change_type="new",
                    prev_shares=0,
                    curr_shares=curr_holding.shares_owned,
                    prev_value=0.0,
                    curr_value=curr_holding.market_value,
                )
            else:
                continue  # 不应该发生

            changes.append(change)

        # 创建持仓变动对象
        holdings_change = HoldingsChange(
            cik=cik,
            fund_name=curr_holdings.fund_name,
            from_quarter=from_quarter,
            to_quarter=to_quarter,
            changes=changes,
            total_prev_value=prev_holdings.total_value,
            total_curr_value=curr_holdings.total_value,
        )

        return holdings_change

    def get_top_holdings(self, cik: str, quarter: str, n: int = 20) -> List[Holding]:
        """
        获取前N大持仓

        Args:
            cik: 基金CIK编号
            quarter: 季度
            n: 返回前N个

        Returns:
            前N大持仓列表
        """
        holdings = self.get_holdings(cik, quarter)
        if not holdings:
            return []

        return sorted(holdings.holdings, key=lambda x: x.market_value, reverse=True)[:n]

    # TODO: No use for now
    def get_sector_allocation(self, cik: str, quarter: str) -> Dict[str, float]:
        """
        获取行业配置（需要外部数据源映射CUSIP到行业）

        Args:
            cik: 基金CIK编号
            quarter: 季度

        Returns:
            行业配置字典 {行业: 占比}
        """
        holdings = self.get_holdings(cik, quarter)
        if not holdings:
            return {}

        # 这里需要实现CUSIP到行业的映射
        # 暂时返回空字典，实际应用中需要集成行业分类数据
        logger.warning("行业配置分析需要外部行业分类数据源")
        return {}

    # No use for now
    def calculate_concentration(self, cik: str, quarter: str) -> Dict[str, float]:
        """
        计算持仓集中度指标

        Args:
            cik: 基金CIK编号
            quarter: 季度

        Returns:
            集中度指标字典
        """
        holdings = self.get_holdings(cik, quarter)
        if not holdings:
            return {}

        # 按持仓价值排序
        sorted_holdings = sorted(
            holdings.holdings, key=lambda x: x.market_value, reverse=True
        )

        # 计算前N大持仓占比
        top_5_pct = (
            sum(h.market_value for h in sorted_holdings[:5])
            / holdings.total_value
            * 100
        )
        top_10_pct = (
            sum(h.market_value for h in sorted_holdings[:10])
            / holdings.total_value
            * 100
        )
        top_20_pct = (
            sum(h.market_value for h in sorted_holdings[:20])
            / holdings.total_value
            * 100
        )

        # 计算赫芬达尔指数（HHI）
        hhi = (
            sum((h.market_value / holdings.total_value) ** 2 for h in holdings.holdings)
            * 10000
        )

        return {
            "top_5_percentage": top_5_pct,
            "top_10_percentage": top_10_pct,
            "top_20_percentage": top_20_pct,
            "herfindahl_index": hhi,
            "total_positions": len(holdings.holdings),
        }

    # No use for now
    def track_holding_over_time(
        self, cik: str, cusip: str, quarters: List[str]
    ) -> pd.DataFrame:
        """
        追踪特定股票在多个季度的持仓变化

        Args:
            cik: 基金CIK编号
            cusip: 股票CUSIP编号
            quarters: 季度列表

        Returns:
            包含持仓历史的DataFrame
        """
        data = []

        for quarter in quarters:
            holdings = self.get_holdings(cik, quarter)
            if holdings:
                # 查找指定CUSIP的持仓
                target_holding = None
                for holding in holdings.holdings:
                    if holding.cusip == cusip:
                        target_holding = holding
                        break

                if target_holding:
                    data.append(
                        {
                            "quarter": quarter,
                            "shares_owned": target_holding.shares_owned,
                            "market_value": target_holding.market_value,
                            "percentage_of_portfolio": target_holding.percentage_of_portfolio,
                            "price_per_share": target_holding.price_per_share,
                            "issuer_name": target_holding.issuer_name,
                        }
                    )
                else:
                    # 该季度没有持仓
                    data.append(
                        {
                            "quarter": quarter,
                            "shares_owned": 0,
                            "market_value": 0.0,
                            "percentage_of_portfolio": 0.0,
                            "price_per_share": 0.0,
                            "issuer_name": "N/A",
                        }
                    )

        return pd.DataFrame(data)

    # TODO: No use for now
    def compare_funds(
        self, ciks: List[str], quarter: str, metric: str = "total_value"
    ) -> pd.DataFrame:
        """
        比较多个基金在同一季度的表现

        Args:
            ciks: 基金CIK列表
            quarter: 季度
            metric: 比较指标 ("total_value", "holdings_count", "concentration")

        Returns:
            比较结果DataFrame
        """
        comparison_data = []

        for cik in ciks:
            holdings = self.get_holdings(cik, quarter)
            if holdings:
                row = {
                    "cik": cik,
                    "fund_name": holdings.fund_name,
                    "quarter": quarter,
                    "total_value": holdings.total_value,
                    "holdings_count": len(holdings.holdings),
                }

                # 添加集中度指标
                if metric == "concentration":
                    concentration = self.calculate_concentration(cik, quarter)
                    row.update(concentration)

                comparison_data.append(row)

        return pd.DataFrame(comparison_data)

    def find_common_holdings(
        self, ciks: List[str], quarter: str, min_funds: int = 2
    ) -> List[Dict]:
        """
        查找多个基金的共同持仓

        Args:
            ciks: 基金CIK列表
            quarter: 季度
            min_funds: 最少持有该股票的基金数量

        Returns:
            共同持仓列表
        """
        # 收集所有基金的持仓
        all_holdings = {}
        fund_names = {}

        for cik in ciks:
            holdings = self.get_holdings(cik, quarter)
            if holdings:
                fund_names[cik] = holdings.fund_name
                for holding in holdings.holdings:
                    cusip = holding.cusip
                    if cusip not in all_holdings:
                        all_holdings[cusip] = {
                            "issuer_name": holding.issuer_name,
                            "funds": {},
                        }

                    all_holdings[cusip]["funds"][cik] = {
                        "shares_owned": holding.shares_owned,
                        "market_value": holding.market_value,
                        "percentage_of_portfolio": holding.percentage_of_portfolio,
                    }

        # 筛选共同持仓
        common_holdings = []
        for cusip, data in all_holdings.items():
            if len(data["funds"]) >= min_funds:
                common_holding = {
                    "cusip": cusip,
                    "issuer_name": data["issuer_name"],
                    "holding_funds_count": len(data["funds"]),
                    "funds": data["funds"],
                }

                # 计算总持仓价值
                total_value = sum(
                    fund_data["market_value"] for fund_data in data["funds"].values()
                )
                common_holding["total_market_value"] = total_value

                common_holdings.append(common_holding)

        # 按总持仓价值排序
        return sorted(
            common_holdings, key=lambda x: x["total_market_value"], reverse=True
        )

    # TODO: No use for now
    def analyze_turnover(
        self, cik: str, from_quarter: str, to_quarter: str
    ) -> Dict[str, float]:
        """
        分析投资组合换手率

        Args:
            cik: 基金CIK编号
            from_quarter: 起始季度
            to_quarter: 结束季度

        Returns:
            换手率指标字典
        """
        prev_holdings = self.get_holdings(cik, from_quarter)
        curr_holdings = self.get_holdings(cik, to_quarter)

        if not prev_holdings or not curr_holdings:
            return {}

        # 计算买入和卖出金额
        prev_cusips = {h.cusip: h.market_value for h in prev_holdings.holdings}
        curr_cusips = {h.cusip: h.market_value for h in curr_holdings.holdings}

        # 计算卖出金额（上期有，本期没有或减少）
        sells = 0.0
        for cusip, prev_value in prev_cusips.items():
            curr_value = curr_cusips.get(cusip, 0.0)
            if curr_value < prev_value:
                sells += prev_value - curr_value

        # 计算买入金额（上期没有或本期增加）
        buys = 0.0
        for cusip, curr_value in curr_cusips.items():
            prev_value = prev_cusips.get(cusip, 0.0)
            if curr_value > prev_value:
                buys += curr_value - prev_value

        # 计算换手率
        avg_portfolio_value = (
            prev_holdings.total_value + curr_holdings.total_value
        ) / 2

        if avg_portfolio_value > 0:
            turnover_rate = (buys + sells) / (2 * avg_portfolio_value) * 100
            buy_turnover = buys / avg_portfolio_value * 100
            sell_turnover = sells / avg_portfolio_value * 100
        else:
            turnover_rate = buy_turnover = sell_turnover = 0.0

        return {
            "turnover_rate": turnover_rate,
            "buy_turnover": buy_turnover,
            "sell_turnover": sell_turnover,
            "total_buys": buys,
            "total_sells": sells,
            "avg_portfolio_value": avg_portfolio_value,
        }
