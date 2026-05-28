"""远程食谱数据源实现"""

import asyncio
import urllib.parse
from html.parser import HTMLParser
from typing import Any

import httpx

from astrbot.api import logger

from ..config.settings import RecipeConfig
from .source import DataParseError, DataValidationError, NetworkError, RecipeDataSource


class _RecipeCardParser(HTMLParser):
    """Extract recipe cards from HowToCookViewer HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.recipes: list[dict[str, str]] = []
        self._current_href = ""
        self._capture_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "a":
            href = attr_map.get("href", "")
            self._current_href = href if href.startswith("/Recipes/Detail/") else ""
            return

        if tag in {"h5", "h6"} and self._current_href:
            classes = attr_map.get("class", "")
            if "card-title" in classes:
                self._capture_title = True

    def handle_data(self, data: str) -> None:
        if not self._capture_title or not self._current_href:
            return

        title = data.strip()
        if title:
            self.recipes.append({"title": title, "href": self._current_href})

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h5", "h6"}:
            self._capture_title = False
        elif tag == "a":
            self._current_href = ""


class RemoteRecipeSource(RecipeDataSource):
    """远程食谱数据源实现

    从远程API获取食谱数据，支持重试机制和错误恢复
    """

    def __init__(self, config: RecipeConfig):
        self.config = config
        self._client: httpx.AsyncClient | None = None

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

    async def fetch_recipes(self) -> list[dict[str, Any]]:
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

    async def _fetch_with_client(self) -> list[dict[str, Any]]:
        """使用HTTP客户端获取数据"""
        if not self._client:
            self._client = httpx.AsyncClient(
                timeout=self.config.request_timeout, follow_redirects=True
            )

        try:
            logger.info(f"正在从远程API获取数据: {self.config.base_url}")
            response = await self._client.get(self.config.base_url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return await self._fetch_from_html_pages()

            try:
                data = response.json()
            except ValueError as e:
                raise DataParseError(
                    f"JSON解析失败: {str(e)}", source="remote_api", cause=e
                )

            if not isinstance(data, dict):
                raise DataValidationError(
                    "响应数据不是有效的JSON对象", source="remote_api"
                )

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

    async def _fetch_from_html_pages(self) -> list[dict[str, Any]]:
        """Fetch recipes from the current HowToCookViewer server-rendered pages."""
        from ..config.constants import RECIPE_CATEGORIES

        recipes: list[dict[str, Any]] = []

        for category in RECIPE_CATEGORIES:
            page = 1
            while True:
                response = await self._get_html_page(
                    self._build_category_page_url(category, page)
                )

                page_recipes = self._parse_recipe_cards(response.text, category)
                if not page_recipes:
                    break

                recipes.extend(page_recipes)

                has_more = response.headers.get("X-Has-More", "").lower()
                if page > 1 and has_more == "false":
                    break

                page += 1

        logger.info(f"成功从 HTML 页面获取 {len(recipes)} 条原始数据")
        return recipes

    async def _get_html_page(self, url: str) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = await self._client.get(
                    url,
                    headers={"Accept-Language": "zh-CN,zh;q=0.9"},
                )
                response.raise_for_status()
                return response
            except httpx.HTTPError as e:
                last_error = e
                if attempt >= self.config.max_retries:
                    break

                wait_time = self.config.retry_delay * (2**attempt)
                logger.warning(f"获取页面失败，{wait_time}秒后重试: {url}, {str(e)}")
                await asyncio.sleep(wait_time)

        raise NetworkError(
            f"页面请求失败: {url}, {str(last_error)}", source="remote_api"
        )

    def _build_category_page_url(self, category: str, page: int) -> str:
        """Build HowToCookViewer category URL for the first page or load-more pages."""
        base_url = self.config.base_url.rstrip("/")
        if page == 1:
            return f"{base_url}?category={urllib.parse.quote(category)}"
        return f"{self.config.site_url.rstrip('/')}/Recipes/LoadMore?category={urllib.parse.quote(category)}&page={page}"

    def _parse_recipe_cards(self, html: str, category: str) -> list[dict[str, str]]:
        parser = _RecipeCardParser()
        try:
            parser.feed(html)
        except Exception as e:
            raise DataParseError(
                f"HTML解析失败: {str(e)}", source="remote_api", cause=e
            )

        return [
            {
                "name": recipe["title"],
                "category": category,
                "url": urllib.parse.urljoin(self.config.site_url, recipe["href"]),
            }
            for recipe in parser.recipes
        ]

    async def health_check(self) -> bool:
        """检查远程API健康状态"""
        try:
            if not self._client:
                self._client = httpx.AsyncClient(
                    timeout=min(self.config.request_timeout, 5.0),  # 健康检查用较短超时
                    follow_redirects=True,
                )

            response = await self._client.get(self.config.base_url)
            return response.status_code == 200

        except Exception as e:
            logger.warning(f"健康检查失败: {str(e)}")
            return False

    def get_source_info(self) -> dict[str, Any]:
        """获取数据源信息"""
        return {
            "type": "remote",
            "base_url": self.config.base_url,
            "site_url": self.config.site_url,
            "timeout": self.config.request_timeout,
            "max_retries": self.config.max_retries,
            "retry_delay": self.config.retry_delay,
        }

    def process_raw_data(self, raw_data: list[dict[str, Any]]) -> list[dict[str, str]]:
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
            if {"name", "category", "url"}.issubset(item):
                category_en = item.get("category", "")
                if category_en not in RECIPE_CATEGORIES:
                    continue

                category_zh = RECIPE_CATEGORIES[category_en]
                dish_name = item.get("name", "").strip()
                if not dish_name:
                    continue

                dish_key = f"{dish_name}_{category_zh}"
                if dish_key in seen_dishes:
                    continue
                seen_dishes.add(dish_key)

                processed_recipes.append(
                    {
                        "name": dish_name,
                        "category": category_en,
                        "category_zh": category_zh,
                        "url": item.get("url", ""),
                    }
                )
                continue

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

            processed_recipes.append(
                {
                    "name": dish_name,
                    "category": category_en,
                    "category_zh": category_zh,
                    "url": location,
                }
            )

        logger.info(
            f"原始数据 {len(raw_data)} 条，处理后有效数据 {len(processed_recipes)} 条"
        )
        return processed_recipes
