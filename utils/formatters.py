"""响应格式化工具"""

from typing import Any, Dict, List

from ..config.settings import RecipeConfig
from ..models.recipe import Recipe, SearchResult


class ResponseFormatter:
    """响应格式化器

    统一处理各种响应的格式化，确保输出风格一致
    """

    def __init__(self, config: RecipeConfig) -> None:
        self.config = config

    def format_search_result(self, search_result: SearchResult) -> str:
        """格式化搜索结果"""
        if search_result.is_empty:
            return f"🔍 没有找到包含 '{search_result.query}' 的菜品"

        # 构建结果列表
        result_lines = []
        for recipe in search_result.recipes:
            result_lines.append(f"• {recipe.name} ({recipe.category_zh})")

        result_text = "\n".join(result_lines)

        # 添加统计信息
        if search_result.has_more:
            header = f"🔍 搜索 '{search_result.query}' 的结果（显示前{search_result.shown_count}个，共{search_result.total_count}个）："  # noqa: E501
            footer = f"\n\n... 还有 {search_result.total_count - search_result.shown_count} 个结果"
            return f"{header}\n{result_text}{footer}"
        else:
            header = f"🔍 搜索 '{search_result.query}' 的结果（共{search_result.total_count}个）："
            return f"{header}\n{result_text}"

    def format_random_recipes(self, recipes: List[Recipe], requested_count: int) -> str:
        """格式化随机推荐结果"""
        if not recipes:
            return "😔 暂无可推荐的菜品"

        actual_count = len(recipes)
        result_lines = []

        for recipe in recipes:
            result_lines.append(f"• {recipe.name} ({recipe.category_zh})")

        result_text = "\n".join(result_lines)
        return f"🎲 随机推荐 {actual_count} 道菜：\n{result_text}"

    def format_categories_info(
        self, categories_info: Dict[str, int], total_count: int
    ) -> str:
        """格式化分类信息"""
        lines = ["🍳 吃点啥 - 食谱助手"]
        lines.append("=" * 25)
        lines.append("📊 分类及菜品数量:")

        # 按菜品数量排序显示
        sorted_categories = sorted(
            categories_info.items(), key=lambda x: x[1], reverse=True
        )

        for category_zh, count in sorted_categories:
            lines.append(f"  {category_zh}: {count} 种菜品")

        lines.append(f"\n📈 总计: {total_count} 种菜品")
        lines.append("\n🔧 可用指令:")
        lines.append("• /吃点啥 [分类] - 随机推荐菜品")
        lines.append("• /菜谱分类 - 查看所有分类")
        lines.append("• /菜谱搜索 <关键词> - 搜索菜品")
        lines.append("• /怎么做 <菜名> - 获取制作方法")
        lines.append("• /随机推荐 - 随机推荐3道菜")

        return "\n".join(lines)

    def format_category_recipes(self, category_zh: str, recipes: List[Recipe]) -> str:
        """格式化分类下的菜品列表"""
        if not recipes:
            return f"😔 {category_zh} 分类下暂时没有菜品。"

        total_count = len(recipes)
        max_display = self.config.max_category_display

        if total_count > max_display:
            shown_recipes = recipes[:max_display]
            result_lines = [f"• {recipe.name}" for recipe in shown_recipes]
            result_text = "\n".join(result_lines)
            return f"🍽️ {category_zh} 分类下的菜品（显示前{max_display}个，共{total_count}个）：\n{result_text}\n\n... 还有 {total_count - max_display} 个菜品"  # noqa: E501
        else:
            result_lines = [f"• {recipe.name}" for recipe in recipes]
            result_text = "\n".join(result_lines)
            return f"🍽️ {category_zh} 分类下的菜品（共{total_count}个）：\n{result_text}"

    def format_invalid_category(
        self, invalid_category: str, valid_categories: List[str]
    ) -> str:
        """格式化无效分类的错误信息"""
        categories_text = ", ".join(valid_categories)
        return f"❌ 未知分类: {invalid_category}\n🏷️ 可用分类: {categories_text}"

    def format_recipe_url(self, recipe: Recipe) -> str:
        """格式化菜品制作方法URL"""
        return f"📖 {recipe.name} 的制作方式：\n{recipe.full_url}"

    def format_error_message(
        self, error_type: str, message: str, suggestion: str = ""
    ) -> str:
        """格式化错误信息"""
        result = f"❌ {error_type}: {message}"
        if suggestion:
            result += f"\n💡 {suggestion}"
        return result

    def format_success_message(self, message: str) -> str:
        """格式化成功信息"""
        return f"✅ {message}"

    def format_warning_message(self, message: str) -> str:
        """格式化警告信息"""
        return f"⚠️ {message}"

    def format_info_message(self, message: str) -> str:
        """格式化信息提示"""
        return f"ℹ️ {message}"

    def format_stats(self, stats: Dict[str, Any]) -> str:
        """格式化统计信息"""
        lines = ["📊 食谱插件统计信息"]
        lines.append("=" * 25)

        # 基本信息
        if "total_recipes" in stats:
            lines.append(f"📈 总食谱数量: {stats['total_recipes']}")

        # 请求统计
        if "requests" in stats:
            req_stats = stats["requests"]
            lines.append(f"🔍 总请求数: {req_stats.get('requests_total', 0)}")
            lines.append(f"   搜索请求: {req_stats.get('search_requests', 0)}")
            lines.append(f"   随机推荐: {req_stats.get('random_requests', 0)}")
            lines.append(f"   分类查询: {req_stats.get('category_requests', 0)}")

        # 缓存统计
        if "cache_service" in stats:
            cache_stats = stats["cache_service"]
            lines.append("\n💾 缓存统计:")

            for cache_type, cache_info in cache_stats.items():
                if isinstance(cache_info, dict) and "hit_rate" in cache_info:
                    hit_rate = cache_info["hit_rate"]
                    size = cache_info.get("size", 0)
                    max_size = cache_info.get("max_size", 0)
                    lines.append(
                        f"   {cache_type}: {size}/{max_size} 命中率{hit_rate:.1%}"
                    )

        # 搜索服务统计
        if "search_service" in stats and "categories_info" in stats["search_service"]:
            categories = stats["search_service"]["categories_info"]
            lines.append(f"\n🗂️ 分类数量: {len(categories)}")

        return "\n".join(lines)

    def format_validation_error(self, field: str, value: Any, reason: str) -> str:
        """格式化验证错误信息"""
        return f"❌ 参数验证失败: {field}='{value}' - {reason}"

    def format_help_text(
        self, command: str, description: str, usage: str, examples: List[str] = None
    ) -> str:
        """格式化帮助文本"""
        lines = [f"🔧 {command}"]
        lines.append(f"📝 描述: {description}")
        lines.append(f"💡 用法: {usage}")

        if examples:
            lines.append("📋 示例:")
            for example in examples:
                lines.append(f"   {example}")

        return "\n".join(lines)
