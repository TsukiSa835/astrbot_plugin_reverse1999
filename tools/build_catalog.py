"""把已下载的公共资料和静态图片导入独立图鉴库；不会联网。"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from PIL import Image


# 数据源的 career 编号只在适配边界出现，domain 使用中文灵感名称。
AFFLATUS = {1: ("岩",), 2: ("星",), 3: ("木",), 4: ("兽",),
            5: ("灵",), 6: ("智",), 101: ("星", "岩")}
# 仅选择已检查过的完整静态图；动画贴图、模糊大背景不能混入。
IMAGE_DIRS = {"portrait": "singlebg/headicon_img",
              "icon": "singlebg/headicon_middle",
              "skin_preview": "singlebg/headskinicon_middle"}
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS catalog_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS characters (character_id TEXT PRIMARY KEY, "
    "name TEXT NOT NULL, name_en TEXT NOT NULL, rarity INTEGER CHECK(rarity BETWEEN 2 AND 6), "
    "afflatus_json TEXT NOT NULL, default_skin_id TEXT, raw_mapping TEXT NOT NULL, "
    "raw_attributes TEXT)",
    "CREATE TABLE IF NOT EXISTS skins (skin_id TEXT PRIMARY KEY, character_id TEXT NOT NULL "
    "REFERENCES characters(character_id), name TEXT NOT NULL, description TEXT NOT NULL, "
    "raw_mapping TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS images (skin_id TEXT NOT NULL REFERENCES skins(skin_id), "
    "kind TEXT NOT NULL, relative_path TEXT NOT NULL, width INTEGER NOT NULL, "
    "height INTEGER NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(skin_id, kind))",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def unique_rows(rows, key):
    result = {}
    for row in rows:
        value = str(row[key])
        if not value.isdecimal() or value in result:
            raise ValueError(f"重复或非法 {key}: {value}")
        result[value] = row
    return result


def build_catalog(root: Path, attributes: Path, roster: Path,
                  provenance: Path, database: Path, overrides: Path | None = None) -> dict:
    """先检查全部输入，再在一个事务内替换图鉴；失败保留上次成功数据。"""
    root = root.resolve()
    mapping_path = root / "mappings/ArcanistMap.json"
    mapping = unique_rows(read_json(mapping_path), "id")
    attrs = read_json(attributes)
    roster_rows = unique_rows(read_json(roster), "baseId")
    sources = read_json(provenance)
    inputs = {"mapping": mapping_path, "attributes": attributes, "roster": roster}
    for label, path in inputs.items():
        if digest(path) != sources[label]["sha256"]:
            raise ValueError(f"{label} 的校验和与来源记录不符")
    if not mapping or not attrs:
        raise ValueError("角色资料为空，拒绝覆盖已有图鉴")
    for key, value in attrs.items():
        if str(value["id"]) != key:
            raise ValueError(f"角色属性 ID 不一致: {key}")
    review = read_json(overrides) if overrides else {}
    if review and review.get("version") != 1:
        raise ValueError("不支持此人工核对版本")
    known_skins = {str(s["id"]): cid for cid, c in mapping.items() for s in c.get("live2d", [])}
    image_rules = {}
    classified = {}
    ignored = {}
    for entry in review.get("images", []):
        key = (entry["skin_id"], entry["kind"])
        if known_skins.get(entry["skin_id"]) != entry["character_id"] or key in image_rules:
            raise ValueError("人工图片映射归属错误或重复")
        if entry["kind"] not in {*IMAGE_DIRS, "portrait_variant", "portrait_decoration_1", "portrait_decoration_2"}:
            raise ValueError("未知图片用途")
        image_rules[key] = entry["path"]
    for entry in review.get("classified_images", []):
        if entry["path"] in classified:
            raise ValueError("重复的图片分类")
        classified[entry["path"]] = entry
    for relative in [*image_rules.values(), *classified]:
        file = root / relative
        if Path(relative).is_absolute() or not file.resolve().is_relative_to(root) or not file.is_file():
            raise ValueError(f"人工核对路径非法或文件不存在: {relative}")
    if set(image_rules.values()) & set(classified):
        raise ValueError("同一文件不能既作为皮肤展示又被分类排除")
    for entry in review.get("ignored_missing", []):
        if known_skins.get(entry["skin_id"]) != entry["character_id"] or entry["skin_id"] in ignored:
            raise ValueError("忽略项归属错误或重复")
        ignored[entry["skin_id"]] = entry
    if overrides:
        sources["manual_review"] = {"sha256": digest(overrides), "decisions": review}
    # 属性表存在、但美术映射没有的角色也入库，同时报告图片缺口。
    all_ids = sorted(set(mapping) | set(attrs), key=int)
    characters, skins, images = [], [], []
    seen_skins = set()
    report = {"missing_attributes": [], "unknown_careers": [],
              "missing_mapping": [], "missing_default": [],
              "missing_portraits": [], "invalid_images": [], "unmapped_images": {},
              "ignored_missing_portraits": [], "classified_images": list(classified.values())}
    for cid in all_ids:
        source = mapping.get(cid, {})
        attr = attrs.get(cid)
        known = roster_rows.get(cid, {})
        name = source.get("name") or attr["name"]["zh"]
        rarity, afflatus = None, None
        if attr is None:
            report["missing_attributes"].append({"id": cid, "name": name})
        else:
            rarity = attr["rarity"]
            if type(rarity) is not int or not 2 <= rarity <= 6:
                raise ValueError(f"稀有度非法: {cid}")
            if known.get("rarity") not in (None, rarity):
                raise ValueError(f"两个来源的稀有度冲突: {cid}")
            afflatus = AFFLATUS.get(attr["career"])
            if afflatus is None:
                report["unknown_careers"].append({"id": cid, "career": attr["career"]})
        if not source:
            report["missing_mapping"].append(cid)
        local_skins = unique_rows(source.get("live2d", []), "id")
        defaults = [sid for sid, skin in local_skins.items() if skin.get("des") == "初始皮肤"]
        roster_default = known.get("defaultVariant")
        if roster_default in local_skins:
            defaults.append(roster_default)
        defaults = set(defaults)
        if len(defaults) > 1:
            raise ValueError(f"默认皮肤来源冲突: {cid}")
        default = next(iter(defaults), None)
        if default is None:
            report["missing_default"].append(cid)
        characters.append((cid, name, source.get("nameEng") or (attr["name"]["en"] if attr else ""),
                           rarity, json_text(afflatus), default, json_text(source),
                           json_text(attr)))
        for sid, skin in local_skins.items():
            if sid in seen_skins:
                raise ValueError(f"皮肤被多个角色引用: {sid}")
            seen_skins.add(sid)
            skins.append((sid, cid, skin.get("characterSkin") or skin["name"],
                          skin.get("skinDescription", ""), json_text(skin)))
            has_portrait = False
            candidates = {kind: f"{folder}/{sid}.png" for kind, folder in IMAGE_DIRS.items()}
            candidates.update({kind: path for (skin_id, kind), path in image_rules.items() if skin_id == sid})
            for kind, relative in candidates.items():
                file = root / relative
                if not file.is_file():
                    continue
                if not file.resolve().is_relative_to(root):
                    raise ValueError(f"图片路径越出资源目录: {relative}")
                try:
                    with Image.open(file) as image:
                        width, height = image.size
                        image.load()  # 真正解码，不能仅凭扩展名和文件头入库。
                        if image.format != "PNG":
                            raise ValueError("文件格式不是 PNG")
                    images.append((sid, kind, relative, width, height, digest(file)))
                    has_portrait |= kind == "portrait"
                except (OSError, ValueError) as error:
                    report["invalid_images"].append({"path": relative, "error": str(error)})
            if not has_portrait:
                if sid in ignored:
                    report["ignored_missing_portraits"].append(ignored[sid])
                else:
                    report["missing_portraits"].append({"character_id": cid, "skin_id": sid})
    indexed_paths = {row[2] for row in images}
    for kind, folder in IMAGE_DIRS.items():
        report["unmapped_images"][kind] = sorted(
            p.relative_to(root).as_posix() for p in (root / folder).glob("*.png")
            if p.relative_to(root).as_posix() not in indexed_paths
            and p.relative_to(root).as_posix() not in classified)
    report.update(characters=len(characters), skins=len(skins), images=len(images),
                  with_attributes=sum(row[3] is not None for row in characters))
    metadata = {"schema_version": "1", "sources": json_text(sources),
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "report": json_text(report)}
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        existing = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if existing - {"catalog_meta", "characters", "skins", "images"}:
            raise ValueError("目标含其他业务表，拒绝作为图鉴库使用")
        if existing:
            version = db.execute("SELECT value FROM catalog_meta WHERE key='schema_version'").fetchone()
            if not version or version[0] != "1":
                raise ValueError("不支持此图鉴结构版本")
        # 显式 BEGIN 让建表和数据替换一同回滚。
        db.execute("BEGIN IMMEDIATE")
        with db:
            for statement in SCHEMA:
                db.execute(statement)
            for table in ("images", "skins", "characters", "catalog_meta"):
                db.execute(f"DELETE FROM {table}")  # 表名来自固定元组，不来自输入。
            db.executemany("INSERT INTO characters VALUES (?,?,?,?,?,?,?,?)", characters)
            db.executemany("INSERT INTO skins VALUES (?,?,?,?,?)", skins)
            db.executemany("INSERT INTO images VALUES (?,?,?,?,?,?)", images)
            db.executemany("INSERT INTO catalog_meta VALUES (?,?)", metadata.items())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "attributes", "roster", "provenance", "database"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--overrides", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data/catalog_overrides.json")
    args = parser.parse_args()
    report = build_catalog(**vars(args))
    # 完整缺口报告保存在数据库 catalog_meta 中。
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
