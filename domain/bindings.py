from dataclasses import dataclass


@dataclass(frozen=True)
class ChatUser:
    """聊天用户身份；不包含群号、会话或机器人实例。"""

    platform: str
    user_id: str


@dataclass
class AccountSelection:
    """本次查询的账号；未选定时由 candidates 提供可选绑定。"""

    player_id: str | None
    candidates: list[str]
