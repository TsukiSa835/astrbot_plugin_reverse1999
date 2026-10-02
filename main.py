from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger


class Reverse1999Plugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        logger.info("[R1999] Reverse1999 插件初始化成功")

    @filter.command("1999测试")
    async def test(self, event: AstrMessageEvent):
        """测试 Reverse1999 插件是否正常加载。"""
        yield event.plain_result("Reverse1999 插件已正常加载。")

    async def terminate(self):
        """插件关闭或卸载时调用。"""