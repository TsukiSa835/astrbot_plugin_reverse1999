from typing import Protocol

from .models import PlayerBox


class BoxDataSource(Protocol):
    """Box 数据源需要提供的查询能力。"""

    async def get_box(self, player_id: str) -> PlayerBox | None:
        """返回玩家 Box；玩家不存在时返回 None。"""
        ...
