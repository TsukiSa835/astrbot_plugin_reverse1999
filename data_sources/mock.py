from ..domain.models import (
    Character,
    CharacterInfo,
    PlayerBox,
    Psychube,
    PsychubeSlot,
    ResonancePattern,
    SkinInfo,
)


class MockBoxDataSource:
    """提供模拟 Box，供开发阶段验证流程。"""

    async def get_box(self, player_id: str) -> PlayerBox | None:
        """返回模拟玩家 Box；未知玩家返回 None。"""
        if player_id in ("mock-player", "player-a"):
            skin_a_default = SkinInfo(skin_id="mock-a-default", name="默认外观", character_id="mock-a")
            skin_a_selected = SkinInfo(skin_id="mock-a-skin-1", name="示例皮肤 A", character_id="mock-a")
            skin_b_default = SkinInfo(skin_id="mock-b-default", name="默认外观", character_id="mock-b")
            characters = [
                Character(
                    info=CharacterInfo(character_id="mock-a", name="示例角色 A", rarity=6),
                    level=30,
                    insight=2,
                    resonance_level=10,
                    portray_level=0,
                    trust=25.5,
                    is_favorite=False,
                    equipped_skin=skin_a_selected,
                    owned_skins=[skin_a_default, skin_a_selected],
                    resonance_pattern=ResonancePattern(pattern_id="mock-pattern-a", name="示例调频 A"),
                    equipped_psychube=PsychubeSlot(
                        psychube=Psychube(
                            psychube_id="mock-psychube-a",
                            name="示例心相 A",
                            level=40,
                            amplification=1,
                        ),
                    ),
                ),
                Character(
                    info=CharacterInfo(character_id="mock-b", name="示例角色 B", rarity=5),
                    level=10,
                    insight=0,
                    resonance_level=1,
                    portray_level=2,
                    trust=0.0,
                    is_favorite=True,
                    equipped_skin=skin_b_default,
                    owned_skins=[skin_b_default],
                    equipped_psychube=PsychubeSlot(),
                ),
            ]
        elif player_id == "player-b":
            characters = [
                Character(
                    info=CharacterInfo(character_id="mock-c", name="示例角色 C", rarity=4),
                    level=20,
                    resonance_level=10,
                    resonance_pattern=ResonancePattern(pattern_id="default", name="默认配置"),
                ),
            ]
        elif player_id == "player-empty":
            characters = []
        else:
            return None
        return PlayerBox(player_id=player_id, characters=characters)
