"""常量定义"""

from typing import Dict

# 食谱分类映射
RECIPE_CATEGORIES: Dict[str, str] = {
    "aquatic": "水产",
    "breakfast": "早餐",
    "condiment": "酱料与其他材料",
    "dessert": "甜点",
    "drink": "饮料",
    "meat_dish": "荤菜",
    "semi-finished": "半成品加工",
    "soup": "汤与粥",
    "staple": "主食",
    "vegetable_dish": "素菜",
}

# 中文到英文分类的反向映射
CATEGORIES_ZH_TO_EN: Dict[str, str] = {
    category_zh: category_en for category_en, category_zh in RECIPE_CATEGORIES.items()
}

# 默认限制
DEFAULT_LIMITS = {
    "MAX_SEARCH_RESULTS": 10,
    "MAX_RANDOM_RESULTS": 10,
    "MAX_CATEGORY_DISPLAY": 20,
    "MIN_RANDOM_COUNT": 1,
    "MAX_RANDOM_COUNT": 10,
}

# API相关常量
API_CONSTANTS = {
    "BASE_URL": "https://cook.aiursoft.cn/search/search_index.json",
    "SITE_URL": "https://cook.aiursoft.cn/",
    "REQUEST_TIMEOUT": 10.0,
    "MAX_RETRIES": 3,
    "RETRY_DELAY": 1.0,
}

# 缓存相关常量
CACHE_CONSTANTS = {
    "DEFAULT_TTL": 3600,  # 1小时
    "SEARCH_CACHE_SIZE": 100,
    "RANDOM_POOL_SIZE": 50,
}
