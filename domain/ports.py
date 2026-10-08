from typing import Protocol

from .catalog import CatalogCharacter, CatalogSkin, StaticImage
from .bindings import ChatUser
from .models import PlayerBox


class BoxDataSource(Protocol):
    """Box 数据源需要提供的查询能力。"""

    async def get_box(self, player_id: str) -> PlayerBox | None:
        """返回玩家 Box；玩家不存在时返回 None。"""
        ...


class BindingStore(Protocol):
    """绑定存储约定；每个用户可以关联多个账号。"""

    async def list_accounts(self, user: ChatUser) -> list[str]:
        ...

    async def bind(self, user: ChatUser, player_id: str) -> bool:
        """新增返回 True，已存在返回 False。"""
        ...

    async def unbind(self, user: ChatUser, player_id: str) -> bool:
        """删除返回 True，不存在返回 False。"""
        ...


class CharacterCatalog(Protocol):
    """公共资料查询约定，与玩家账号和聊天平台无关。"""

    async def get_character(self, character_id: str) -> CatalogCharacter | None:
        ...

    async def get_skin(self, character_id: str, skin_id: str) -> CatalogSkin | None:
        ...

    async def get_image(self, character_id: str, skin_id: str,
                        kind: str = "portrait") -> StaticImage | None:
        ...
