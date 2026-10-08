from ..domain.models import PlayerBox


def render_box_text(box: PlayerBox) -> str:
    """将模拟玩家 Box 排版为文本，保留传入的角色顺序和数据。"""
    lines = ["重返未来：1999 Box（模拟数据）", f"玩家：{box.player_id}"]
    for character in box.characters:
        favorite = {True: "已置顶", False: "未置顶", None: "置顶状态未知"}[character.is_favorite]
        rarity = f"{character.info.rarity}星" if character.info.rarity is not None else "星级未知"
        lines.append(f"{character.info.name}｜{rarity}｜{favorite}")
        equipped_skin = character.equipped_skin
        lines.append(f"当前皮肤：{equipped_skin.name if equipped_skin is not None else '未知'}")
        fields = [
            ("等级", character.level),
            ("洞悉", character.insight),
            ("共鸣", character.resonance_level),
            ("塑造", character.portray_level),
        ]
        details = []
        for label, value in fields:
            details.append(f"{label}：{value if value is not None else '未知'}")
        trust = f"{character.trust:g}%" if character.trust is not None else "未知"
        details.append(f"信任度：{trust}")
        lines.append("｜".join(details))
        if character.resonance_level is not None and character.resonance_level >= 10:
            pattern = character.resonance_pattern
            lines.append(f"调频：{pattern.name if pattern is not None else '未知'}")
        slot = character.equipped_psychube
        if slot is None:
            lines.append("心相：未知")
        elif slot.psychube is None:
            lines.append("心相：未装备")
        else:
            psychube = slot.psychube
            level = psychube.level if psychube.level is not None else "未知"
            amplification = psychube.amplification if psychube.amplification is not None else "未知"
            lines.append(f"心相：{psychube.name}｜等级：{level}｜增幅：{amplification}")
    if not box.characters:
        lines.append("暂无角色。")
    return "\n".join(lines)
