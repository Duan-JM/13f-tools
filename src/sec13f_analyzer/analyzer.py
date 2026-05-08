"""
SEC 13F持仓分析引擎

提供持仓变动分析、统计和比较功能
"""

from typing import Dict, List, Optional, Set

from loguru import logger

from .data_fetcher import SEC13FDataFetcher
from .models import Holding, HoldingChange, Holdings, HoldingsChange


class SEC13FAnalyzer:
    """SEC 13F持仓分析器"""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        company_name: Optional[str] = None,
        email: Optional[str] = None,
        config_file: Optional[str] = None,
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
        if holdings is None:
            return None

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
                    security_class=curr_holding.security_class,
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
                    security_class=prev_holding.security_class,
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
                    security_class=curr_holding.security_class,
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
