"""远程食谱数据源实现"""

import asyncio
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

from astrbot.api import logger

from ..config.settings import RecipeConfig
from .source import DataParseError, DataValidationError, NetworkError, RecipeDataSource


class RemoteRecipeSource(RecipeDataSource):
    """远程食谱数据源实现

    从远程API获取食谱数据，支持重试机制和错误恢复
    """

    def __init__(self, config: RecipeConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._client = httpx.AsyncClient(
            timeout=self.config.request_timeout, follow_redirects=True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_recipes(self) -> List[Dict[str, Any]]:
        """获取食谱数据，带重试机制"""
        last_error = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return await self._fetch_with_client()
            except NetworkError as e:
                last_error = e
                if attempt < self.config.max_retries:
                    wait_time = self.config.retry_delay * (2**attempt)  # 指数退避
                    logger.warning(
                        f"第 {attempt + 1} 次获取数据失败，{wait_time}秒后重试: {e.message}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"获取数据失败，已达到最大重试次数: {e.message}")
            except (DataParseError, DataValidationError) as e:
                # 数据解析错误不重试
                logger.error(f"数据处理失败: {e.message}")
                raise e

        # 所有重试都失败了
        raise last_error or NetworkError("未知网络错误", source="remote_api")

    async def _fetch_with_client(self) -> List[Dict[str, Any]]:
        """使用HTTP客户端获取数据"""
        if not self._client:
            self._client = httpx.AsyncClient(
                timeout=self.config.request_timeout, follow_redirects=True
            )

        try:
            logger.info(f"正在从远程API获取数据: {self.config.base_url}")
            response = await self._client.get(self.config.base_url)
            response.raise_for_status()

            # 解析JSON响应
            try:
                data = response.json()
            except ValueError as e:
                raise DataParseError(f"JSON解析失败: {str(e)}", source="remote_api", cause=e)

            # 验证响应结构
            if not isinstance(data, dict):
                raise DataValidationError("响应数据不是有效的JSON对象", source="remote_api")

            docs = data.get("docs", [])
            if not isinstance(docs, list):
                raise DataValidationError("docs字段不是有效的列表", source="remote_api")

            logger.info(f"成功获取 {len(docs)} 条原始数据")
            return docs

        except httpx.HTTPStatusError as e:
            raise NetworkError(
                f"HTTP请求失败: {e.response.status_code}", source="remote_api", cause=e
            )
        except httpx.RequestError as e:
            raise NetworkError(f"网络请求异常: {str(e)}", source="remote_api", cause=e)
        except httpx.TimeoutException as e:
            raise NetworkError(f"请求超时: {str(e)}", source="remote_api", cause=e)

    async def health_check(self) -> bool:
        """检查远程API健康状态"""
        try:
            if not self._client:
                self._client = httpx.AsyncClient(
                    timeout=min(self.config.request_timeout, 5.0),  # 健康检查用较短超时
                    follow_redirects=True,
                )

            response = await self._client.head(self.config.base_url)
            return response.status_code == 200

        except Exception as e:
            logger.warning(f"健康检查失败: {str(e)}")
            return False

    def get_source_info(self) -> Dict[str, Any]:
        """获取数据源信息"""
        return {
            "type": "remote",
            "base_url": self.config.base_url,
            "site_url": self.config.site_url,
            "timeout": self.config.request_timeout,
            "max_retries": self.config.max_retries,
            "retry_delay": self.config.retry_delay,
        }

    def process_raw_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """处理原始数据，提取有效的食谱信息

        Args:
            raw_data: 从API获取的原始数据

        Returns:
            List[Dict[str, str]]: 处理后的食谱数据，包含 name, category, url 字段
        """
        from ..config.constants import RECIPE_CATEGORIES

        processed_recipes = []
        seen_dishes = set()  # 去重

        for item in raw_data:
            location = item.get("location", "")
            if not location or "dishes/" not in location or "#" in location:
                continue

            # 解析URL路径
            parts = location.split("dishes/")
            if len(parts) < 2:
                continue

            path_parts = parts[1].strip("/").split("/")
            if len(path_parts) < 2:
                continue

            category_en = path_parts[0]
            dish_name_encoded = path_parts[1]

            # URL解码菜品名称
            try:
                dish_name = urllib.parse.unquote(dish_name_encoded)
            except Exception:
                continue

            # 验证分类有效性
            if category_en not in RECIPE_CATEGORIES:
                continue

            category_zh = RECIPE_CATEGORIES[category_en]

            # 去重处理
            dish_key = f"{dish_name}_{category_zh}"
            if dish_key in seen_dishes:
                continue
            seen_dishes.add(dish_key)

            processed_recipes.append({
                "name": dish_name,
                "category": category_en,
                "category_zh": category_zh,
                "url": location,
            })

        logger.info(f"原始数据 {len(raw_data)} 条，处理后有效数据 {len(processed_recipes)} 条")
        return processed_recipes
