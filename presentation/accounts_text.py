def render_account_selection(accounts: list[str], command: str) -> str:
    """提供本次查询的选择指令，不记录默认账号。"""
    if not accounts:
        return "你还没有绑定账号。请发送 /1999绑定 UID；当前可用 player-a 等模拟标识测试。"
    lines = ["你绑定了多个账号，本次要查询哪个？请发送对应指令："]
    lines.extend(f"/{command} {player_id}" for player_id in accounts)
    return "\n".join(lines)


def render_bound_accounts(accounts: list[str]) -> str:
    if not accounts:
        return "你还没有绑定账号。请发送 /1999绑定 UID。"
    return "已绑定账号：\n" + "\n".join(f"• {player_id}" for player_id in accounts)
