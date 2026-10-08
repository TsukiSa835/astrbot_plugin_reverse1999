import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path

from ..domain.bindings import ChatUser


class SQLiteBindingStore:
    """以平台、用户号、游戏账号的组合保存绑定，允许多对多关联。"""

    def __init__(self, path: Path):
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._execute(
            "CREATE TABLE IF NOT EXISTS account_bindings ("
            "platform TEXT NOT NULL, user_id TEXT NOT NULL, player_id TEXT NOT NULL, "
            "PRIMARY KEY (platform, user_id, player_id))",
            (),
        )

    def _execute(self, sql: str, parameters: tuple) -> tuple[list[tuple], int]:
        with closing(sqlite3.connect(self._path, timeout=10)) as connection:
            with connection:
                cursor = connection.execute(sql, parameters)
                return cursor.fetchall(), cursor.rowcount

    async def list_accounts(self, user: ChatUser) -> list[str]:
        rows, _ = await asyncio.to_thread(
            self._execute,
            "SELECT player_id FROM account_bindings "
            "WHERE platform = ? AND user_id = ? ORDER BY player_id",
            (user.platform, user.user_id),
        )
        return [row[0] for row in rows]

    async def bind(self, user: ChatUser, player_id: str) -> bool:
        _, changed = await asyncio.to_thread(
            self._execute,
            "INSERT INTO account_bindings (platform, user_id, player_id) "
            "VALUES (?, ?, ?) ON CONFLICT(platform, user_id, player_id) DO NOTHING",
            (user.platform, user.user_id, player_id),
        )
        return changed == 1

    async def unbind(self, user: ChatUser, player_id: str) -> bool:
        _, changed = await asyncio.to_thread(
            self._execute,
            "DELETE FROM account_bindings "
            "WHERE platform = ? AND user_id = ? AND player_id = ?",
            (user.platform, user.user_id, player_id),
        )
        return changed == 1
