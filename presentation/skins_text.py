from ..domain.models import PlayerBox


def render_skins_text(box: PlayerBox) -> str:
    """展示拥有的皮肤与当前装扮，保留未知状态和传入顺序。"""
    lines = ["重返未来：1999 皮肤（模拟数据）", f"玩家：{box.player_id}"]
    for character in box.characters:
        lines.append("")
        lines.append(character.info.name)
        skins = character.owned_skins
        equipped_skin = character.equipped_skin
        current_listed = False
        if skins is None:
            lines.append("皮肤拥有信息未知。")
        elif not skins:
            lines.append("暂无皮肤记录。")
        else:
            for skin in skins:
                is_current = (
                    equipped_skin is not None
                    and skin.skin_id == equipped_skin.skin_id
                    and skin.character_id == equipped_skin.character_id
                )
                marker = "【当前使用】" if is_current else ""
                lines.append(f"• {skin.name}{marker}")
                current_listed = current_listed or is_current
        if equipped_skin is None:
            lines.append("当前皮肤：未知")
        elif not current_listed:
            lines.append(f"当前使用：{equipped_skin.name}（未列入上述拥有列表）")
    if not box.characters:
        lines.append("暂无角色。")
    return "\n".join(lines)
