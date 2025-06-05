"""配置管理"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict

from .constants import API_CONSTANTS, CACHE_CONSTANTS, DEFAULT_LIMITS


@dataclass
class RecipeConfig:
    """食谱插件配置类"""

    # API配置
    base_url: str = field(
        default_factory=lambda: os.getenv("RECIPE_BASE_URL", API_CONSTANTS["BASE_URL"])
    )
    site_url: str = field(
        default_factory=lambda: os.getenv("RECIPE_SITE_URL", API_CONSTANTS["SITE_URL"])
    )
    request_timeout: float = field(
        default_factory=lambda: float(
            os.getenv("RECIPE_TIMEOUT", str(API_CONSTANTS["REQUEST_TIMEOUT"]))
        )
    )
    max_retries: int = field(
        default_factory=lambda: int(
            os.getenv("RECIPE_MAX_RETRIES", str(API_CONSTANTS["MAX_RETRIES"]))
        )
    )
    retry_delay: float = field(
        default_factory=lambda: float(
            os.getenv("RECIPE_RETRY_DELAY", str(API_CONSTANTS["RETRY_DELAY"]))
        )
    )

    # 缓存配置
    cache_ttl: int = field(
        default_factory=lambda: int(
            os.getenv("RECIPE_CACHE_TTL", str(CACHE_CONSTANTS["DEFAULT_TTL"]))
        )
    )
    search_cache_size: int = field(
        default_factory=lambda: int(
            os.getenv("RECIPE_SEARCH_CACHE_SIZE", str(CACHE_CONSTANTS["SEARCH_CACHE_SIZE"]))
        )
    )
    random_pool_size: int = field(
        default_factory=lambda: int(
            os.getenv("RECIPE_RANDOM_POOL_SIZE", str(CACHE_CONSTANTS["RANDOM_POOL_SIZE"]))
        )
    )

    # 限制配置
    max_search_results: int = field(
        default_factory=lambda: int(
            os.getenv("RECIPE_MAX_SEARCH_RESULTS", str(DEFAULT_LIMITS["MAX_SEARCH_RESULTS"]))
        )
    )
    max_random_results: int = field(
        default_factory=lambda: int(
            os.getenv("RECIPE_MAX_RANDOM_RESULTS", str(DEFAULT_LIMITS["MAX_RANDOM_RESULTS"]))
        )
    )
    max_category_display: int = field(
        default_factory=lambda: int(
            os.getenv("RECIPE_MAX_CATEGORY_DISPLAY", str(DEFAULT_LIMITS["MAX_CATEGORY_DISPLAY"]))
        )
    )
    min_random_count: int = DEFAULT_LIMITS["MIN_RANDOM_COUNT"]
    max_random_count: int = DEFAULT_LIMITS["MAX_RANDOM_COUNT"]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "base_url": self.base_url,
            "site_url": self.site_url,
            "request_timeout": self.request_timeout,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "cache_ttl": self.cache_ttl,
            "search_cache_size": self.search_cache_size,
            "random_pool_size": self.random_pool_size,
            "max_search_results": self.max_search_results,
            "max_random_results": self.max_random_results,
            "max_category_display": self.max_category_display,
            "min_random_count": self.min_random_count,
            "max_random_count": self.max_random_count,
        }

    def validate(self) -> None:
        """验证配置有效性"""
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.retry_delay < 0:
            raise ValueError("retry_delay must be non-negative")
        if self.cache_ttl <= 0:
            raise ValueError("cache_ttl must be positive")
        if self.max_search_results <= 0:
            raise ValueError("max_search_results must be positive")
        if self.min_random_count > self.max_random_count:
            raise ValueError("min_random_count cannot be greater than max_random_count")
