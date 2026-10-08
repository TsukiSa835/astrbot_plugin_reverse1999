from dataclasses import dataclass
from typing import List


@dataclass
class CharacterInfo:
    """角色基础资料，与玩家的养成进度无关。"""

    character_id: str
    name: str
    rarity: int | None = None
    # None 表示未知；元组允许双灵感角色，例如 ("星", "岩")。
    afflatus: tuple[str, ...] | None = None


@dataclass
class ResonancePattern:
    """当前共鸣配置，包括默认配置；标识由数据源映射。"""

    pattern_id: str
    name: str


@dataclass
class Psychube:
    """当前心相及其养成信息。"""

    psychube_id: str
    name: str
    level: int | None = None
    amplification: int | None = None


@dataclass
class PsychubeSlot:
    """已获取到的心相栏；psychube 为 None 表示确认未装备。"""

    psychube: Psychube | None = None


@dataclass
class SkinInfo:
    """皮肤基础资料；character_id 表示所属角色。"""

    skin_id: str
    name: str
    character_id: str


@dataclass
class Character:
    """玩家角色状态；None 表示未获取到，trust 使用百分数（如 25.5）。"""

    info: CharacterInfo
    level: int | None = None
    insight: int | None = None
    resonance_level: int | None = None
    portray_level: int | None = None
    trust: float | None = None
    is_favorite: bool | None = None
    resonance_pattern: ResonancePattern | None = None
    equipped_psychube: PsychubeSlot | None = None
    equipped_skin: SkinInfo | None = None
    # None 表示拥有列表未知；空列表表示已获取但结果为空。
    owned_skins: List[SkinInfo] | None = None


@dataclass
class PlayerBox:
    """一个玩家的角色集合。"""

    player_id: str
    characters: List[Character]
