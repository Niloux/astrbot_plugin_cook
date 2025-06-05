"""食谱数据模型"""

from dataclasses import dataclass
from typing import Any, Dict, List

# 字符串池化 - 减少重复字符串的内存占用
_string_pool: Dict[str, str] = {}
_site_url_cache = "https://cook.aiursoft.cn/"


def _intern_string(s: str) -> str:
    """字符串池化，减少内存占用"""
    if s not in _string_pool:
        _string_pool[s] = s
    return _string_pool[s]


@dataclass(frozen=True, slots=True)
class Recipe:
    """食谱数据模型

    使用frozen=True确保不可变性，slots=True优化内存使用
    """

    name: str
    category: str
    category_zh: str
    url: str

    def __post_init__(self) -> None:
        """数据验证"""
        if not self.name.strip():
            raise ValueError("Recipe name cannot be empty")
        if not self.category.strip():
            raise ValueError("Recipe category cannot be empty")
        if not self.category_zh.strip():
            raise ValueError("Recipe category_zh cannot be empty")
        if not self.url.strip():
            raise ValueError("Recipe url cannot be empty")

        # 字符串池化优化内存
        object.__setattr__(self, "name", _intern_string(self.name))
        object.__setattr__(self, "category", _intern_string(self.category))
        object.__setattr__(self, "category_zh", _intern_string(self.category_zh))
        object.__setattr__(self, "url", _intern_string(self.url))

    @property
    def full_url(self) -> str:
        """获取完整URL - 缓存计算结果"""
        if self.url.startswith(_site_url_cache):
            return self.url
        return _site_url_cache + self.url.lstrip("/")

    def to_dict(self) -> Dict[str, str]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "category": self.category,
            "category_zh": self.category_zh,
            "url": self.url,
            "full_url": self.full_url,
        }

    def __hash__(self) -> int:
        """优化哈希计算"""
        return hash((self.name, self.category_zh))


@dataclass(frozen=True, slots=True)
class SearchResult:
    """搜索结果数据模型"""

    recipes: List[Recipe]
    total_count: int
    has_more: bool
    query: str = ""

    def __post_init__(self) -> None:
        """数据验证"""
        if self.total_count < 0:
            raise ValueError("total_count cannot be negative")
        if len(self.recipes) > self.total_count:
            raise ValueError("recipes count cannot exceed total_count")

        # 字符串池化
        object.__setattr__(self, "query", _intern_string(self.query))

    @property
    def is_empty(self) -> bool:
        """是否为空结果"""
        return len(self.recipes) == 0

    @property
    def shown_count(self) -> int:
        """显示的结果数量"""
        return len(self.recipes)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "recipes": [recipe.to_dict() for recipe in self.recipes],
            "total_count": self.total_count,
            "shown_count": self.shown_count,
            "has_more": self.has_more,
            "query": self.query,
            "is_empty": self.is_empty,
        }


@dataclass(frozen=True, slots=True)
class CategoryInfo:
    """分类信息数据模型"""

    name_zh: str
    name_en: str
    count: int

    def __post_init__(self) -> None:
        """数据验证"""
        if not self.name_zh.strip():
            raise ValueError("Category name_zh cannot be empty")
        if not self.name_en.strip():
            raise ValueError("Category name_en cannot be empty")
        if self.count < 0:
            raise ValueError("Category count cannot be negative")

        # 字符串池化
        object.__setattr__(self, "name_zh", _intern_string(self.name_zh))
        object.__setattr__(self, "name_en", _intern_string(self.name_en))

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {"name_zh": self.name_zh, "name_en": self.name_en, "count": self.count}


def clear_string_pool() -> int:
    """清理字符串池，释放内存"""
    count = len(_string_pool)
    _string_pool.clear()
    return count


def get_string_pool_stats() -> Dict[str, Any]:
    """获取字符串池统计信息"""
    return {
        "pool_size": len(_string_pool),
        "memory_saved_estimate": len(_string_pool) * 50,  # 粗略估算节省的内存
    }
