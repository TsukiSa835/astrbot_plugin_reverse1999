from ..domain.models import Character, PlayerBox


class MockBoxDataSource:
    """提供模拟 Box，供开发阶段验证流程。"""

    async def get_box(self, player_id: str) -> PlayerBox | None:
        """返回模拟玩家 Box；未知玩家返回 None。"""
        if player_id in ("mock-player", "player-a"):
            characters = [
                Character(name="示例角色 A", level=30),
                Character(name="示例角色 B", level=10),
            ]
        elif player_id == "player-b":
            characters = [Character(name="示例角色 C", level=20)]
        elif player_id == "player-empty":
            characters = []
        else:
            return None
        return PlayerBox(player_id=player_id, characters=characters)
