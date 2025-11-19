"""
SEC 13F数据获取模块

从SEC EDGAR数据库获取13F报告数据
"""

import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from loguru import logger
from tqdm import tqdm

from .config import get_config
from .models import FundInfo, Holding, Holdings


class SEC13FDataFetcher:
    """SEC 13F数据获取器"""
    
    BASE_URL = "https://www.sec.gov"
    EDGAR_URL = "https://www.sec.gov/edgar"
    SEARCH_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
    
    def __init__(self, user_agent: str = None, company_name: str = None, email: str = None, config_file: str = None):
        """
        初始化数据获取器
        
        Args:
            user_agent: 用户代理字符串，如果不提供会自动生成符合SEC要求的格式
            company_name: 公司名称，用于生成User-Agent
            email: 联系邮箱，用于生成User-Agent
            config_file: 配置文件路径
        """
        # 加载配置
        self.config = get_config(config_file)
        
        # 验证配置
        config_errors = self.config.validate_config()
        if config_errors:
            logger.warning(f"配置验证失败: {'; '.join(config_errors)}")
        
        # 确定User-Agent
        if user_agent:
            final_user_agent = user_agent
        elif company_name and email:
            # 使用更现代的User-Agent格式，避免被识别为爬虫
            final_user_agent = f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 {company_name}-SEC13F-Analyzer/1.0 ({email})"
        else:
            final_user_agent = self.config.get_user_agent()
        
        logger.info(f"使用User-Agent: {final_user_agent}")
        
        # 获取URL配置
        self.BASE_URL = self.config.get_base_url()
        self.EDGAR_URL = self.config.get_edgar_url()
        self.SEARCH_URL = self.config.get_search_url()
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': final_user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        })
        
        # 从配置获取请求参数
        self.request_delay = self.config.get_request_delay()
        self.max_retries = self.config.get_max_retries()
        self.timeout = self.config.get_timeout()
        self.last_request_time = 0
        
        logger.info(f"请求延迟: {self.request_delay}秒, 最大重试: {self.max_retries}次")
        
    def _wait_if_needed(self):
        """控制请求频率，遵守SEC访问限制"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> requests.Response:
        """发送HTTP请求，包含重试逻辑"""
        self._wait_if_needed()
        
        logger.info(f"请求URL: {url}")
        if params:
            logger.debug(f"请求参数: {params}")
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"尝试请求 {attempt + 1}/{self.max_retries}")
                response = self.session.get(url, params=params, timeout=self.timeout)
                
                logger.info(f"响应状态码: {response.status_code}")
                logger.debug(f"响应头: {dict(response.headers)}")
                
                # 处理403错误
                if response.status_code == 403:
                    logger.warning(f"收到403错误，响应内容: {response.text[:500]}")
                    logger.warning(f"请求头: {dict(self.session.headers)}")
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.info(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)  # 指数退避
                        continue
                
                # 处理其他HTTP错误
                if response.status_code >= 400:
                    logger.warning(f"HTTP错误 {response.status_code}: {response.text[:200]}")
                
                response.raise_for_status()
                logger.info("请求成功")
                return response
                
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP错误: {e}")
                if hasattr(e, 'response') and e.response.status_code == 403:
                    logger.error("SEC拒绝访问的可能原因:")
                    logger.error("1) User-Agent不符合SEC要求（必须包含公司名和联系方式）")
                    logger.error("2) 访问频率过高（SEC限制每秒不超过10个请求）")
                    logger.error("3) IP地址被临时限制")
                    logger.error("4) 需要更真实的浏览器headers")
                    if attempt == self.max_retries - 1:
                        raise Exception(f"SEC访问被拒绝: {e}")
                else:
                    if attempt == self.max_retries - 1:
                        raise
            except requests.exceptions.Timeout as e:
                logger.error(f"请求超时: {e}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"请求超时，可能网络连接不稳定: {e}")
                time.sleep(2)  # 超时后等待2秒
            except requests.RequestException as e:
                logger.error(f"请求失败 {url} (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"网络请求失败: {e}")
                time.sleep(1)  # 等待1秒后重试
    
    def search_fund_cik(self, fund_name: str) -> List[Tuple[str, str]]:
        """
        根据基金名称搜索CIK
        
        Args:
            fund_name: 基金名称
            
        Returns:
            List[(cik, fund_name)] 搜索结果列表
        """
        params = {
            'action': 'getcompany',
            'company': fund_name,
            'type': '13F',  # 搜索所有13F相关报告，包括13F-HR和13F-HR/A
            'dateb': '',
            'count': '40',
        }
        
        response = self._make_request(self.SEARCH_URL, params)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        results = []
        
        # 情况1: 搜索结果页面（包含多个公司的表格）
        table = soup.find('table', {'class': 'tableFile2'})
        if not table:
            # 尝试其他可能的表格结构
            table = soup.find('table')
        
        if table:
            rows = table.find_all('tr')[1:]  # 跳过表头
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    company_link = cells[0].find('a')
                    if company_link:
                        # 从链接文本获取公司名称
                        company_name = company_link.text.strip()
                        href = company_link.get('href', '')
                        
                        # 从链接中提取CIK
                        cik_match = re.search(r'CIK=(\d+)', href)
                        if cik_match:
                            cik = cik_match.group(1).zfill(10)  # 补足10位
                            
                            # 如果公司名称是CIK编号，尝试从href或其他地方获取真实名称
                            if company_name.isdigit() or company_name == cik:
                                # 尝试从页面其他地方获取公司名称
                                # 查看下一个cell是否包含公司名称
                                if len(cells) > 1:
                                    potential_name = cells[1].text.strip()
                                    if potential_name and not potential_name.isdigit():
                                        company_name = potential_name
                                
                                # 如果还是没有找到合适的名称，保持CIK
                                if company_name.isdigit():
                                    company_name = f"Fund-{cik}"
                            
                            results.append((cik, company_name))
        
        # 情况2: 直接跳转到公司详情页面（单个匹配结果）
        # 查找公司信息部分
        if not results:
            company_info = soup.find('div', {'class': 'companyInfo'})
            if company_info:
                # 提取公司名称
                company_name_span = company_info.find('span', {'class': 'companyName'})
                if company_name_span:
                    # 提取公司名称（移除CIK信息）
                    full_text = company_name_span.get_text()
                    company_name = full_text.split('CIK')[0].strip()
                    
                    # 从链接中提取CIK
                    cik_link = company_name_span.find('a')
                    if cik_link:
                        href = cik_link.get('href', '')
                        cik_match = re.search(r'CIK=(\d+)', href)
                        if cik_match:
                            cik = cik_match.group(1).zfill(10)
                            results.append((cik, company_name))
        
        # 情况3: 从页面内容的所有链接中提取CIK
        if not results:
            # 查找所有包含CIK的链接
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                cik_match = re.search(r'CIK=(\d+)', href)
                if cik_match:
                    cik = cik_match.group(1).zfill(10)
                    
                    # 尝试从链接文本获取公司名称
                    link_text = link.get_text().strip()
                    if link_text and not link_text.isdigit() and len(link_text) > 2:
                        company_name = link_text
                    else:
                        # 尝试从链接的父元素或兄弟元素获取名称
                        parent = link.parent
                        if parent:
                            parent_text = parent.get_text().strip()
                            # 从父元素文本中提取公司名称（移除CIK等信息）
                            lines = [line.strip() for line in parent_text.split('\n') if line.strip()]
                            for line in lines:
                                if not line.isdigit() and 'CIK' not in line and len(line) > 3:
                                    company_name = line
                                    break
                            else:
                                company_name = fund_name  # 使用搜索的名称作为备选
                        else:
                            company_name = fund_name
                    
                    results.append((cik, company_name))
                    break  # 找到第一个结果就停止
            
        # 情况4: 检查RSS feed链接
        if not results:
            rss_link = soup.find('link', {'rel': 'alternate', 'type': 'application/atom+xml'})
            if rss_link:
                href = rss_link.get('href', '')
                cik_match = re.search(r'CIK=(\d+)', href)
                if cik_match:
                    cik = cik_match.group(1).zfill(10)
                    company_name = fund_name  # 使用搜索的名称
                    results.append((cik, company_name))
        
        # 如果没有找到结果，记录调试信息
        if not results:
            logger.warning(f"未找到'{fund_name}'的搜索结果")
            logger.debug(f"响应内容预览: {response.text[:1000]}")
        
        return results
    
    def get_fund_info(self, cik: str) -> Optional[FundInfo]:
        """
        获取基金基本信息
        
        Args:
            cik: 基金的CIK编号
            
        Returns:
            FundInfo对象或None
        """
        params = {
            'action': 'getcompany', 
            'CIK': cik,
            'type': '13F',  # 获取所有13F相关报告信息
            'dateb': '',
            'count': '10',
        }
        
        try:
            response = self._make_request(self.SEARCH_URL, params)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 提取公司名称
            company_info = soup.find('div', {'class': 'companyInfo'})
            fund_name = ""
            if company_info:
                company_name_span = company_info.find('span', {'class': 'companyName'})
                if company_name_span:
                    fund_name = company_name_span.text.strip()
                    # 移除CIK信息
                    fund_name = re.sub(r'\s+CIK.*$', '', fund_name)
            
            # 提取地址信息
            business_address = None
            mailing_address = None
            
            address_divs = soup.find_all('div', {'class': 'mailer'})
            for div in address_divs:
                addr_text = div.get_text(separator='\n').strip()
                if 'Business Address' in addr_text:
                    business_address = addr_text
                elif 'Mailing Address' in addr_text:
                    mailing_address = addr_text
            
            return FundInfo(
                cik=cik,
                fund_name=fund_name,
                business_address=business_address,
                mailing_address=mailing_address
            )
            
        except Exception as e:
            logger.error(f"获取基金信息失败 CIK {cik}: {e}")
            return None
    
    def get_13f_filings(self, cik: str, years: int = 2) -> List[Dict]:
        """
        获取13F报告列表
        
        Args:
            cik: 基金的CIK编号
            years: 获取多少年内的报告
            
        Returns:
            13F报告信息列表
        """
        params = {
            'action': 'getcompany',
            'CIK': cik,
            'type': '13F',  # 获取所有13F相关报告，包括13F-HR和13F-HR/A
            'dateb': '',
            'count': '100',
        }
        
        response = self._make_request(self.SEARCH_URL, params)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        filings = []
        cutoff_date = datetime.now() - timedelta(days=365 * years)
        
        # 解析报告列表表格
        table = soup.find('table', {'class': 'tableFile2'})
        if table:
            rows = table.find_all('tr')[1:]  # 跳过表头
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 4:
                    # 提取报告链接
                    document_link = cells[1].find('a')
                    if document_link:
                        filing_url = urljoin(self.BASE_URL, document_link.get('href'))
                        
                        # 提取报告描述和类型
                        description = cells[2].text.strip()
                        
                        is_amendment = 'Amend' in description or '/A' in description
                        filing_type = '13F-HR/A' if is_amendment else '13F-HR'
                        
                        # 提取报告日期
                        filing_date_str = cells[3].text.strip()
                        try:
                            filing_date = datetime.strptime(filing_date_str, '%Y-%m-%d')
                            
                            # 只获取指定年限内的报告
                            if filing_date >= cutoff_date:
                                # 解析季度信息
                                quarter = self._parse_quarter_from_date(filing_date)
                                
                                filings.append({
                                    'filing_date': filing_date,
                                    'quarter': quarter,
                                    'url': filing_url,
                                    'description': description,
                                    'filing_type': filing_type,
                                    'is_amendment': is_amendment,
                                })
                            
                        except ValueError:
                            logger.warning(f"无法解析日期: {filing_date_str}")
                            continue
        
        return sorted(filings, key=lambda x: x['filing_date'], reverse=True)
    
    def _parse_quarter_from_date(self, filing_date: datetime) -> str:
        """
        根据填报日期解析对应的持仓报告季度
        
        13F报告需要在季度结束后45天内提交，所以：
        - 2-5月份的填报 -> 上一年Q4或当年Q1
        - 5-8月份的填报 -> 当年Q1或Q2  
        - 8-11月份的填报 -> 当年Q2或Q3
        - 11月-次年2月的填报 -> 当年Q3或Q4
        
        Args:
            filing_date: 填报日期
            
        Returns:
            对应的报告季度，格式如 "2024Q3"
        """
        year = filing_date.year
        month = filing_date.month
        day = filing_date.day
        
        # 根据填报时间推断报告季度
        # 考虑45天的填报期限，以及一些机构可能提前或延迟提交
        if month <= 2 or (month == 3 and day <= 15):
            # 1-2月及3月上半月的填报 -> 上一年Q4
            quarter = f"{year-1}Q4"
        elif month <= 5 or (month == 6 and day <= 15):
            # 3月下半月-5月及6月上半月的填报 -> 当年Q1
            quarter = f"{year}Q1"
        elif month <= 8 or (month == 9 and day <= 15):
            # 6月下半月-8月及9月上半月的填报 -> 当年Q2
            quarter = f"{year}Q2"
        elif month <= 11 or (month == 12 and day <= 15):
            # 9月下半月-11月及12月上半月的填报 -> 当年Q3
            quarter = f"{year}Q3"
        else:
            # 12月下半月的填报 -> 当年Q4
            quarter = f"{year}Q4"
            
        return quarter
    
    def get_holdings_data(self, cik: str, quarter: str) -> Optional[Holdings]:
        """
        获取指定季度的13F持仓数据
        
        Args:
            cik: 基金的CIK编号
            quarter: 季度，格式如 "2024Q3"
            
        Returns:
            Holdings对象或None
        """
        # 首先获取13F报告列表
        filings = self.get_13f_filings(cik, years=3)
        
        # 找到对应季度的所有报告（包括13F-HR和13F-HR/A）
        quarter_filings = [filing for filing in filings if filing['quarter'] == quarter]
        
        if not quarter_filings:
            logger.warning(f"未找到 CIK {cik} 在 {quarter} 的13F报告")
            return None
        
        # 分析该季度的报告类型
        hr_filings = [f for f in quarter_filings if not f['is_amendment']]
        hra_filings = [f for f in quarter_filings if f['is_amendment']]
        
        # 检查是否存在修订版本并发出警告
        if hra_filings:
            hra_dates = [f['filing_date'].strftime('%Y-%m-%d') for f in hra_filings]
            logger.warning(f"⚠️  CIK {cik} 在 {quarter} 季度存在13F-HR/A修订版本 (提交日期: {', '.join(hra_dates)})，建议人工检查原始报告和修订版本的差异")
        
        # 选择目标报告：优先使用13F-HR，如果没有则跳过该季度
        target_filing = None
        if hr_filings:
            # 如果有多个13F-HR，选择最新的
            target_filing = max(hr_filings, key=lambda x: x['filing_date'])
            logger.info(f"选择13F-HR报告 (提交日期: {target_filing['filing_date'].strftime('%Y-%m-%d')})")
        else:
            # 只有13F-HR/A，跳过并警告
            logger.warning(f"❌ CIK {cik} 在 {quarter} 季度只有13F-HR/A修订版本，跳过该季度。建议人工检查修订版本内容。")
            return None
        
        # 获取报告详细页面
        response = self._make_request(target_filing['url'])
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 查找13F-HR表格链接
        table_link = None
        document_links = []
        
        # 收集所有可能的文档链接，包括周围的上下文
        for link in soup.find_all('a'):
            href = link.get('href', '')
            text = link.text.strip().lower()
            
            if href:
                # 获取链接周围的上下文（父级td和相邻td的文本）
                context_text = ""
                if link.parent:
                    # 获取父级单元格和相邻单元格的文本
                    parent_row = link.parent.parent if link.parent.parent else None
                    if parent_row:
                        cells = parent_row.find_all(['td', 'th'])
                        context_text = " ".join([cell.get_text().strip() for cell in cells])
                
                combined_text = f"{text} {context_text}".lower()
                document_links.append((href, text, combined_text))
        
        # 优先查找Information Table文件
        priority_patterns = [
            # 最高优先级：直接的XML文件，不是XSL转换的HTML版本
            (lambda href, text, context: 'form13finfotable.xml' in href.lower() and 'xsl' not in href.lower(), "直接XML版本的Information Table"),
            (lambda href, text, context: 'information table' in context and '.xml' in href and 'xsl' not in href.lower(), "Information Table 直接XML"),
            
            # 次优先级：XSL转换的版本（虽然显示为HTML但可能有XML数据）
            (lambda href, text, context: 'form13finfotable.xml' in href.lower(), "Information Table XML文件"),
            (lambda href, text, context: 'information table' in context and '.xml' in href, "Information Table XML"),
            
            # 中等优先级：其他可能的文件
            (lambda href, text, context: 'infotable' in href.lower() and '.xml' in href, "Info Table XML"),
            (lambda href, text, context: 'holdings' in context and '.xml' in href, "Holdings XML"),
            
            # 低优先级：备选文件
            (lambda href, text, context: 'primary_doc.xml' in href and '.xml' in href, "Primary Doc XML"),
        ]
        
        for pattern_func, pattern_desc in priority_patterns:
            for href, text, context in document_links:
                if pattern_func(href, text, context):
                    table_link = urljoin(self.BASE_URL, href)
                    logger.info(f"找到13F-HR文件 ({pattern_desc}): {text} -> {table_link}")
                    break
            if table_link:
                break
        
        # 如果没有找到明确的13F-HR文件，尝试其他策略
        if not table_link:
            # 查找第一个.xml文件
            for href, text, context in document_links:
                if href.endswith('.xml'):
                    table_link = urljoin(self.BASE_URL, href)
                    logger.info(f"备选文件: {text} -> {table_link}")
                    break
        
        if not table_link:
            logger.error(f"未找到 {quarter} 的13F-HR表格文件")
            logger.debug(f"可用的文档链接: {document_links}")
            return None
        
        # 下载并解析持仓数据
        return self._parse_holdings_from_file(table_link, cik, quarter)
    
    def _parse_holdings_from_file(self, file_url: str, cik: str, quarter: str) -> Optional[Holdings]:
        """
        从13F-HR文件解析持仓数据
        
        Args:
            file_url: 13F-HR文件URL
            cik: 基金CIK
            quarter: 季度
            
        Returns:
            Holdings对象或None
        """
        try:
            response = self._make_request(file_url)
            content = response.text
            
            # 基金信息
            fund_info = self.get_fund_info(cik)
            fund_name = fund_info.fund_name if fund_info else f"Fund-{cik}"
            
            holdings = []
            total_value = 0.0
            period_end_date = None
            
            if file_url.endswith('.xml'):
                holdings, total_value, period_end_date = self._parse_xml_holdings(content)
            else:
                holdings, total_value, period_end_date = self._parse_txt_holdings(content)
            
            if not period_end_date:
                # 如果无法从文件中提取日期，根据季度推断
                period_end_date = self._quarter_to_date(quarter)
            
            return Holdings(
                cik=cik,
                fund_name=fund_name,
                quarter=quarter,
                period_end_date=period_end_date,
                total_value=total_value,
                holdings=holdings
            )
            
        except Exception as e:
            logger.error(f"解析持仓文件失败 {file_url}: {e}")
            return None
    
    def _parse_xml_holdings(self, xml_content: str) -> Tuple[List[Holding], float, Optional[datetime]]:
        """解析XML格式的13F-HR文件"""
        from xml.etree import ElementTree as ET
        
        holdings = []
        total_value = 0.0
        period_end_date = None
        
        try:
            # 尝试清理XML内容
            cleaned_content = xml_content
            
            # 如果内容是HTML格式，尝试提取XML部分
            if '<html' in xml_content.lower():
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(xml_content, 'html.parser')
                
                # 查找XML数据
                xml_script = soup.find('script', {'type': 'text/xml'})
                if xml_script:
                    cleaned_content = xml_script.string
                else:
                    # 查找pre标签中的XML
                    pre_tag = soup.find('pre')
                    if pre_tag:
                        cleaned_content = pre_tag.get_text()
                    else:
                        logger.warning("HTML页面中未找到XML数据，尝试解析HTML表格")
                        return self._parse_html_table(xml_content)
            
            # 尝试解析XML
            root = ET.fromstring(cleaned_content)
            
            # 查找命名空间
            ns = {}
            if root.tag.startswith('{'):
                ns_uri = root.tag.split('}')[0][1:]
                ns['ns'] = ns_uri
            
            # 提取报告期结束日期
            period_elem = root.find('.//ns:reportCalendarOrQuarter' if ns else './/reportCalendarOrQuarter', ns)
            if period_elem is not None:
                try:
                    period_end_date = datetime.strptime(period_elem.text, '%m-%d-%Y')
                except ValueError:
                    try:
                        period_end_date = datetime.strptime(period_elem.text, '%Y-%m-%d')
                    except ValueError:
                        pass
            
            # 提取持仓信息
            info_table = root.find('.//ns:informationTable' if ns else './/informationTable', ns)
            if info_table is None:
                # 尝试其他可能的根元素
                if 'informationTable' in root.tag:
                    info_table = root
                else:
                    # 查找所有可能包含持仓数据的元素
                    for elem in root.iter():
                        if 'table' in elem.tag.lower() or 'info' in elem.tag.lower():
                            info_table = elem
                            break
            
            if info_table is not None:
                # 查找持仓条目
                entry_tags = ['infoTable', 'holdingInfo', 'holding', 'entry']
                entries = []
                
                for tag in entry_tags:
                    entries = info_table.findall(f'.//ns:{tag}' if ns else f'.//{tag}', ns)
                    if entries:
                        break
                
                for entry in entries:
                    try:
                        # 提取各字段
                        cusip_elem = entry.find('.//ns:cusip' if ns else './/cusip', ns)
                        name_elem = entry.find('.//ns:nameOfIssuer' if ns else './/nameOfIssuer', ns)
                        class_elem = entry.find('.//ns:titleOfClass' if ns else './/titleOfClass', ns)
                        shares_elem = entry.find('.//ns:sshPrnamt' if ns else './/sshPrnamt', ns)
                        value_elem = entry.find('.//ns:value' if ns else './/value', ns)
                        
                        if all(elem is not None for elem in [cusip_elem, name_elem, shares_elem, value_elem]):
                            cusip = cusip_elem.text.strip()
                            issuer_name = name_elem.text.strip()
                            security_class = class_elem.text.strip() if class_elem is not None else "COM"
                            shares_owned = int(shares_elem.text)
                            market_value = float(value_elem.text) * 1000  # SEC以千美元为单位
                            
                            # 投票权信息
                            sole_elem = entry.find('.//ns:Sole' if ns else './/Sole', ns)
                            shared_elem = entry.find('.//ns:Shared' if ns else './/Shared', ns)  
                            none_elem = entry.find('.//ns:None' if ns else './/None', ns)
                            
                            voting_sole = int(sole_elem.text) if sole_elem is not None and sole_elem.text else None
                            voting_shared = int(shared_elem.text) if shared_elem is not None and shared_elem.text else None
                            voting_none = int(none_elem.text) if none_elem is not None and none_elem.text else None
                            
                            holding = Holding(
                                cusip=cusip,
                                issuer_name=issuer_name,
                                security_class=security_class,
                                shares_owned=shares_owned,
                                market_value=market_value,
                                percentage_of_portfolio=0.0,  # 稍后计算
                                voting_authority_sole=voting_sole,
                                voting_authority_shared=voting_shared,
                                voting_authority_none=voting_none
                            )
                            
                            holdings.append(holding)
                            total_value += market_value
                            
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"跳过无效的持仓记录: {e}")
                        continue
                        
        except ET.ParseError as e:
            logger.error(f"XML解析错误: {e}")
            # 如果XML解析失败，尝试HTML表格解析
            return self._parse_html_table(xml_content)
            
        return holdings, total_value, period_end_date
    
    def _parse_html_table(self, html_content: str) -> Tuple[List[Holding], float, Optional[datetime]]:
        """解析HTML表格中的13F数据"""
        from bs4 import BeautifulSoup
        
        holdings = []
        total_value = 0.0
        period_end_date = None
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找表格
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                
                # 查找包含持仓数据的表格（通常包含CUSIP等列）
                header_row = None
                data_rows = []
                
                for i, row in enumerate(rows):
                    cells = row.find_all(['th', 'td'])
                    cell_texts = [cell.get_text().strip().lower() for cell in cells]
                    
                    # 识别表头
                    if any('cusip' in text for text in cell_texts):
                        header_row = cell_texts
                        data_rows = rows[i+1:]
                        break
                
                if header_row and data_rows:
                    # 找到列索引
                    cusip_idx = next((i for i, text in enumerate(header_row) if 'cusip' in text), None)
                    name_idx = next((i for i, text in enumerate(header_row) if 'name' in text or 'issuer' in text), None)
                    shares_idx = next((i for i, text in enumerate(header_row) if 'shares' in text or 'amount' in text), None)
                    value_idx = next((i for i, text in enumerate(header_row) if 'value' in text), None)
                    
                    for row in data_rows:
                        cells = row.find_all('td')
                        if len(cells) >= max(filter(None, [cusip_idx, name_idx, shares_idx, value_idx]), default=0) + 1:
                            try:
                                cusip = cells[cusip_idx].get_text().strip() if cusip_idx is not None else ""
                                issuer_name = cells[name_idx].get_text().strip() if name_idx is not None else ""
                                shares_text = cells[shares_idx].get_text().strip().replace(',', '') if shares_idx is not None else "0"
                                value_text = cells[value_idx].get_text().strip().replace(',', '').replace('$', '') if value_idx is not None else "0"
                                
                                if cusip and issuer_name:
                                    shares_owned = int(shares_text) if shares_text.isdigit() else 0
                                    market_value = float(value_text) * 1000 if value_text.replace('.', '').isdigit() else 0.0
                                    
                                    if shares_owned > 0 and market_value > 0:
                                        holding = Holding(
                                            cusip=cusip,
                                            issuer_name=issuer_name,
                                            security_class="COM",
                                            shares_owned=shares_owned,
                                            market_value=market_value,
                                            percentage_of_portfolio=0.0
                                        )
                                        
                                        holdings.append(holding)
                                        total_value += market_value
                                        
                            except (ValueError, IndexError):
                                continue
                    
                    if holdings:  # 如果找到了数据，跳出表格循环
                        break
                        
        except Exception as e:
            logger.error(f"HTML表格解析错误: {e}")
            
        return holdings, total_value, period_end_date
    
    def _parse_txt_holdings(self, txt_content: str) -> Tuple[List[Holding], float, Optional[datetime]]:
        """解析文本格式的13F-HR文件"""
        holdings = []
        total_value = 0.0
        period_end_date = None
        
        lines = txt_content.split('\n')
        
        # 查找表格数据
        in_table = False
        for line in lines:
            line = line.strip()
            
            # 查找报告期结束日期
            if not period_end_date and 'period ended' in line.lower():
                date_match = re.search(r'(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})', line)
                if date_match:
                    date_str = date_match.group(1)
                    try:
                        if '/' in date_str:
                            period_end_date = datetime.strptime(date_str, '%m/%d/%Y')
                        else:
                            period_end_date = datetime.strptime(date_str, '%Y-%m-%d')
                    except ValueError:
                        pass
            
            # 识别表格开始
            if 'cusip' in line.lower() and 'name of issuer' in line.lower():
                in_table = True
                continue
            
            # 解析表格行
            if in_table and line:
                # 简单的分隔符解析 - 实际实现需要更复杂的逻辑
                parts = re.split(r'\s{2,}|\t', line)
                if len(parts) >= 4:
                    try:
                        cusip = parts[0].strip()
                        issuer_name = parts[1].strip()
                        
                        # 查找数值字段
                        shares_owned = 0
                        market_value = 0.0
                        
                        for part in parts[2:]:
                            part = part.strip().replace(',', '').replace('$', '')
                            if part.isdigit():
                                if shares_owned == 0:
                                    shares_owned = int(part)
                                elif market_value == 0:
                                    market_value = float(part) * 1000  # 千美元转美元
                        
                        if cusip and issuer_name and shares_owned > 0:
                            holding = Holding(
                                cusip=cusip,
                                issuer_name=issuer_name,
                                security_class="COM",
                                shares_owned=shares_owned,
                                market_value=market_value,
                                percentage_of_portfolio=0.0
                            )
                            
                            holdings.append(holding)
                            total_value += market_value
                            
                    except (ValueError, IndexError):
                        continue
        
        return holdings, total_value, period_end_date
    
    def _quarter_to_date(self, quarter: str) -> datetime:
        """将季度字符串转换为季度末日期"""
        year_str, q_str = quarter.split('Q')
        year = int(year_str)
        q = int(q_str)
        
        if q == 1:
            return datetime(year, 3, 31)
        elif q == 2:
            return datetime(year, 6, 30)
        elif q == 3:
            return datetime(year, 9, 30)
        else:
            return datetime(year, 12, 31)
