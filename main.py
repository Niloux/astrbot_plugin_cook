"""吃点啥 - AstrBot 食谱插件"""

import random
import urllib.parse

import httpx

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


class Recipes:
    """食谱获取与管理类"""

    BASE_URL = "https://cook.aiursoft.cn/search/search_index.json"
    SITE_URL = "https://cook.aiursoft.cn/"
    TYPES = {
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
    TYPES_ZH_TO_EN = {type_zh: type_en for type_en, type_zh in TYPES.items()}

    def __init__(self):
        self.recipes = {type_zh: {} for type_zh in self.TYPES.values()}
        self.total_count = 0

    async def fetch_and_process_recipes(self):
        """从远程获取并处理食谱数据"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.BASE_URL)
                response.raise_for_status()
                data = response.json().get("docs", [])
                self._process_recipes(data)
        except httpx.RequestError as e:
            logger.error(f"请求失败: {e}")
        except ValueError as e:
            logger.error(f"解析响应失败: {e}")

    def _process_recipes(self, data):
        """处理并分类存储食谱数据"""
        if not data:
            logger.error("未获取到食谱数据。")
            return

        dish_urls = {}

        for item in data:
            location = item.get("location", "")
            if not location or "dishes/" not in location or "#" in location:
                continue

            parts = location.split("dishes/")
            if len(parts) < 2:
                continue

            path_parts = parts[1].strip("/").split("/")
            if len(path_parts) < 2:
                continue

            category = path_parts[0]
            dish_name_encoded = path_parts[1]

            try:
                dish_name = urllib.parse.unquote(dish_name_encoded)
            except Exception:
                continue

            if category not in self.TYPES:
                continue

            category_zh = self.TYPES[category]

            if dish_name not in dish_urls:
                dish_urls[dish_name] = location
                self.recipes[category_zh][dish_name] = location

        self.total_count = sum(len(dishes) for dishes in self.recipes.values())

        if self.total_count == 0:
            logger.warning("没有找到有效的菜谱数据")

    def random_recipe(self, category):
        """随机获取指定分类中的菜品"""
        if category not in self.recipes:
            return f"❌ 未知分类: {category}\n🏷️ 可用分类: {', '.join(self.recipes.keys())}"

        if not self.recipes[category]:
            return f"😔 分类 '{category}' 下暂时没有菜品。"

        selected_dish = random.choice(list(self.recipes[category].keys()))
        return f"🍽️ 推荐的{category}: {selected_dish}"

    def what_we_have(self, category):
        """获取指定分类下的菜品列表"""
        if category not in self.recipes:
            available_categories = ", ".join(self.recipes.keys())
            return f"❌ 未知分类: {category}\n🏷️ 可用分类: {available_categories}"

        dishes = list(self.recipes[category].keys())
        if dishes:
            if len(dishes) > 20:
                shown_dishes = dishes[:20]
                dish_list = "\n".join(f"• {dish}" for dish in shown_dishes)
                return f"🍽️ {category} 分类下的菜品（显示前20个，共{len(dishes)}个）：\n{dish_list}\n\n... 还有 {len(dishes) - 20} 个菜品"
            else:
                dish_list = "\n".join(f"• {dish}" for dish in dishes)
                return f"🍽️ {category} 分类下的菜品（共{len(dishes)}个）：\n{dish_list}"
        else:
            return f"😔 {category} 分类下暂时没有菜品。"

    def how_to_cook(self, food):
        """获取菜品的制作方式"""
        for category, dishes in self.recipes.items():
            if food in dishes:
                dish_url = dishes[food]
                full_url = self.SITE_URL + dish_url
                return f"📖 {food} 的制作方式：\n{full_url}"

        return f"❌ 未找到菜品: {food}\n💡 建议使用 /菜谱分类 查看可用菜品"

    def search_recipe(self, keyword):
        """根据关键词搜索菜品"""
        results = []
        for category, dishes in self.recipes.items():
            for dish_name in dishes.keys():
                if keyword.lower() in dish_name.lower():
                    results.append((category, dish_name))

        if not results:
            return f"🔍 没有找到包含 '{keyword}' 的菜品"

        if len(results) > 10:
            shown_results = results[:10]
            result_list = "\n".join(f"• {dish} ({category})" for category, dish in shown_results)
            return f"🔍 搜索 '{keyword}' 的结果（显示前10个，共{len(results)}个）：\n{result_list}\n\n... 还有 {len(results) - 10} 个结果"
        else:
            result_list = "\n".join(f"• {dish} ({category})" for category, dish in results)
            return f"🔍 搜索 '{keyword}' 的结果（共{len(results)}个）：\n{result_list}"

    def get_random_recipes(self, count=3):
        """获取随机推荐的菜品"""
        all_dishes = []
        for category, dishes in self.recipes.items():
            for dish_name in dishes.keys():
                all_dishes.append((category, dish_name))

        if not all_dishes:
            return "😔 暂无可推荐的菜品"

        random_count = min(count, len(all_dishes))
        random_dishes = random.sample(all_dishes, random_count)

        result_list = "\n".join(f"• {dish} ({category})" for category, dish in random_dishes)
        return f"🎲 随机推荐 {random_count} 道菜：\n{result_list}"

    def help(self):
        """生成帮助信息"""
        msgs = ["🍳 吃点啥 - 食谱助手"]
        msgs.append("=" * 25)
        msgs.append("📊 分类及菜品数量:")
        for category, dishes in self.recipes.items():
            msgs.append(f"  {category}: {len(dishes)} 种菜品")
        msgs.append(f"\n📈 总计: {self.total_count} 种菜品")
        msgs.append("\n🔧 可用指令:")
        msgs.append("• /吃点啥 [分类] - 随机推荐菜品")
        msgs.append("• /菜谱分类 - 查看所有分类")
        msgs.append("• /菜谱搜索 <关键词> - 搜索菜品")
        msgs.append("• /怎么做 <菜名> - 获取制作方法")
        msgs.append("• /随机推荐 - 随机推荐3道菜")
        return "\n".join(msgs)


@register("cook", "AstrBot", "吃点啥 - 食谱推荐插件", "1.0.0")
class CookPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.recipes = None

    async def initialize(self):
        """初始化食谱数据"""
        logger.info("正在初始化食谱插件...")
        self.recipes = Recipes()
        await self.recipes.fetch_and_process_recipes()
        logger.info(f"食谱插件初始化完成，共加载 {self.recipes.total_count} 种菜品")

    @filter.command("吃点啥")
    async def random_recommend(self, event: AstrMessageEvent):
        """随机推荐菜品 - 可指定分类，如：/吃点啥 主食"""
        if not self.recipes:
            yield event.plain_result("❌ 食谱数据未加载完成，请稍后再试")
            return

        message_str = event.message_str.strip()
        if message_str:
            # 指定分类推荐
            result = self.recipes.random_recipe(message_str)
        else:
            # 随机推荐一道菜
            result = self.recipes.get_random_recipes(1)

        yield event.plain_result(result)

    @filter.command("菜谱分类")
    async def show_categories(self, event: AstrMessageEvent):
        """查看所有菜品分类"""
        if not self.recipes:
            yield event.plain_result("❌ 食谱数据未加载完成，请稍后再试")
            return

        result = self.recipes.help()
        yield event.plain_result(result)

    @filter.command("菜谱搜索")
    async def search_recipe(self, event: AstrMessageEvent):
        """搜索菜品 - 根据关键词搜索，如：/菜谱搜索 鸡"""
        if not self.recipes:
            yield event.plain_result("❌ 食谱数据未加载完成，请稍后再试")
            return

        keyword = event.message_str.strip()
        if not keyword:
            yield event.plain_result("❌ 请提供搜索关键词，如：/菜谱搜索 鸡")
            return

        result = self.recipes.search_recipe(keyword)
        yield event.plain_result(result)

    @filter.command("怎么做")
    async def how_to_cook(self, event: AstrMessageEvent):
        """获取菜品制作方法 - 如：/怎么做 手工水饺"""
        if not self.recipes:
            yield event.plain_result("❌ 食谱数据未加载完成，请稍后再试")
            return

        dish_name = event.message_str.strip()
        if not dish_name:
            yield event.plain_result("❌ 请提供菜品名称，如：/怎么做 手工水饺")
            return

        result = self.recipes.how_to_cook(dish_name)
        yield event.plain_result(result)

    @filter.command("随机推荐")
    async def random_recipes(self, event: AstrMessageEvent):
        """随机推荐3道不同的菜品"""
        if not self.recipes:
            yield event.plain_result("❌ 食谱数据未加载完成，请稍后再试")
            return

        result = self.recipes.get_random_recipes(3)
        yield event.plain_result(result)

    async def terminate(self):
        """插件销毁时的清理工作"""
        logger.info("食谱插件已卸载")
