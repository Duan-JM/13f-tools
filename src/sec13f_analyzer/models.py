"""
数据模型定义
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

import pandas as pd


class AmendmentType(Enum):
    """13F-HR/A修订类型"""

    RESTATEMENT = "RESTATEMENT"  # 完全重述，替换原始13F-HR
    NEW_HOLDINGS = "NEW HOLDINGS"  # 添加新持仓条目
    UNKNOWN = "UNKNOWN"  # 未知类型


@dataclass
class AmendmentInfo:
    """修订信息"""

    filing_date: datetime
    amendment_type: AmendmentType
    amendment_number: Optional[int] = None


@dataclass
class Holding:
    """单个持仓记录"""

    cusip: str
    issuer_name: str
    security_class: str
    shares_owned: int
    market_value: float  # 单位：美元
    percentage_of_portfolio: float
    voting_authority_sole: Optional[int] = None
    voting_authority_shared: Optional[int] = None
    voting_authority_none: Optional[int] = None

    def __post_init__(self):
        """后处理，计算衍生字段"""
        if self.market_value > 0 and self.shares_owned > 0:
            self.price_per_share = self.market_value / self.shares_owned
        else:
            self.price_per_share = 0.0


@dataclass
class Holdings:
    """13F报告持仓数据"""

    cik: str
    fund_name: str
    quarter: str
    period_end_date: datetime
    total_value: float  # 总持仓价值，单位：美元
    holdings: List[Holding]
    filing_date: Optional[datetime] = None
    is_amendment: bool = False  # 是否为修订版本
    amendment_info: Optional[AmendmentInfo] = None  # 修订信息
    is_merged: bool = False  # 是否为合并数据
    amendment_metadata: List[AmendmentInfo] = field(
        default_factory=list
    )  # 所有相关修订的元数据

    def __post_init__(self):
        """后处理，计算统计信息"""
        if self.holdings:
            # 计算每个持仓在总投资组合中的百分比
            for holding in self.holdings:
                if self.total_value > 0:
                    holding.percentage_of_portfolio = (
                        holding.market_value / self.total_value
                    ) * 100
                else:
                    holding.percentage_of_portfolio = 0.0

    @property
    def holdings_count(self) -> int:
        """持仓股票数量"""
        return len(self.holdings)

    def top_holdings(self, n: int = 10) -> List[Holding]:
        """获取前N大持仓"""
        return sorted(self.holdings, key=lambda x: x.market_value, reverse=True)[:n]

    def to_dataframe(self) -> pd.DataFrame:
        """转换为DataFrame"""
        data = []
        for holding in self.holdings:
            data.append(
                {
                    "cusip": holding.cusip,
                    "issuer_name": holding.issuer_name,
                    "security_class": holding.security_class,
                    "shares_owned": holding.shares_owned,
                    "market_value": holding.market_value,
                    "percentage_of_portfolio": holding.percentage_of_portfolio,
                    "price_per_share": holding.price_per_share,
                    "voting_authority_sole": holding.voting_authority_sole,
                    "voting_authority_shared": holding.voting_authority_shared,
                    "voting_authority_none": holding.voting_authority_none,
                }
            )

        df = pd.DataFrame(data)
        df["quarter"] = self.quarter
        df["fund_name"] = self.fund_name
        df["cik"] = self.cik
        return df


@dataclass
class HoldingChange:
    """持仓变化记录"""

    cusip: str
    issuer_name: str
    change_type: str  # 'new', 'increased', 'decreased', 'closed', 'unchanged'
    security_class: Optional[str] = None  # 证券类别，如 "COM", "CLASS A", "CLASS C"
    prev_shares: Optional[int] = None
    curr_shares: Optional[int] = None
    prev_value: Optional[float] = None
    curr_value: Optional[float] = None
    shares_change: Optional[int] = None
    value_change: Optional[float] = None
    percentage_change: Optional[float] = None

    def __post_init__(self):
        """计算变化量和百分比"""
        if self.prev_shares is not None and self.curr_shares is not None:
            self.shares_change = self.curr_shares - self.prev_shares

        if self.prev_value is not None and self.curr_value is not None:
            self.value_change = self.curr_value - self.prev_value

            if self.prev_value > 0:
                self.percentage_change = (self.value_change / self.prev_value) * 100
            else:
                self.percentage_change = 100.0 if self.curr_value > 0 else 0.0


@dataclass
class HoldingsChange:
    """持仓变动分析结果"""

    cik: str
    fund_name: str
    from_quarter: str
    to_quarter: str
    changes: List[HoldingChange]

    # 统计信息
    total_prev_value: float = 0.0
    total_curr_value: float = 0.0
    total_value_change: float = 0.0
    total_percentage_change: float = 0.0

    def __post_init__(self):
        """计算总体变化统计"""
        if self.total_prev_value > 0:
            self.total_value_change = self.total_curr_value - self.total_prev_value
            self.total_percentage_change = (
                self.total_value_change / self.total_prev_value
            ) * 100

    @property
    def new_positions(self) -> List[HoldingChange]:
        """新增持仓"""
        return [c for c in self.changes if c.change_type == "new"]

    @property
    def closed_positions(self) -> List[HoldingChange]:
        """清仓持仓"""
        return [c for c in self.changes if c.change_type == "closed"]

    @property
    def increased_positions(self) -> List[HoldingChange]:
        """增持"""
        return [c for c in self.changes if c.change_type == "increased"]

    @property
    def decreased_positions(self) -> List[HoldingChange]:
        """减持"""
        return [c for c in self.changes if c.change_type == "decreased"]

    def to_dataframe(self) -> pd.DataFrame:
        """转换为DataFrame"""
        data = []
        for change in self.changes:
            data.append(
                {
                    "cusip": change.cusip,
                    "issuer_name": change.issuer_name,
                    "security_class": change.security_class,
                    "change_type": change.change_type,
                    "prev_shares": change.prev_shares,
                    "curr_shares": change.curr_shares,
                    "prev_value": change.prev_value,
                    "curr_value": change.curr_value,
                    "shares_change": change.shares_change,
                    "value_change": change.value_change,
                    "percentage_change": change.percentage_change,
                }
            )

        df = pd.DataFrame(data)
        df["fund_name"] = self.fund_name
        df["cik"] = self.cik
        df["from_quarter"] = self.from_quarter
        df["to_quarter"] = self.to_quarter
        return df


@dataclass
class FundInfo:
    """基金基本信息"""

    cik: str
    fund_name: str
    business_address: Optional[str] = None
    business_phone: Optional[str] = None
    mailing_address: Optional[str] = None
