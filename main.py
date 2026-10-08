from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools
from astrbot.api import logger

from .data_sources.mock import MockBoxDataSource
from .domain.bindings import ChatUser
from .presentation.accounts_text import render_account_selection, render_bound_accounts
from .presentation.box_text import render_box_text
from .presentation.skins_text import render_skins_text
from .services.binding_service import BindingService
from .services.box_service import BoxService
from .storage.sqlite_bindings import SQLiteBindingStore


class Reverse1999Plugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        data_source = MockBoxDataSource()
        self._box_service = BoxService(data_source)
        data_dir = StarTools.get_data_dir("astrbot_plugin_reverse1999")
        self._binding_service = BindingService(SQLiteBindingStore(data_dir / "bindings.sqlite3"))

    async def initialize(self):
        logger.info("[R1999] Reverse1999 插件初始化成功")

    @filter.command("1999测试")
    async def test(self, event: AstrMessageEvent):
        """测试 Reverse1999 插件是否正常加载。"""
        yield event.plain_result("Reverse1999 插件已正常加载。")

    @filter.command("1999box")
    async def box(self, event: AstrMessageEvent, player_id: str = ""):
        """展示模拟角色 Box，可指定玩家标识。"""
        player_id, prompt = await self._resolve_player_id(event, player_id, "1999box")
        if player_id is None:
            yield event.plain_result(prompt)
            return
        box = await self._box_service.get_box(player_id)
        if box is None:
            yield event.plain_result(f"未找到模拟玩家：{player_id}。")
            return
        text = render_box_text(box)
        yield event.plain_result(text)

    @filter.command("1999皮肤")
    async def skins(self, event: AstrMessageEvent, player_id: str = ""):
        """展示模拟玩家拥有的皮肤，可指定玩家标识。"""
        player_id, prompt = await self._resolve_player_id(event, player_id, "1999皮肤")
        if player_id is None:
            yield event.plain_result(prompt)
            return
        box = await self._box_service.get_box(player_id)
        if box is None:
            yield event.plain_result(f"未找到模拟玩家：{player_id}。")
            return
        text = render_skins_text(box)
        yield event.plain_result(text)

    def _chat_user(self, event: AstrMessageEvent) -> ChatUser:
        platform = event.get_platform_name()
        user_id = event.get_sender_id()
        if not platform or not user_id:
            raise ValueError("无法识别当前用户，请从正常的聊天账号发送指令。")
        return ChatUser(platform=platform, user_id=user_id)

    async def _resolve_player_id(
        self, event: AstrMessageEvent, player_id: str, command: str
    ) -> tuple[str | None, str]:
        try:
            selection = await self._binding_service.select_account(self._chat_user(event), player_id)
        except ValueError as error:
            return None, str(error)
        if selection.player_id is not None:
            return selection.player_id, ""
        return None, render_account_selection(selection.candidates, command)

    @filter.command("1999绑定")
    async def bind(self, event: AstrMessageEvent, player_id: str = ""):
        """绑定账号；可多次执行以绑定多个账号。"""
        if not player_id.strip():
            yield event.plain_result("用法：/1999绑定 UID；当前可用 player-a 等模拟标识测试。")
            return
        try:
            added = await self._binding_service.bind(self._chat_user(event), player_id)
        except ValueError as error:
            yield event.plain_result(str(error))
            return
        status = "已绑定账号" if added else "你已绑定该账号"
        yield event.plain_result(f"{status}：{player_id.strip()}。绑定跨群聊和私聊共用；当前查询仍为模拟数据。")

    @filter.command("1999账号")
    async def accounts(self, event: AstrMessageEvent):
        """查看当前用户的所有绑定。"""
        try:
            accounts = await self._binding_service.list_accounts(self._chat_user(event))
        except ValueError as error:
            yield event.plain_result(str(error))
            return
        yield event.plain_result(render_bound_accounts(accounts))

    @filter.command("1999解绑")
    async def unbind(self, event: AstrMessageEvent, player_id: str = ""):
        """仅移除当前用户与指定账号的绑定。"""
        if not player_id.strip():
            yield event.plain_result("用法：/1999解绑 UID")
            return
        try:
            removed = await self._binding_service.unbind(self._chat_user(event), player_id)
        except ValueError as error:
            yield event.plain_result(str(error))
            return
        status = "已解除绑定" if removed else "你未绑定该账号"
        yield event.plain_result(f"{status}：{player_id.strip()}。")

    async def terminate(self):
        """插件关闭或卸载时调用。"""
