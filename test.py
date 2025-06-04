"""吃点啥"""

import logging
import random
import urllib.parse

import requests


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
        self.recipes = {type_zh: {} for type_zh in self.TYPES.values()}  # 改为字典存储菜名和URL
        self.total_count = 0
        self._fetch_and_process_recipes()

    def _fetch_and_process_recipes(self):
        """从远程获取并处理食谱数据"""
        try:
            response = requests.get(self.BASE_URL, timeout=10)
            response.raise_for_status()
            data = response.json().get("docs", [])
            self._process_recipes(data)
        except requests.RequestException as e:
            logging.error(f"请求失败: {e}")
        except ValueError as e:
            logging.error(f"解析响应失败: {e}")

    def _process_recipes(self, data):
        """处理并分类存储食谱数据"""
        if not data:
            logging.error("未获取到食谱数据。")
            return

        dish_urls = {}  # 用于去重和存储完整URL

        for item in data:
            location = item.get("location", "")
            if not location or "dishes/" not in location or "#" in location:
                continue

            # 解析URL结构: dishes/category/dish_name/
            parts = location.split("dishes/")
            if len(parts) < 2:
                continue

            path_parts = parts[1].strip("/").split("/")
            if len(path_parts) < 2:
                continue

            category = path_parts[0]
            dish_name_encoded = path_parts[1]

            # URL解码获取菜名
            try:
                dish_name = urllib.parse.unquote(dish_name_encoded)
            except Exception:
                continue

            # 检查分类是否存在
            if category not in self.TYPES:
                continue

            category_zh = self.TYPES[category]

            # 存储菜名和对应的URL（去重）
            if dish_name not in dish_urls:
                dish_urls[dish_name] = location
                self.recipes[category_zh][dish_name] = location

        # 统计总数
        self.total_count = sum(len(dishes) for dishes in self.recipes.values())

        if self.total_count == 0:
            logging.warning("没有找到有效的菜谱数据")

    def all_recipes(self):
        """获取所有分类及菜品"""
        return self.recipes

    def random_recipe(self, category):
        """随机获取指定分类中的菜品"""
        if category not in self.recipes:
            logging.warning(f"未知分类: {category}")
            return f"未知分类: {category}"

        if not self.recipes[category]:
            logging.warning(f"分类 '{category}' 下没有菜品。")
            return f"分类 '{category}' 下没有菜品。"

        selected_dish = random.choice(list(self.recipes[category].keys()))
        return f"推荐的{category}: {selected_dish}。"

    def help(self):
        """生成帮助信息"""
        msgs = ["🍳 食谱系统帮助"]
        msgs.append("=" * 20)
        msgs.append("分类及菜品数量:")
        for category, dishes in self.recipes.items():
            msgs.append(f"  {category}: {len(dishes)} 种菜品")
        msgs.append(f"\n📊 总计: {self.total_count} 种菜品")
        msgs.append("\n🔧 可用命令:")
        msgs.append("• /what_we_have <分类> - 获取指定分类下的菜品")
        msgs.append("• /what_to_eat <分类> - 随机推荐指定分类的菜品")
        msgs.append("• /how_to_cook <菜名> - 获取菜品的制作方法")
        return "\n".join(msgs)

    def how_to_cook(self, food):
        """获取菜品的制作方式"""
        # 在所有分类中查找菜品
        for category, dishes in self.recipes.items():
            if food in dishes:
                dish_url = dishes[food]
                full_url = self.SITE_URL + dish_url
                return f"📖 {food} 的制作方式：\n{full_url}"

        logging.warning(f"未找到菜品: {food}")
        return f"❌ 未找到菜品: {food}\n💡 建议使用 /what_we_have <分类> 查看可用菜品"

    def what_we_have(self, category):
        """获取指定分类下的菜品列表"""
        if category not in self.recipes:
            available_categories = ", ".join(self.recipes.keys())
            return f"❌ 未知分类: {category}\n🏷️ 可用分类: {available_categories}"

        dishes = list(self.recipes[category].keys())
        if dishes:
            # 如果菜品太多，只显示前20个并提示总数
            if len(dishes) > 20:
                shown_dishes = dishes[:20]
                dish_list = "\n".join(f"• {dish}" for dish in shown_dishes)
                return f"🍽️ {category} 分类下的菜品（显示前20个，共{len(dishes)}个）：\n{dish_list}\n\n... 还有 {len(dishes) - 20} 个菜品"
            else:
                dish_list = "\n".join(f"• {dish}" for dish in dishes)
                return f"🍽️ {category} 分类下的菜品（共{len(dishes)}个）：\n{dish_list}"
        else:
            return f"😔 {category} 分类下暂时没有菜品。"

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

    def get_random_recipes(self, count=5):
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


recipes = Recipes()


if __name__ == "__main__":
    print("=== 升级版食谱系统测试 ===\n")

    # 初始化食谱系统
    print("1. 初始化食谱系统...")
    recipes = Recipes()
    print("✓ 食谱系统初始化完成\n")

    # 测试帮助信息
    print("2. 测试帮助信息:")
    help_info = recipes.help()
    print(help_info)
    print()

    # 测试获取所有食谱分类
    print("3. 测试获取所有食谱分类:")
    all_recipes = recipes.all_recipes()
    total_dishes = 0
    for category, dishes in all_recipes.items():
        count = len(dishes)
        total_dishes += count
        print(f"  {category}: {count} 种菜品")
    print(f"  总计: {total_dishes} 种菜品")
    print()

    # 测试随机推荐功能
    print("4. 测试随机推荐功能:")
    test_categories = ["主食", "素菜", "荤菜", "汤与粥", "甜点"]
    for category in test_categories:
        result = recipes.random_recipe(category)
        print(f"  {result}")

    # 测试未知分类
    unknown_result = recipes.random_recipe("未知分类")
    print(f"  {unknown_result}")
    print()

    # 测试获取指定分类下的菜品（只显示前3个菜）
    print("5. 测试获取指定分类下的菜品:")
    test_category = "早餐"
    what_we_have_result = recipes.what_we_have(test_category)
    # 只显示前几行
    lines = what_we_have_result.split("\n")
    if len(lines) > 8:
        print("\n".join(lines[:8]) + "\n  ... （更多菜品已省略）")
    else:
        print(what_we_have_result)
    print()

    # 测试搜索功能
    print("6. 测试搜索功能:")
    search_result = recipes.search_recipe("鸡")
    print(f"  {search_result}")
    print()

    # 测试获取菜品制作方式
    print("7. 测试获取菜品制作方式:")
    # 先获取一个菜品来测试
    if recipes.recipes["主食"]:
        test_dish = list(recipes.recipes["主食"].keys())[0]
        cook_result = recipes.how_to_cook(test_dish)
        print(f"  {cook_result}")

    # 测试不存在的菜品
    non_exist_result = recipes.how_to_cook("不存在的菜品")
    print(f"  {non_exist_result}")
    print()

    # 测试随机推荐多道菜
    print("8. 测试随机推荐多道菜:")
    random_recipes_result = recipes.get_random_recipes(3)
    print(f"  {random_recipes_result}")
    print()

    print("=== 升级版测试完成 ===")
