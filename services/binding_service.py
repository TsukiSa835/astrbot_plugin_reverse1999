from ..domain.bindings import AccountSelection, ChatUser
from ..domain.ports import BindingStore


def validate_player_id(player_id: str) -> str:
    """仅检查输入格式，不验证游戏账号存在或归属。"""
    player_id = player_id.strip()
    if not player_id or len(player_id) > 128 or any(char.isspace() for char in player_id):
        raise ValueError("账号标识需为 1～128 个字符，且不能包含空白。")
    return player_id


class BindingService:
    """组织绑定与账号选择规则，不依赖聊天框架或数据库。"""

    def __init__(self, store: BindingStore):
        self._store = store

    async def bind(self, user: ChatUser, player_id: str) -> bool:
        return await self._store.bind(user, validate_player_id(player_id))

    async def unbind(self, user: ChatUser, player_id: str) -> bool:
        return await self._store.unbind(user, validate_player_id(player_id))

    async def list_accounts(self, user: ChatUser) -> list[str]:
        return await self._store.list_accounts(user)

    async def select_account(self, user: ChatUser, requested_id: str = "") -> AccountSelection:
        if requested_id.strip():
            return AccountSelection(validate_player_id(requested_id), [])
        accounts = await self._store.list_accounts(user)
        if len(accounts) == 1:
            return AccountSelection(accounts[0], accounts)
        return AccountSelection(None, accounts)
