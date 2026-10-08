"""绑定规则的回归测试，所有数据库均创建在临时目录。"""
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from astrbot_plugin_reverse1999.domain.bindings import ChatUser
from astrbot_plugin_reverse1999.services.binding_service import BindingService
from astrbot_plugin_reverse1999.storage.sqlite_bindings import SQLiteBindingStore


class BindingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "bindings.sqlite3"
        self.store = SQLiteBindingStore(self.path)
        self.service = BindingService(self.store)
        self.user = ChatUser("aiocqhttp", "10001")

    async def test_multiple_users_can_bind_same_account(self):
        other = ChatUser("aiocqhttp", "10002")
        self.assertTrue(await self.service.bind(self.user, "player-a"))
        self.assertFalse(await self.service.bind(self.user, "player-a"))
        self.assertTrue(await self.service.bind(other, "player-a"))
        await self.service.bind(self.user, "player-b")
        self.assertEqual(await self.service.list_accounts(self.user), ["player-a", "player-b"])
        self.assertTrue(await self.service.unbind(self.user, "player-a"))
        self.assertFalse(await self.service.unbind(self.user, "player-a"))
        self.assertEqual(await self.service.list_accounts(other), ["player-a"])

    async def test_platforms_are_separate(self):
        await self.service.bind(self.user, "player-a")
        self.assertEqual(await self.service.list_accounts(ChatUser("other", "10001")), [])

    async def test_persistence_after_reopening(self):
        await self.service.bind(self.user, "player-a")
        reopened = BindingService(SQLiteBindingStore(self.path))
        self.assertEqual(await reopened.list_accounts(self.user), ["player-a"])
        await reopened.unbind(self.user, "player-a")
        self.assertEqual(await self.service.list_accounts(self.user), [])

    async def test_selection_requires_choice_every_time(self):
        empty = await self.service.select_account(self.user)
        self.assertIsNone(empty.player_id)
        self.assertEqual(empty.candidates, [])
        await self.service.bind(self.user, "player-a")
        self.assertEqual((await self.service.select_account(self.user)).player_id, "player-a")
        await self.service.bind(self.user, "player-b")
        multiple = await self.service.select_account(self.user)
        self.assertIsNone(multiple.player_id)
        self.assertEqual(multiple.candidates, ["player-a", "player-b"])
        self.assertEqual((await self.service.select_account(self.user, "player-b")).player_id, "player-b")
        self.assertIsNone((await self.service.select_account(self.user)).player_id)

    async def test_explicit_query_does_not_create_binding(self):
        result = await self.service.select_account(self.user, "player-a")
        self.assertEqual(result.player_id, "player-a")
        self.assertEqual(await self.service.list_accounts(self.user), [])

    async def test_concurrent_updates_do_not_lose_accounts(self):
        services = [self.service, BindingService(SQLiteBindingStore(self.path))]
        await asyncio.gather(*(services[i % 2].bind(self.user, f"account-{i}") for i in range(12)))
        self.assertEqual(len(await self.service.list_accounts(self.user)), 12)
        inserted = await asyncio.gather(*(services[i % 2].bind(self.user, "shared") for i in range(8)))
        self.assertEqual(sum(inserted), 1)

    async def test_validation_and_parameterized_storage(self):
        for invalid in ("", "   ", "two accounts", "a" * 129):
            with self.assertRaises(ValueError):
                await self.service.bind(self.user, invalid)
        await self.service.bind(self.user, " player-a ")
        self.assertEqual(await self.service.list_accounts(self.user), ["player-a"])
        unusual = "uid');--"
        await self.service.bind(self.user, unusual)
        self.assertIn(unusual, await self.service.list_accounts(self.user))
        await self.service.unbind(self.user, unusual)
        self.assertEqual(await self.service.list_accounts(self.user), ["player-a"])


if __name__ == "__main__":
    unittest.main()
