from dataclasses import dataclass
from typing import List


@dataclass
class Character:
    """玩家拥有的一个角色。"""

    name: str
    level: int


@dataclass
class PlayerBox:
    """一个玩家的角色集合。"""

    player_id: str
    characters: List[Character]
