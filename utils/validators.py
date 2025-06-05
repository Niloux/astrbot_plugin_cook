"""数据验证工具"""

import re
from typing import Any, Dict, List

from ..config.settings import RecipeConfig


class ValidationError(Exception):
    """验证错误异常"""

    def __init__(self, field: str, value: Any, reason: str) -> None:
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(f"Validation failed for {field}='{value}': {reason}")


class DataValidator:
    """数据验证器

    提供统一的数据验证逻辑，确保数据完整性和有效性
    """

    def __init__(self, config: RecipeConfig) -> None:
        self.config = config

    def validate_recipe_name(self, name: Any) -> str:
        """验证食谱名称"""
        if not isinstance(name, str):
            raise ValidationError("recipe_name", name, "必须是字符串类型")

        name = name.strip()
        if not name:
            raise ValidationError("recipe_name", name, "不能为空")

        if len(name) > 100:
            raise ValidationError("recipe_name", name, "长度不能超过100个字符")

        # 检查是否包含非法字符
        if re.search(r'[<>:"/\\|?*]', name):
            raise ValidationError("recipe_name", name, "包含非法字符")

        return name

    def validate_category(self, category: Any, valid_categories: List[str]) -> str:
        """验证分类"""
        if not isinstance(category, str):
            raise ValidationError("category", category, "必须是字符串类型")

        category = category.strip()
        if not category:
            raise ValidationError("category", category, "不能为空")

        if category not in valid_categories:
            valid_list = ", ".join(valid_categories[:5])  # 只显示前5个
            if len(valid_categories) > 5:
                valid_list += f" 等{len(valid_categories)}个分类"
            raise ValidationError("category", category, f"无效分类，可用分类: {valid_list}")

        return category

    def validate_url(self, url: Any) -> str:
        """验证URL"""
        if not isinstance(url, str):
            raise ValidationError("url", url, "必须是字符串类型")

        url = url.strip()
        if not url:
            raise ValidationError("url", url, "不能为空")

        # 简单的URL格式验证
        url_pattern = re.compile(
            r"^(?:http|ftp)s?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        if not url_pattern.match(url) and not url.startswith("/"):
            raise ValidationError("url", url, "URL格式无效")

        return url

    def validate_search_keyword(self, keyword: Any) -> str:
        """验证搜索关键词"""
        if not isinstance(keyword, str):
            raise ValidationError("search_keyword", keyword, "必须是字符串类型")

        keyword = keyword.strip()
        if not keyword:
            raise ValidationError("search_keyword", keyword, "搜索关键词不能为空")

        if len(keyword) > 50:
            raise ValidationError("search_keyword", keyword, "搜索关键词长度不能超过50个字符")

        # 检查是否包含特殊字符（允许中文、英文、数字、空格）
        if not re.match(r"^[\u4e00-\u9fa5a-zA-Z0-9\s]+$", keyword):
            raise ValidationError("search_keyword", keyword, "只能包含中文、英文、数字和空格")

        return keyword

    def validate_count(self, count: Any, min_val: int = 1, max_val: int = 10) -> int:
        """验证数量参数"""
        # 类型转换
        if isinstance(count, str):
            try:
                count = int(count)
            except ValueError:
                raise ValidationError("count", count, "必须是有效的整数")

        if not isinstance(count, int):
            raise ValidationError("count", count, "必须是整数类型")

        if count < min_val:
            raise ValidationError("count", count, f"不能小于{min_val}")

        if count > max_val:
            raise ValidationError("count", count, f"不能大于{max_val}")

        return count

    def validate_random_count(self, count: Any) -> int:
        """验证随机推荐数量"""
        return self.validate_count(
            count, self.config.min_random_count, self.config.max_random_count
        )

    def validate_search_results_limit(self, limit: Any) -> int:
        """验证搜索结果限制数量"""
        return self.validate_count(limit, 1, self.config.max_search_results)

    def validate_recipe_data(self, recipe_data: Dict[str, Any]) -> Dict[str, str]:
        """验证完整的食谱数据"""
        required_fields = ["name", "category", "category_zh", "url"]

        # 检查必需字段
        for field in required_fields:
            if field not in recipe_data:
                raise ValidationError("recipe_data", recipe_data, f"缺少必需字段: {field}")

        validated_data = {}

        # 验证名称
        validated_data["name"] = self.validate_recipe_name(recipe_data["name"])

        # 验证分类（这里假设英文分类已验证）
        if not isinstance(recipe_data["category"], str) or not recipe_data["category"].strip():
            raise ValidationError("category", recipe_data["category"], "英文分类无效")
        validated_data["category"] = recipe_data["category"].strip()

        # 验证中文分类
        if (
            not isinstance(recipe_data["category_zh"], str)
            or not recipe_data["category_zh"].strip()
        ):
            raise ValidationError("category_zh", recipe_data["category_zh"], "中文分类无效")
        validated_data["category_zh"] = recipe_data["category_zh"].strip()

        # 验证URL
        validated_data["url"] = self.validate_url(recipe_data["url"])

        return validated_data

    def validate_command_params(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """验证命令参数"""
        validated_params = {}

        if command == "search":
            if "keyword" in params:
                validated_params["keyword"] = self.validate_search_keyword(params["keyword"])
            if "limit" in params:
                validated_params["limit"] = self.validate_search_results_limit(params["limit"])

        elif command == "random":
            if "count" in params:
                validated_params["count"] = self.validate_random_count(params["count"])
            if "category" in params and params["category"]:
                # 分类验证需要在具体使用时进行，这里只做基础验证
                if not isinstance(params["category"], str):
                    raise ValidationError("category", params["category"], "必须是字符串类型")
                validated_params["category"] = params["category"].strip()

        elif command == "recipe_url":
            if "dish_name" in params:
                validated_params["dish_name"] = self.validate_recipe_name(params["dish_name"])

        return validated_params

    def validate_config(self, config: Dict[str, Any]) -> None:
        """验证配置参数"""
        # 验证超时设置
        if "request_timeout" in config:
            timeout = config["request_timeout"]
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                raise ValidationError("request_timeout", timeout, "必须是正数")

        # 验证重试次数
        if "max_retries" in config:
            retries = config["max_retries"]
            if not isinstance(retries, int) or retries < 0:
                raise ValidationError("max_retries", retries, "必须是非负整数")

        # 验证缓存TTL
        if "cache_ttl" in config:
            ttl = config["cache_ttl"]
            if not isinstance(ttl, int) or ttl <= 0:
                raise ValidationError("cache_ttl", ttl, "必须是正整数")

        # 验证限制参数
        limit_fields = ["max_search_results", "max_random_results", "max_category_display"]
        for field in limit_fields:
            if field in config:
                value = config[field]
                if not isinstance(value, int) or value <= 0:
                    raise ValidationError(field, value, "必须是正整数")

    def sanitize_input(self, text: Any) -> str:
        """清理用户输入"""
        if not isinstance(text, str):
            text = str(text)

        # 移除首尾空白
        text = text.strip()

        # 移除控制字符
        text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)

        # 限制长度
        if len(text) > 200:
            text = text[:200]

        return text

    def is_safe_filename(self, filename: str) -> bool:
        """检查文件名是否安全"""
        if not filename or filename.strip() != filename:
            return False

        # 检查危险字符
        dangerous_chars = r'[<>:"/\\|?*\x00-\x1f]'
        if re.search(dangerous_chars, filename):
            return False

        # 检查保留名称
        reserved_names = [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        ]

        if filename.upper() in reserved_names:
            return False

        return True
