from ..domain.models import PlayerBox
from ..domain.ports import BoxDataSource


class BoxService:
    """通过数据源查询玩家 Box。"""

    def __init__(self, data_source: BoxDataSource):
        self._data_source = data_source

    async def get_box(self, player_id: str) -> PlayerBox | None:
        """返回玩家 Box；玩家不存在时返回 None。"""
        box = await self._data_source.get_box(player_id)
        if box is None:
            return None
        characters = sorted(box.characters, key=lambda character: character.is_favorite is not True)
        return PlayerBox(player_id=box.player_id, characters=characters)
