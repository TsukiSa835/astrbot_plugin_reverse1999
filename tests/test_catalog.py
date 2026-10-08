"""用微型资料和图片测试导入及查询，不依赖外网或真实资源目录。"""
import asyncio
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from astrbot_plugin_reverse1999.storage.sqlite_catalog import SQLiteCatalog
from astrbot_plugin_reverse1999.tools.build_catalog import build_catalog, digest


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mapping = [{"id": 3003, "name": "槲寄生", "nameEng": "Druvis III",
                         "live2d": [{"id": 300301, "name": "初始皮肤", "des": "初始皮肤"}]}]
        self.attributes = {"3003": {"id": 3003, "name": {"zh": "槲寄生", "en": "Druvis III"},
                                     "rarity": 6, "career": 3}}
        self.roster = [{"baseId": 3003, "rarity": 6, "defaultVariant": "300301"}]
        self.paths = {"mapping": self.root / "mappings/ArcanistMap.json",
                      "attributes": self.root / "attributes.json", "roster": self.root / "roster.json"}
        self.provenance = self.root / "provenance.json"
        self.database = self.root / "catalog.sqlite3"
        self.image = self.root / "singlebg/headicon_img/300301.png"
        self.image.parent.mkdir(parents=True)
        Image.new("RGBA", (8, 12), (255, 0, 0, 255)).save(self.image)
        self.save_inputs()

    def save_inputs(self):
        for label, path in self.paths.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(getattr(self, label)), "utf8")
        self.provenance.write_text(json.dumps({
            label: {"sha256": digest(path)} for label, path in self.paths.items()}), "utf8")

    def build(self):
        return build_catalog(self.root, self.paths["attributes"], self.paths["roster"],
                             self.provenance, self.database)

    def test_import_repeat_and_queries(self):
        first = self.build()
        self.assertEqual(first, self.build())
        self.assertEqual((first["characters"], first["skins"], first["images"]), (1, 1, 1))
        store = SQLiteCatalog(self.database)
        char = asyncio.run(store.get_character("3003"))
        self.assertEqual((char.info.rarity, char.info.afflatus), (6, ("木",)))
        self.assertEqual(char.default_skin_id, "300301")
        image = asyncio.run(store.get_image("3003", "300301"))
        self.assertEqual((image.width, image.height), (8, 12))
        self.assertEqual(image.sha256, hashlib.sha256(self.image.read_bytes()).hexdigest())
        self.assertIsNone(asyncio.run(store.get_image("9999", "300301")))
        self.assertIsNone(asyncio.run(store.get_skin("9999", "300301")))
        self.assertIsNone(asyncio.run(store.get_character("missing")))

    def test_dual_and_unknown_afflatus(self):
        self.attributes["3003"]["career"] = 101
        self.save_inputs(); self.build()
        store = SQLiteCatalog(self.database)
        self.assertEqual(asyncio.run(store.get_character("3003")).info.afflatus, ("星", "岩"))
        self.attributes["3003"]["career"] = 999
        self.save_inputs()
        self.assertTrue(self.build()["unknown_careers"])
        self.assertIsNone(asyncio.run(store.get_character("3003")).info.afflatus)

    def test_missing_attributes_not_invented(self):
        self.mapping.append({"id": 9998, "name": "?", "nameEng": "?", "live2d": []})
        self.save_inputs()
        report = self.build()
        self.assertEqual(report["with_attributes"], 1)
        unknown = asyncio.run(SQLiteCatalog(self.database).get_character("9998"))
        self.assertIsNone(unknown.info.rarity)
        self.assertIsNone(unknown.info.afflatus)

    def test_corrupt_image_reported_without_fake_path(self):
        self.image.write_bytes(b"not a png")
        report = self.build()
        self.assertEqual(report["images"], 0)
        self.assertEqual(len(report["invalid_images"]), 1)
        self.assertEqual(len(report["missing_portraits"]), 1)

    def test_bad_input_preserves_previous_database(self):
        self.build()
        before = self.database.read_bytes()
        self.mapping.append(self.mapping[0])
        self.save_inputs()
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(self.database.read_bytes(), before)

    def test_failed_insert_rolls_back_deleted_rows(self):
        self.build()
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("CREATE TRIGGER stop BEFORE INSERT ON skins BEGIN SELECT RAISE(ABORT, 'test'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.build()
        char = asyncio.run(SQLiteCatalog(self.database).get_character("3003"))
        self.assertEqual(char.info.name, "槲寄生")
        self.assertIsNotNone(asyncio.run(SQLiteCatalog(self.database).get_image("3003", "300301")))

    def test_refuses_other_database_and_changed_snapshot(self):
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("CREATE TABLE bindings (id TEXT)")
        with self.assertRaises(ValueError):
            self.build()
        self.paths["attributes"].write_text("{}", "utf8")
        with self.assertRaises(ValueError):
            self.build()

    def test_review_overrides_and_classifications(self):
        extra = self.image.with_name("300301_3.png")
        Image.new("RGBA", (4, 6)).save(extra)
        review = {"version": 1, "images": [
            {"character_id": "3003", "skin_id": "300301", "kind": "portrait",
             "path": "singlebg/headicon_img/300301_3.png"}],
            "classified_images": [{"path": "singlebg/headicon_img/300301.png", "category": "composite_art"}]}
        path = self.root / "review.json"
        path.write_text(json.dumps(review), "utf8")
        report = build_catalog(self.root, self.paths["attributes"], self.paths["roster"],
                               self.provenance, self.database, path)
        result = asyncio.run(SQLiteCatalog(self.database).get_image("3003", "300301"))
        self.assertEqual(result.relative_path, "singlebg/headicon_img/300301_3.png")
        self.assertEqual(report["unmapped_images"]["portrait"], [])
        review["images"][0]["character_id"] = "9998"
        path.write_text(json.dumps(review), "utf8")
        with self.assertRaises(ValueError):
            build_catalog(self.root, self.paths["attributes"], self.paths["roster"],
                          self.provenance, self.database, path)

    def test_ignored_missing_preserves_skin(self):
        self.image.unlink()
        path = self.root / "review.json"
        path.write_text(json.dumps({"version": 1, "ignored_missing": [
            {"character_id": "3003", "skin_id": "300301", "reason": "暂忽略"}]}), "utf8")
        report = build_catalog(self.root, self.paths["attributes"], self.paths["roster"],
                               self.provenance, self.database, path)
        self.assertEqual(report["missing_portraits"], [])
        self.assertEqual(len(report["ignored_missing_portraits"]), 1)
        self.assertIsNotNone(asyncio.run(SQLiteCatalog(self.database).get_skin("3003", "300301")))

    def test_rarity_conflict_fails(self):
        self.roster[0]["rarity"] = 5
        self.save_inputs()
        with self.assertRaises(ValueError):
            self.build()


if __name__ == "__main__":
    unittest.main()
