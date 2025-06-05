"""搜索服务实现"""

import random
from collections import defaultdict
from typing import Dict, List, Optional, Set

from astrbot.api import logger

from ..config.settings import RecipeConfig
from ..models.recipe import Recipe, SearchResult


class RecipeSearchService:
    """食谱搜索服务

    提供高性能的食谱搜索功能，包含：
    - 反向索引优化的O(1)查找
    - 关键词搜索
    - 分类筛选
    - 随机推荐
    """

    def __init__(self, recipes: Dict[str, Recipe], config: RecipeConfig) -> None:
        self.config = config
        self._recipes: Dict[str, Recipe] = recipes  # name -> Recipe

        # 索引结构
        self._name_index: Dict[str, Recipe] = {}  # name -> Recipe (精确匹配)
        self._category_index: Dict[str, List[Recipe]] = defaultdict(
            list
        )  # category_zh -> [Recipe]
        self._keyword_index: Dict[str, Set[str]] = defaultdict(set)  # keyword -> {recipe_names}

        # 随机推荐池（预计算）
        self._random_pool: Dict[str, List[Recipe]] = {}  # category -> [Recipe]
        self._all_recipes_list: List[Recipe] = []

        # 构建索引
        self._build_indexes()

        logger.info(
            f"搜索服务初始化完成: {len(self._recipes)} 个食谱, {len(self._keyword_index)} 个关键词"
        )

    def _build_indexes(self) -> None:
        """构建所有索引结构"""
        if not self._recipes:
            logger.warning("没有食谱数据，跳过索引构建")
            return

        # 清空现有索引
        self._name_index.clear()
        self._category_index.clear()
        self._keyword_index.clear()
        self._random_pool.clear()
        self._all_recipes_list.clear()

        # 构建基础索引
        for recipe in self._recipes.values():
            # 名称索引 (精确匹配)
            self._name_index[recipe.name] = recipe
            self._name_index[recipe.name.lower()] = recipe  # 支持大小写不敏感

            # 分类索引
            self._category_index[recipe.category_zh].append(recipe)

            # 关键词索引 (支持部分匹配)
            self._build_keyword_index(recipe)

            # 添加到总列表
            self._all_recipes_list.append(recipe)

        # 构建随机推荐池
        self._build_random_pools()

        logger.info(
            f"索引构建完成: 名称索引{len(self._name_index)}, 分类{len(self._category_index)}, 关键词{len(self._keyword_index)}"
        )

    def _build_keyword_index(self, recipe: Recipe) -> None:
        """为单个食谱构建关键词索引"""
        # 提取关键词：菜名的每个字符和词组
        name = recipe.name.lower()

        # 单字符索引
        for char in name:
            if char.strip():  # 跳过空白字符
                self._keyword_index[char].add(recipe.name)

        # 2-3字符词组索引（对中文搜索很重要）
        for i in range(len(name)):
            for length in [2, 3]:
                if i + length <= len(name):
                    keyword = name[i : i + length]
                    if keyword.strip():
                        self._keyword_index[keyword].add(recipe.name)

    def _build_random_pools(self) -> None:
        """构建随机推荐池"""
        # 按分类构建随机池
        for category_zh, recipes in self._category_index.items():
            if recipes:
                # 预打乱顺序
                pool = recipes.copy()
                random.shuffle(pool)
                self._random_pool[category_zh] = pool

        # 全局随机池
        if self._all_recipes_list:
            global_pool = self._all_recipes_list.copy()
            random.shuffle(global_pool)
            self._random_pool[""] = global_pool  # 空字符串表示全部分类

    def update_recipes(self, recipes: Dict[str, Recipe]) -> None:
        """更新食谱数据并重建索引"""
        self._recipes = recipes
        self._build_indexes()
        logger.info(f"食谱数据已更新: {len(recipes)} 个食谱")

    def find_by_name(self, name: str) -> Optional[Recipe]:
        """根据名称精确查找食谱 - O(1)复杂度"""
        if not name.strip():
            return None

        # 先尝试精确匹配
        recipe = self._name_index.get(name)
        if recipe:
            return recipe

        # 再尝试大小写不敏感匹配
        return self._name_index.get(name.lower())

    def search_by_keyword(self, keyword: str, max_results: Optional[int] = None) -> SearchResult:
        """根据关键词搜索食谱"""
        if not keyword.strip():
            return SearchResult(recipes=[], total_count=0, has_more=False, query=keyword)

        max_results = max_results or self.config.max_search_results
        keyword_lower = keyword.lower()

        # 收集匹配的食谱名称
        matched_names: Set[str] = set()

        # 精确关键词匹配
        if keyword_lower in self._keyword_index:
            matched_names.update(self._keyword_index[keyword_lower])

        # 部分匹配：查找包含关键词的所有关键词索引
        for indexed_keyword, recipe_names in self._keyword_index.items():
            if keyword_lower in indexed_keyword:
                matched_names.update(recipe_names)

        # 转换为Recipe对象并去重
        matched_recipes = []
        seen_names = set()

        for name in matched_names:
            if name not in seen_names and name in self._recipes:
                matched_recipes.append(self._recipes[name])
                seen_names.add(name)

        # 按相关性排序（简单的相关性：名称中关键词出现的位置）
        matched_recipes.sort(key=lambda r: self._calculate_relevance(r.name, keyword_lower))

        # 分页处理
        total_count = len(matched_recipes)
        has_more = total_count > max_results
        shown_recipes = matched_recipes[:max_results]

        return SearchResult(
            recipes=shown_recipes, total_count=total_count, has_more=has_more, query=keyword
        )

    def _calculate_relevance(self, recipe_name: str, keyword: str) -> int:
        """计算搜索相关性分数（越小越相关）"""
        name_lower = recipe_name.lower()

        # 精确匹配得分最高
        if name_lower == keyword:
            return 0

        # 开头匹配得分较高
        if name_lower.startswith(keyword):
            return 1

        # 包含匹配
        if keyword in name_lower:
            return 2 + name_lower.index(keyword)  # 位置越靠前得分越高

        # 其他情况
        return 1000

    def get_recipes_by_category(
        self, category_zh: str, max_results: Optional[int] = None
    ) -> List[Recipe]:
        """获取指定分类的食谱列表"""
        if category_zh not in self._category_index:
            return []

        recipes = self._category_index[category_zh]
        if max_results and len(recipes) > max_results:
            return recipes[:max_results]

        return recipes

    def get_random_recipes(self, count: int, category_zh: Optional[str] = None) -> List[Recipe]:
        """获取随机食谱推荐 - 高性能实现"""
        # 限制推荐数量
        count = max(self.config.min_random_count, min(count, self.config.max_random_count))

        # 选择对应的随机池
        pool_key = category_zh if category_zh and category_zh in self._random_pool else ""

        if pool_key not in self._random_pool:
            return []

        pool = self._random_pool[pool_key]
        if not pool:
            return []

        # 如果请求数量大于池大小，返回整个池
        if count >= len(pool):
            return pool.copy()

        # 随机采样
        return random.sample(pool, count)

    def get_random_recipe_by_category(self, category_zh: str) -> Optional[Recipe]:
        """获取指定分类的随机食谱"""
        recipes = self.get_random_recipes(1, category_zh)
        return recipes[0] if recipes else None

    def get_categories_info(self) -> Dict[str, int]:
        """获取所有分类及其食谱数量"""
        return {
            category_zh: len(recipes)
            for category_zh, recipes in self._category_index.items()
            if recipes  # 只返回有食谱的分类
        }

    def get_total_count(self) -> int:
        """获取总食谱数量"""
        return len(self._recipes)

    def validate_category(self, category_zh: str) -> bool:
        """验证分类是否存在且有食谱"""
        return category_zh in self._category_index and len(self._category_index[category_zh]) > 0

    def get_search_suggestions(self, partial_keyword: str, max_suggestions: int = 5) -> List[str]:
        """获取搜索建议（自动补全）"""
        if not partial_keyword.strip():
            return []

        partial_lower = partial_keyword.lower()
        suggestions = set()

        # 从关键词索引中查找匹配的关键词
        for keyword in self._keyword_index.keys():
            if keyword.startswith(partial_lower) and len(keyword) > len(partial_lower):
                suggestions.add(keyword)

        # 从食谱名称中查找匹配的名称
        for recipe_name in self._recipes.keys():
            if recipe_name.lower().startswith(partial_lower):
                suggestions.add(recipe_name)

        # 转换为列表并排序
        suggestion_list = sorted(list(suggestions))
        return suggestion_list[:max_suggestions]

    def get_stats(self) -> Dict[str, any]:
        """获取搜索服务统计信息"""
        return {
            "total_recipes": len(self._recipes),
            "total_categories": len(self._category_index),
            "total_keywords": len(self._keyword_index),
            "categories_info": self.get_categories_info(),
            "index_sizes": {
                "name_index": len(self._name_index),
                "category_index": sum(len(recipes) for recipes in self._category_index.values()),
                "keyword_index": sum(len(names) for names in self._keyword_index.values()),
                "random_pools": {k: len(v) for k, v in self._random_pool.items()},
            },
        }
