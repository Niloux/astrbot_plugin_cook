"""缓存服务实现"""

import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Dict, Optional, Tuple

from astrbot.api import logger


class LRUCache:
    """LRU缓存实现，支持TTL（生存时间）"""

    def __init__(self, max_size: int = 100, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, Tuple[Any, float]] = (
            OrderedDict()
        )  # key -> (value, expire_time)
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                return None

            value, expire_time = self._cache[key]
            current_time = time.time()

            # 检查是否过期
            if current_time > expire_time:
                del self._cache[key]
                return None

            # LRU: 移动到末尾
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        with self._lock:
            current_time = time.time()
            expire_time = current_time + (ttl or self.default_ttl)

            # 如果key已存在，先删除
            if key in self._cache:
                del self._cache[key]

            # 检查缓存大小限制
            while len(self._cache) >= self.max_size:
                # 删除最久未使用的项目
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            # 添加新项目
            self._cache[key] = (value, expire_time)

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()

    def clear_expired(self) -> int:
        """清理过期缓存，返回清理的数量"""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, (_, expire_time) in self._cache.items() if current_time > expire_time
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)

    def size(self) -> int:
        """获取当前缓存大小"""
        with self._lock:
            return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            current_time = time.time()
            expired_count = sum(
                1 for _, (_, expire_time) in self._cache.items() if current_time > expire_time
            )

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "expired_count": expired_count,
                "valid_count": len(self._cache) - expired_count,
            }


class CacheService:
    """缓存服务，管理多个缓存实例"""

    def __init__(self, config=None):
        self.config = config

        # 默认配置
        default_ttl = getattr(config, "cache_ttl", 3600) if config else 3600
        search_cache_size = getattr(config, "search_cache_size", 100) if config else 100
        random_pool_size = getattr(config, "random_pool_size", 50) if config else 50

        # 不同类型的缓存
        self.search_cache = LRUCache(max_size=search_cache_size, default_ttl=default_ttl)
        self.random_cache = LRUCache(max_size=random_pool_size, default_ttl=default_ttl)
        self.category_cache = LRUCache(
            max_size=20, default_ttl=default_ttl * 2
        )  # 分类信息缓存时间更长

        # 统计信息
        self.stats = {
            "search_hits": 0,
            "search_misses": 0,
            "random_hits": 0,
            "random_misses": 0,
            "category_hits": 0,
            "category_misses": 0,
        }

    def get_search_result(self, query: str) -> Optional[Any]:
        """获取搜索结果缓存"""
        cache_key = f"search:{query.lower()}"
        result = self.search_cache.get(cache_key)

        if result is not None:
            self.stats["search_hits"] += 1
        else:
            self.stats["search_misses"] += 1

        return result

    def set_search_result(self, query: str, result: Any, ttl: Optional[int] = None) -> None:
        """设置搜索结果缓存"""
        cache_key = f"search:{query.lower()}"
        self.search_cache.set(cache_key, result, ttl)

    def get_random_recipes(self, category: str, count: int) -> Optional[Any]:
        """获取随机推荐缓存"""
        cache_key = f"random:{category}:{count}"
        result = self.random_cache.get(cache_key)

        if result is not None:
            self.stats["random_hits"] += 1
        else:
            self.stats["random_misses"] += 1

        return result

    def set_random_recipes(
        self, category: str, count: int, result: Any, ttl: Optional[int] = None
    ) -> None:
        """设置随机推荐缓存"""
        cache_key = f"random:{category}:{count}"
        self.random_cache.set(cache_key, result, ttl)

    def get_category_info(self, category: str) -> Optional[Any]:
        """获取分类信息缓存"""
        cache_key = f"category:{category}"
        result = self.category_cache.get(cache_key)

        if result is not None:
            self.stats["category_hits"] += 1
        else:
            self.stats["category_misses"] += 1

        return result

    def set_category_info(self, category: str, result: Any, ttl: Optional[int] = None) -> None:
        """设置分类信息缓存"""
        cache_key = f"category:{category}"
        self.category_cache.set(cache_key, result, ttl)

    def clear_all(self) -> None:
        """清空所有缓存"""
        self.search_cache.clear()
        self.random_cache.clear()
        self.category_cache.clear()

        # 重置统计信息
        for key in self.stats:
            self.stats[key] = 0

        logger.info("已清空所有缓存")

    def cleanup_expired(self) -> Dict[str, int]:
        """清理所有过期缓存"""
        search_cleared = self.search_cache.clear_expired()
        random_cleared = self.random_cache.clear_expired()
        category_cleared = self.category_cache.clear_expired()

        total_cleared = search_cleared + random_cleared + category_cleared

        if total_cleared > 0:
            logger.info(
                f"清理过期缓存: 搜索{search_cleared}个, 随机{random_cleared}个, 分类{category_cleared}个"  # noqa: E501
            )

        return {
            "search_cleared": search_cleared,
            "random_cleared": random_cleared,
            "category_cleared": category_cleared,
            "total_cleared": total_cleared,
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        search_stats = self.search_cache.stats()
        random_stats = self.random_cache.stats()
        category_stats = self.category_cache.stats()

        # 计算命中率
        total_search = self.stats["search_hits"] + self.stats["search_misses"]
        total_random = self.stats["random_hits"] + self.stats["random_misses"]
        total_category = self.stats["category_hits"] + self.stats["category_misses"]

        search_hit_rate = self.stats["search_hits"] / total_search if total_search > 0 else 0
        random_hit_rate = self.stats["random_hits"] / total_random if total_random > 0 else 0
        category_hit_rate = (
            self.stats["category_hits"] / total_category if total_category > 0 else 0
        )

        return {
            "search_cache": {
                **search_stats,
                "hits": self.stats["search_hits"],
                "misses": self.stats["search_misses"],
                "hit_rate": round(search_hit_rate, 3),
            },
            "random_cache": {
                **random_stats,
                "hits": self.stats["random_hits"],
                "misses": self.stats["random_misses"],
                "hit_rate": round(random_hit_rate, 3),
            },
            "category_cache": {
                **category_stats,
                "hits": self.stats["category_hits"],
                "misses": self.stats["category_misses"],
                "hit_rate": round(category_hit_rate, 3),
            },
        }
