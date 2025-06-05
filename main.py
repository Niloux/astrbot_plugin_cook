"""吃点啥 - AstrBot 食谱插件 (重构版)"""

from typing import Optional

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .config.settings import RecipeConfig
from .data.remote_source import RemoteRecipeSource
from .services.recipe_service import RecipeService
from .utils.formatters import ResponseFormatter
from .utils.validators import DataValidator, ValidationError


@register("cook", "AstrBot", "吃点啥 - 食谱推荐插件", "2.0.0")
class CookPlugin(Star):
    """食谱插件主类 - 重构版

    提供食谱搜索、随机推荐、分类查看等功能
    使用全新的架构设计，提供更好的性能和可维护性
    """

    def __init__(self, context: Context):
        super().__init__(context)

        # 核心服务组件
        self._recipe_service: Optional[RecipeService] = None
        self._validator: Optional[DataValidator] = None
        self._formatter: Optional[ResponseFormatter] = None
        self._config: Optional[RecipeConfig] = None

        # 初始化状态
        self._is_ready = False
        self._initialization_error: Optional[str] = None

    async def initialize(self):
        """初始化插件"""
        try:
            logger.info("开始初始化食谱插件 v2.0...")

            # 1. 加载配置
            self._config = RecipeConfig()
            self._config.validate()

            # 2. 初始化工具类
            self._validator = DataValidator(self._config)
            self._formatter = ResponseFormatter(self._config)

            # 3. 初始化数据源
            data_source = RemoteRecipeSource(self._config)

            # 4. 初始化核心服务
            self._recipe_service = RecipeService(data_source, self._config)
            await self._recipe_service.initialize()

            self._is_ready = True
            logger.info("食谱插件初始化完成 v2.0")

        except Exception as e:
            error_msg = f"食谱插件初始化失败: {str(e)}"
            logger.error(error_msg)
            self._initialization_error = error_msg
            self._is_ready = False

    def _ensure_ready(self) -> bool:
        """确保插件已准备就绪"""
        return self._is_ready and self._recipe_service is not None

    def _get_error_response(self, event: AstrMessageEvent) -> str:
        """获取错误响应"""
        if self._initialization_error:
            return f"❌ 插件未就绪: {self._initialization_error}"
        else:
            return "❌ 食谱数据未加载完成，请稍后再试"

    @filter.command("吃点啥")
    async def random_recommend(self, event: AstrMessageEvent, category: str = ""):
        """随机推荐菜品 - 可指定分类，如：/吃点啥 主食"""
        if not self._ensure_ready():
            yield event.plain_result(self._get_error_response(event))
            return

        try:
            # 输入验证和清理
            if category:
                category = self._validator.sanitize_input(category)

                # 验证分类（在服务层会进一步验证）
                if not category.strip():
                    yield event.plain_result("❌ 分类名称不能为空")
                    return

            # 调用服务层
            result = await self._recipe_service.get_random_recipe(category if category else None)
            yield event.plain_result(result)

        except ValidationError as e:
            error_msg = self._formatter.format_validation_error(e.field, e.value, e.reason)
            yield event.plain_result(error_msg)
        except Exception as e:
            logger.error(f"随机推荐失败: {str(e)}")
            yield event.plain_result(f"❌ 推荐失败: {str(e)}")

    @filter.command("菜谱分类")
    async def show_categories(self, event: AstrMessageEvent):
        """查看所有菜品分类"""
        if not self._ensure_ready():
            yield event.plain_result(self._get_error_response(event))
            return

        try:
            result = self._recipe_service.get_categories_info()
            yield event.plain_result(result)

        except Exception as e:
            logger.error(f"获取分类信息失败: {str(e)}")
            yield event.plain_result(f"❌ 获取分类信息失败: {str(e)}")

    @filter.command("菜谱搜索")
    async def search_recipe(self, event: AstrMessageEvent, keyword: str):
        """搜索菜品 - 根据关键词搜索，如：/菜谱搜索 鸡"""
        if not self._ensure_ready():
            yield event.plain_result(self._get_error_response(event))
            return

        try:
            # 输入验证
            keyword = self._validator.validate_search_keyword(keyword)

            # 调用服务层
            result = await self._recipe_service.search_recipes(keyword)
            yield event.plain_result(result)

        except ValidationError as e:
            error_msg = self._formatter.format_validation_error(e.field, e.value, e.reason)
            yield event.plain_result(error_msg)
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            yield event.plain_result(f"❌ 搜索失败: {str(e)}")

    @filter.command("怎么做")
    async def how_to_cook(self, event: AstrMessageEvent, dish_name: str):
        """获取菜品制作方法 - 如：/怎么做 手工水饺"""
        if not self._ensure_ready():
            yield event.plain_result(self._get_error_response(event))
            return

        try:
            # 输入验证
            dish_name = self._validator.validate_recipe_name(dish_name)

            # 调用服务层
            result = await self._recipe_service.get_recipe_url(dish_name)
            yield event.plain_result(result)

        except ValidationError as e:
            error_msg = self._formatter.format_validation_error(e.field, e.value, e.reason)
            yield event.plain_result(error_msg)
        except Exception as e:
            logger.error(f"获取制作方法失败: {str(e)}")
            yield event.plain_result(f"❌ 获取制作方法失败: {str(e)}")

    @filter.command("随机推荐")
    async def random_recipes(self, event: AstrMessageEvent, count: int = 3):
        """随机推荐菜品 - 可指定数量，如：/随机推荐 5"""
        if not self._ensure_ready():
            yield event.plain_result(self._get_error_response(event))
            return

        try:
            # 输入验证
            count = self._validator.validate_random_count(count)

            # 调用服务层
            result = await self._recipe_service.get_random_recipes_batch(count)
            yield event.plain_result(result)

        except ValidationError as e:
            error_msg = self._formatter.format_validation_error(e.field, e.value, e.reason)
            yield event.plain_result(error_msg)
        except Exception as e:
            logger.error(f"随机推荐失败: {str(e)}")
            yield event.plain_result(f"❌ 随机推荐失败: {str(e)}")

    @filter.command("食谱统计")
    async def show_stats(self, event: AstrMessageEvent):
        """显示插件统计信息 - 管理员功能"""
        if not self._ensure_ready():
            yield event.plain_result(self._get_error_response(event))
            return

        try:
            stats = self._recipe_service.get_service_stats()
            result = self._formatter.format_stats(stats)
            yield event.plain_result(result)

        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}")
            yield event.plain_result(f"❌ 获取统计信息失败: {str(e)}")

    @filter.command("重载食谱")
    async def reload_recipes(self, event: AstrMessageEvent):
        """重新加载食谱数据 - 管理员功能"""
        if not self._ensure_ready():
            yield event.plain_result(self._get_error_response(event))
            return

        try:
            result = await self._recipe_service.reload_data()
            yield event.plain_result(result)

        except Exception as e:
            logger.error(f"重载数据失败: {str(e)}")
            yield event.plain_result(f"❌ 重载数据失败: {str(e)}")

    @filter.command("食谱帮助")
    async def show_help(self, event: AstrMessageEvent):
        """显示详细帮助信息"""
        help_text = self._formatter.format_help_text(
            "食谱插件帮助",
            "提供食谱搜索和推荐功能",
            "使用以下命令与插件交互",
            [
                "/吃点啥 [分类] - 随机推荐菜品",
                "/菜谱分类 - 查看所有分类",
                "/菜谱搜索 <关键词> - 搜索菜品",
                "/怎么做 <菜名> - 获取制作方法",
                "/随机推荐 [数量] - 随机推荐多道菜",
                "/食谱统计 - 查看统计信息",
                "/重载食谱 - 重新加载数据",
                "/食谱帮助 - 显示此帮助",
            ],
        )
        yield event.plain_result(help_text)

    async def terminate(self):
        """插件销毁时的清理工作"""
        try:
            if self._recipe_service:
                await self._recipe_service.cleanup()

            logger.info("食谱插件已卸载")

        except Exception as e:
            logger.error(f"插件清理失败: {str(e)}")


# 向后兼容：保留原有的类名引用
Recipes = None  # 标记为已废弃，使用新的服务架构
