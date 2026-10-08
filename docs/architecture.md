# 架构与数据模型

## 实现边界

当前 Bot 流程为账号选择、模拟 Box 查询和文本展示。离线图鉴工具及 SQLite 图鉴查询已经实现，但尚未在 `main.py` 中组装；图片渲染、真实游戏数据源和跨客户端接口仍属计划。

## 模块职责

| 模块 | 职责与依赖 |
| --- | --- |
| [main.py](../main.py) | AstrBot 指令入口，识别发送者并组装服务与适配器 |
| [domain/models.py](../domain/models.py) | 公共角色资料与玩家状态模型 |
| [domain/bindings.py](../domain/bindings.py) | 平台用户身份、账号选择结果 |
| [domain/catalog.py](../domain/catalog.py) | 图鉴角色、皮肤与静态图片记录 |
| [domain/ports.py](../domain/ports.py) | `BoxDataSource`、`BindingStore`、`CharacterCatalog` 接口 |
| [services/box_service.py](../services/box_service.py) | 通过数据源查询，并对置顶状态稳定排序 |
| [services/binding_service.py](../services/binding_service.py) | 账号格式校验与多账号选择规则 |
| [presentation](../presentation) | 将业务对象排版为文本，不依赖 AstrBot 事件 |
| [data_sources/mock.py](../data_sources/mock.py) | 模拟 Box 数据源 |
| [storage](../storage) | SQLite 绑定存储与图鉴只读查询 |
| [tools/build_catalog.py](../tools/build_catalog.py) | 离线资料转换、图片校验与图鉴导入 |

业务服务依赖 domain 中的接口，由入口注入具体实现。domain 不导入 AstrBot、SQLite 或图片处理库。外部数据字段与来源格式的变化由适配层承担。

## 公共资料与玩家状态

| 对象／字段 | 语义 |
| --- | --- |
| `CharacterInfo` | 角色 ID、名称、稀有度与灵感，与玩家养成无关 |
| `afflatus` | `tuple[str, ...]` 支持单／双灵感；`None` 表示未知 |
| `SkinInfo` | 皮肤 ID、名称和所属角色 ID |
| `Character` | 一个玩家的角色养成、置顶、心相及皮肤状态 |
| `PlayerBox` | 玩家标识及角色集合；角色列表为空不等于玩家不存在 |
| `ResonancePattern` | 当前共鸣配置，包含默认配置与调频配置；标识由数据源映射 |
| `Psychube` | 心相标识、名称、等级及增幅 |
| `PsychubeSlot` | 已读取的心相栏，用于区分未装备与数据未知 |

角色状态包含等级、洞悉、共鸣等级、塑造、信任度和置顶。`trust` 使用百分数，例如 `25.5` 表示 25.5%。未知值不转为 0；零塑造、零信任度等是有效数据。

| 状态 | 含义 |
| --- | --- |
| `equipped_psychube is None` | 心相栏数据未知 |
| `equipped_psychube.psychube is None` | 已取得栏位信息，确认未装备 |
| `equipped_skin is None` | 当前装扮未知 |
| `owned_skins is None` | 拥有的皮肤列表未知 |
| `owned_skins == []` | 已取得列表，但结果为空 |
| `is_favorite is None` | 置顶状态未知 |

当前模型只表示一个心相栏，尚不支持多栏心相装备。皮肤拥有列表和当前装扮独立保存，不能相互推断。

## 当前展示规则

- `BoxService` 将 `is_favorite is True` 的角色置前；其余角色保持原相对顺序。返回新的角色列表，不修改数据源列表，也不深拷贝角色对象。
- 共鸣等级已知且不低于 10 才显示调频；达到条件但配置未知时显示“未知”。
- Box 文本展示当前皮肤；皮肤指令展示拥有列表，并按角色和皮肤 ID 标记当前装扮。当前装扮未列入拥有列表时另行显示，不修改原始数据。
- 稀有度已用于 Box 文本；灵感仅在模型和图鉴中支持，当前文本未输出。
- 查询不到玩家时返回 `None`；已知玩家无角色时返回空 `PlayerBox`。展示层保留这两种状态的差别。

## 图鉴与存储边界

`CatalogCharacter` 复用 `CharacterInfo`，并包含英文名和可空的默认皮肤 ID。`CatalogSkin` 复用 `SkinInfo`，附加描述。`StaticImage` 保存图片用途、相对路径、尺寸和 SHA-256，不保存本机资源根目录。

图鉴记录使用 `frozen=True` 限制字段重新赋值，但嵌套的 `CharacterInfo`、`SkinInfo` 仍是可变对象，不保证深度不可变。

绑定库保存聊天账号与游戏账号的关联；图鉴库保存公共资料。当前服务共用不等于游戏数据缓存，每次查询仍调用数据源。

## 后续扩展

真实数据源应实现 `BoxDataSource`，在边界完成字段转换与访问权限检查。跨平台入口应提供明确的平台身份，不将不同身份体系强行合并。网页与小程序尚未实现。

图片资源定位与渲染的最终职责划分尚未落实到代码；预期由资源适配负责文件访问，展示流程实施回退，domain 保持纯数据与接口。详细约定见[图片回退设计](image-fallback.md)。

相关规范：[账号绑定](account-bindings.md)、[静态图鉴](static-catalog.md)。
