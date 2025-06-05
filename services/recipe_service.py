"""核心食谱业务服务"""

import asyncio
from typing import Any, Dict, List, Optional

from astrbot.api import logger

from ..config.settings import RecipeConfig
from ..data.source import DataSourceError, RecipeDataSource
from ..models.recipe import Recipe
from ..services.cache_service import CacheService
from ..services.search_service import RecipeSearchService


class RecipeService:
    """核心食谱业务服务

    整合数据获取、搜索、缓存等功能，提供统一的业务接口
    """

    def __init__(self, data_source: RecipeDataSource, config: RecipeConfig):
        self.config = config
        self._data_source = data_source

        # 核心数据
        self._recipes: Dict[str, Recipe] = {}  # name -> Recipe
        self._is_initialized = False

        # 服务组件
        self._search_service: Optional[RecipeSearchService] = None
        self._cache_service: Optional[CacheService] = None

        # 统计信息
        self._stats = {
            "requests_total": 0,
            "search_requests": 0,
            "random_requests": 0,
            "category_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    async def initialize(self) -> None:
        """初始化服务：获取数据、构建索引、启动缓存"""
        if self._is_initialized:
            logger.warning("服务已经初始化过，跳过重复初始化")
            return

        try:
            logger.info("开始初始化食谱服务...")

            # 1. 检查数据源健康状态
            is_healthy = await self._data_source.health_check()
            if not is_healthy:
                logger.warning("数据源健康检查失败，但继续尝试获取数据")

            # 2. 获取并处理数据
            await self._load_recipe_data()

            # 3. 初始化搜索服务
            self._search_service = RecipeSearchService(self._recipes, self.config)

            # 4. 初始化缓存服务
            self._cache_service = CacheService(self.config)

            # 5. 启动后台清理任务
            asyncio.create_task(self._background_cleanup())

            self._is_initialized = True
            logger.info(f"食谱服务初始化完成: {len(self._recipes)} 个食谱")

        except Exception as e:
            logger.error(f"食谱服务初始化失败: {str(e)}")
            raise e

    async def _load_recipe_data(self) -> None:
        """加载和处理食谱数据"""
        try:
            # 使用数据源获取原始数据
            async with self._data_source as source:
                raw_data = await source.fetch_recipes()

                # 处理原始数据
                if hasattr(source, "process_raw_data"):
                    processed_data = source.process_raw_data(raw_data)
                else:
                    processed_data = self._default_process_data(raw_data)

                # 转换为Recipe对象
                self._recipes = self._convert_to_recipes(processed_data)

                logger.info(f"成功加载 {len(self._recipes)} 个食谱")

        except DataSourceError as e:
            logger.error(f"数据源错误: {e.message}")
            raise e
        except Exception as e:
            logger.error(f"数据加载失败: {str(e)}")
            raise DataSourceError(f"数据加载过程中发生未知错误: {str(e)}", cause=e)

    def _default_process_data(self, raw_data: List[Dict]) -> List[Dict[str, str]]:
        """默认数据处理逻辑（如果数据源没有提供处理方法）"""
        import urllib.parse

        from ..config.constants import RECIPE_CATEGORIES

        processed_recipes = []
        seen_dishes = set()

        for item in raw_data:
            location = item.get("location", "")
            if not location or "dishes/" not in location or "#" in location:
                continue

            parts = location.split("dishes/")
            if len(parts) < 2:
                continue

            path_parts = parts[1].strip("/").split("/")
            if len(path_parts) < 2:
                continue

            category_en = path_parts[0]
            dish_name_encoded = path_parts[1]

            try:
                dish_name = urllib.parse.unquote(dish_name_encoded)
            except Exception:
                continue

            if category_en not in RECIPE_CATEGORIES:
                continue

            category_zh = RECIPE_CATEGORIES[category_en]
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

        return processed_recipes

    def _convert_to_recipes(self, processed_data: List[Dict[str, str]]) -> Dict[str, Recipe]:
        """将处理后的数据转换为Recipe对象"""
        recipes = {}

        for data in processed_data:
            try:
                recipe = Recipe(
                    name=data["name"],
                    category=data["category"],
                    category_zh=data["category_zh"],
                    url=data["url"],
                )
                recipes[recipe.name] = recipe

            except (KeyError, ValueError) as e:
                logger.warning(f"跳过无效食谱数据: {data}, 错误: {str(e)}")
                continue

        return recipes

    async def _background_cleanup(self) -> None:
        """后台清理任务"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟执行一次

                if self._cache_service:
                    cleared = self._cache_service.cleanup_expired()
                    if cleared["total_cleared"] > 0:
                        logger.debug(f"清理过期缓存: {cleared['total_cleared']} 个")

            except Exception as e:
                logger.error(f"后台清理任务出错: {str(e)}")

    def _ensure_initialized(self) -> None:
        """确保服务已初始化"""
        if not self._is_initialized:
            raise RuntimeError("服务未初始化，请先调用 initialize() 方法")

    async def search_recipes(self, keyword: str) -> str:
        """搜索食谱"""
        self._ensure_initialized()
        self._stats["requests_total"] += 1
        self._stats["search_requests"] += 1

        # 尝试从缓存获取
        cached_result = self._cache_service.get_search_result(keyword)
        if cached_result:
            self._stats["cache_hits"] += 1
            return cached_result

        self._stats["cache_misses"] += 1

        # 执行搜索
        search_result = self._search_service.search_by_keyword(keyword)

        # 格式化结果
        from ..utils.formatters import ResponseFormatter

        formatter = ResponseFormatter(self.config)
        formatted_result = formatter.format_search_result(search_result)

        # 缓存结果
        self._cache_service.set_search_result(keyword, formatted_result)

        return formatted_result

    async def get_random_recipe(self, category: Optional[str] = None) -> str:
        """获取随机推荐的食谱"""
        self._ensure_initialized()
        self._stats["requests_total"] += 1
        self._stats["random_requests"] += 1

        # 验证分类
        if category and not self._search_service.validate_category(category):
            from ..utils.formatters import ResponseFormatter

            formatter = ResponseFormatter(self.config)
            categories_info = self._search_service.get_categories_info()
            return formatter.format_invalid_category(category, list(categories_info.keys()))

        # 尝试从缓存获取
        cache_key = category or "all"
        cached_result = self._cache_service.get_random_recipes(cache_key, 1)
        if cached_result:
            self._stats["cache_hits"] += 1
            return cached_result

        self._stats["cache_misses"] += 1

        # 获取随机食谱
        if category:
            recipe = self._search_service.get_random_recipe_by_category(category)
            if recipe:
                result = f"🍽️ 推荐的{category}: {recipe.name}"
            else:
                result = f"😔 分类 '{category}' 下暂时没有菜品。"
        else:
            recipes = self._search_service.get_random_recipes(1)
            if recipes:
                recipe = recipes[0]
                result = f"🍽️ 推荐菜品: {recipe.name} ({recipe.category_zh})"
            else:
                result = "😔 暂无可推荐的菜品"

        # 缓存结果
        self._cache_service.set_random_recipes(
            cache_key, 1, result, ttl=60
        )  # 随机推荐缓存时间较短

        return result

    async def get_recipe_url(self, dish_name: str) -> str:
        """获取菜品的制作方法URL"""
        self._ensure_initialized()
        self._stats["requests_total"] += 1

        recipe = self._search_service.find_by_name(dish_name)
        if recipe:
            return f"📖 {recipe.name} 的制作方式：\n{recipe.full_url}"
        else:
            return f"❌ 未找到菜品: {dish_name}\n💡 建议使用 /菜谱搜索 查看可用菜品"

    def get_categories_info(self) -> str:
        """获取分类信息"""
        self._ensure_initialized()
        self._stats["requests_total"] += 1
        self._stats["category_requests"] += 1

        # 尝试从缓存获取
        cached_result = self._cache_service.get_category_info("all")
        if cached_result:
            self._stats["cache_hits"] += 1
            return cached_result

        self._stats["cache_misses"] += 1

        # 生成分类信息
        categories_info = self._search_service.get_categories_info()
        total_count = self._search_service.get_total_count()

        from ..utils.formatters import ResponseFormatter

        formatter = ResponseFormatter(self.config)
        result = formatter.format_categories_info(categories_info, total_count)

        # 缓存结果
        self._cache_service.set_category_info("all", result)

        return result

    async def get_random_recipes_batch(self, count: int) -> str:
        """获取多个随机推荐"""
        self._ensure_initialized()
        self._stats["requests_total"] += 1
        self._stats["random_requests"] += 1

        # 限制数量范围
        count = max(self.config.min_random_count, min(count, self.config.max_random_count))

        # 尝试从缓存获取
        cached_result = self._cache_service.get_random_recipes("all", count)
        if cached_result:
            self._stats["cache_hits"] += 1
            return cached_result

        self._stats["cache_misses"] += 1

        # 获取随机食谱
        recipes = self._search_service.get_random_recipes(count)

        if not recipes:
            result = "😔 暂无可推荐的菜品"
        else:
            from ..utils.formatters import ResponseFormatter

            formatter = ResponseFormatter(self.config)
            result = formatter.format_random_recipes(recipes, count)

        # 缓存结果
        self._cache_service.set_random_recipes("all", count, result, ttl=60)

        return result

    async def reload_data(self) -> str:
        """重新加载数据"""
        try:
            logger.info("开始重新加载食谱数据...")

            # 清空缓存
            if self._cache_service:
                self._cache_service.clear_all()

            # 重新加载数据
            await self._load_recipe_data()

            # 更新搜索服务
            if self._search_service:
                self._search_service.update_recipes(self._recipes)

            logger.info(f"数据重新加载完成: {len(self._recipes)} 个食谱")
            return f"✅ 数据重新加载完成，共 {len(self._recipes)} 个食谱"

        except Exception as e:
            logger.error(f"数据重新加载失败: {str(e)}")
            return f"❌ 数据重新加载失败: {str(e)}"

    def get_service_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        stats = {
            "initialized": self._is_initialized,
            "total_recipes": len(self._recipes),
            "requests": self._stats.copy(),
        }

        if self._search_service:
            stats["search_service"] = self._search_service.get_stats()

        if self._cache_service:
            stats["cache_service"] = self._cache_service.get_cache_stats()

        return stats

    async def cleanup(self) -> None:
        """清理服务资源"""
        logger.info("开始清理食谱服务资源...")

        if self._cache_service:
            self._cache_service.clear_all()

        self._recipes.clear()
        self._is_initialized = False

        logger.info("食谱服务资源清理完成")
