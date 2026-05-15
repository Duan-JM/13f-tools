"""
配置管理模块

处理SEC 13F分析工具的配置文件
"""

import configparser
import os
from pathlib import Path
from typing import Optional


class Config:
    """配置管理器"""

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_file: 配置文件路径，如果不提供会自动查找
        """
        self.config = configparser.ConfigParser()
        self.config_file: Optional[str]

        # 查找配置文件
        if config_file and os.path.exists(config_file):
            self.config_file = config_file
        else:
            self.config_file = self._find_config_file()

        # 加载配置
        self._load_config()

    def _find_config_file(self) -> Optional[str]:
        """自动查找配置文件"""
        possible_paths = [
            "config.ini",
            "config.ini.example",
            "../config.ini",
            str(Path.home() / ".sec13f_analyzer" / "config.ini"),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return None

    def _load_config(self):
        """加载配置文件"""
        # 先设置默认值
        self._set_defaults()

        # 如果有配置文件，则加载它
        if self.config_file and os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file)
            except Exception as e:
                # 如果配置文件有问题，记录警告但继续使用默认值
                print(f"警告: 配置文件读取失败 {self.config_file}: {e}")
                print("将使用默认配置")

    def _set_defaults(self):
        """设置默认配置值"""
        defaults = {
            "MAIN": {
                "company_name": "ValueAnalyze Research",
                "email": "research@valueanalyze.com",
                "request_delay": "0.2",
                "max_retries": "3",
                "timeout": "30",
            },
            "API": {
                "base_url": "https://www.sec.gov",
                "edgar_url": "https://www.sec.gov/edgar",
                "search_url": "https://www.sec.gov/cgi-bin/browse-edgar",
            },
            "LOGGING": {"level": "INFO"},
            "CACHE": {"enable_cache": "true", "cache_ttl": "24"},
            "EXPORT": {"default_format": "excel", "output_directory": "./output"},
            "VISUALIZATION": {
                "default_chart_type": "both",
                "chart_style": "seaborn",
                "show_plots": "true",
                "image_format": "png",
                "image_dpi": "300",
            },
        }

        for section, options in defaults.items():
            if not self.config.has_section(section):
                self.config.add_section(section)

            for key, value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, value)

    def get_user_agent(self) -> str:
        """获取User-Agent字符串"""
        custom_ua = self.config.get("MAIN", "user_agent", fallback=None)
        if custom_ua:
            return custom_ua

        company = self.config.get("MAIN", "company_name")
        email = self.config.get("MAIN", "email")

        return f"{company} SEC13F-Analyzer/1.0 ({email})"

    def get_company_name(self) -> str:
        """获取公司名称"""
        return self.config.get("MAIN", "company_name")

    def get_email(self) -> str:
        """获取联系邮箱"""
        return self.config.get("MAIN", "email")

    def get_request_delay(self) -> float:
        """获取请求延迟时间"""
        return self.config.getfloat("MAIN", "request_delay")

    def get_max_retries(self) -> int:
        """获取最大重试次数"""
        return self.config.getint("MAIN", "max_retries")

    def get_timeout(self) -> int:
        """获取请求超时时间"""
        return self.config.getint("MAIN", "timeout")

    def get_base_url(self) -> str:
        """获取SEC基础URL"""
        return self.config.get("API", "base_url")

    def get_edgar_url(self) -> str:
        """获取EDGAR URL"""
        return self.config.get("API", "edgar_url")

    def get_search_url(self) -> str:
        """获取搜索URL"""
        return self.config.get("API", "search_url")

    def save_config(self, config_file: Optional[str] = None):
        """保存配置到文件"""
        file_path = config_file or self.config_file or "config.ini"

        # 确保目录存在
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)

        with open(file_path, "w") as f:
            self.config.write(f)

    def update_config(self, section: str, key: str, value: str):
        """更新配置项"""
        if not self.config.has_section(section):
            self.config.add_section(section)

        self.config.set(section, key, value)

    def validate_config(self) -> list:
        """验证配置，返回错误列表"""
        errors = []

        # 检查必填项
        company_name = self.get_company_name().strip()
        email = self.get_email().strip()

        if not company_name:
            errors.append("公司名称不能为空")

        if not email or "@" not in email:
            errors.append("邮箱格式不正确")

        # 检查延迟时间
        delay = self.get_request_delay()
        if delay < 0.1:
            errors.append("请求延迟不能少于0.1秒（SEC要求）")

        # 检查重试次数
        retries = self.get_max_retries()
        if retries < 1 or retries > 10:
            errors.append("重试次数应该在1-10之间")

        return errors


# 全局配置实例
_config = None


def get_config(config_file: Optional[str] = None) -> Config:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = Config(config_file)
    return _config
