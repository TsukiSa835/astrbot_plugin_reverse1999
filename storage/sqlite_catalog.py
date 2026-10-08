"""图鉴的只读查询适配器；建库由独立导入工具完成。"""
import asyncio
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from ..domain.catalog import CatalogCharacter, CatalogSkin, StaticImage
from ..domain.models import CharacterInfo, SkinInfo


class SQLiteCatalog:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _query(self, sql: str, values: tuple):
        # mode=ro：路径错误时直接报错，不能悄悄创建一个空数据库。
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            return db.execute(sql, values).fetchone()

    async def get_character(self, character_id: str) -> CatalogCharacter | None:
        row = await asyncio.to_thread(
            self._query, "SELECT * FROM characters WHERE character_id=?", (character_id,)
        )
        if row is None:
            return None
        afflatus = json.loads(row["afflatus_json"])
        return CatalogCharacter(
            CharacterInfo(row["character_id"], row["name"], row["rarity"],
                          None if afflatus is None else tuple(afflatus)),
            row["name_en"], row["default_skin_id"],
        )

    async def get_skin(self, character_id: str, skin_id: str) -> CatalogSkin | None:
        row = await asyncio.to_thread(
            self._query, "SELECT * FROM skins WHERE character_id=? AND skin_id=?",
            (character_id, skin_id),
        )
        if row is None:
            return None
        return CatalogSkin(SkinInfo(row["skin_id"], row["name"], row["character_id"]),
                           row["description"])

    async def get_image(self, character_id: str, skin_id: str,
                        kind: str = "portrait") -> StaticImage | None:
        # 同时检查角色归属，不能把别人的默认皮肤当成这个角色的图。
        row = await asyncio.to_thread(
            self._query,
            "SELECT i.* FROM images i JOIN skins s USING(skin_id) "
            "WHERE s.character_id=? AND i.skin_id=? AND i.kind=?",
            (character_id, skin_id, kind),
        )
        return StaticImage(**dict(row)) if row else None
