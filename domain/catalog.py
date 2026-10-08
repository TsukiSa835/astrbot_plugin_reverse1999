"""公共图鉴的数据结构，不依赖 AstrBot、SQLite 或本地磁盘。"""
from dataclasses import dataclass

from .models import CharacterInfo, SkinInfo


@dataclass(frozen=True)
class CatalogCharacter:
    info: CharacterInfo
    name_en: str
    default_skin_id: str | None


@dataclass(frozen=True)
class StaticImage:
    skin_id: str
    kind: str
    relative_path: str  # 相对于资源根目录，迁移磁盘无需改业务模型。
    width: int
    height: int
    sha256: str


@dataclass(frozen=True)
class CatalogSkin:
    info: SkinInfo
    description: str
