"""数据源抽象接口"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class RecipeDataSource(ABC):
    """食谱数据源抽象接口

    定义了获取食谱数据的统一接口，支持不同的数据源实现
    """

    @abstractmethod
    async def fetch_recipes(self) -> List[Dict[str, Any]]:
        """获取食谱数据

        Returns:
            List[Dict[str, Any]]: 原始食谱数据列表

        Raises:
            DataSourceError: 数据获取失败时抛出
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查

        Returns:
            bool: 数据源是否可用
        """
        pass

    @abstractmethod
    def get_source_info(self) -> Dict[str, Any]:
        """获取数据源信息

        Returns:
            Dict[str, Any]: 数据源的基本信息
        """
        pass


class DataSourceError(Exception):
    """数据源异常基类"""

    def __init__(
        self, message: str, source: Optional[str] = None, cause: Optional[Exception] = None
    ):
        self.message = message
        self.source = source
        self.cause = cause
        super().__init__(self.message)


class NetworkError(DataSourceError):
    """网络请求异常"""

    pass


class DataParseError(DataSourceError):
    """数据解析异常"""

    pass


class DataValidationError(DataSourceError):
    """数据验证异常"""

    pass
