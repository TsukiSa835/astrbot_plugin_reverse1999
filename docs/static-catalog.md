# 静态图片索引：第一步

这一层保存大家共用的角色资料和静态图片索引。它不保存玩家拥有谁、穿什么皮肤、角色练到多少级；这些仍然属于 PlayerBox。

## 文件与依赖方向

| 文件 | 负责什么 | 设计原因 |
| --- | --- | --- |
| `domain/models.py` | CharacterInfo 新增 afflatus | 灵感是角色基础资料，允许多种灵感和未知状态 |
| `domain/catalog.py` | 图鉴角色、皮肤和静态图片的数据结构 | 只描述业务数据，不知道 QQ、SQLite 和 D 盘 |
| `domain/ports.py` | CharacterCatalog 查询约定 | 以后业务依赖约定，可以替换存储实现 |
| `storage/sqlite_catalog.py` | 用 SQLite 实现查询约定 | SQL、线程和连接管理都留在外层 |
| `tools/build_catalog.py` | 离线导入资料、检查图片、记录来源 | 外部 JSON 字段最容易变，把转换逻辑集中到这里 |
| `tests/test_catalog.py` | 导入失败、重复导入、角色归属等回归测试 | 这些边界不能只靠一次成功导入判断 |

依赖方向：导入工具/存储实现 → domain；以后 Box 渲染服务 → CharacterCatalog 约定。domain 不反过来导入数据库或插件入口。

这次没有接入 `/1999box` 的图片发送。已有模拟 Box 使用 mock-a 等测试 ID，不能偷偷替换成真实角色。下一步可以在单独的渲染测试中用真实图鉴 ID，再将渲染结果接到 Box。

## 先看模型中的几行

```python
afflatus: tuple[str, ...] | None = None
```

- `afflatus` 表示灵感。
- `tuple[str, ...]` 表示多个字符串组成的不可变序列，如 `("木",)` 或 `("星", "岩")`。
- `| None` 表示允许“没有获取到”，不能用空字符串伪装成已知数据。
- `= None` 提供默认值，因此旧的 mock 角色构造方式仍然有效。

`CatalogCharacter.info` 复用现有 CharacterInfo，而不是再定义一套姓名、星级字段。`default_skin_id` 保存能够从资料核对到的默认皮肤；不能核对时是 None。

`StaticImage.relative_path` 是例如 `singlebg/headicon_img/300301.png` 的相对路径。它不保存 `D:\...`，换服务器时只需要在使用图片的外层换资源根目录。`width`、`height` 可用于排版；`sha256` 用于识别文件内容版本，不代表每次查询都重新校验文件。

`@dataclass(frozen=True)` 为这些记录自动生成初始化方法，并阻止给字段重新赋值。注意嵌套的旧 CharacterInfo 本身仍是可变对象，这不是深度不可变。

## 查询代码的关键逻辑

`asyncio.to_thread(...)` 把同步 SQLite 查询放到线程执行，避免阻塞 Bot 的事件循环。每次查询新建并关闭连接，不把同一 SQLite 连接跨线程共享。

`mode=ro` 以只读方式打开数据库。路径拼错时会报错，不能自动创建一个空库后让人误以为角色不存在。

查询图片同时传 `character_id` 和 `skin_id`。SQL 通过 skins 表确认归属，再返回图片；不能只拿一个皮肤 ID 就假定它属于当前角色。SQL 的 `?` 占位符绑定参数，用户输入不会拼进 SQL 语句。

查不到记录返回 None，表示图鉴中没有匹配记录。数据库本身打不开则抛出异常，两种情况不能混为一谈。

## 导入过程

1. 读取美术映射、角色属性、补充图鉴与来源记录；校验 SHA-256，确认文件与记录的快照一致。
2. 按角色 ID 合并，绝不按名字模糊配对。属性表有但素材映射没有的角色也入库，并报告缺口。
3. 稀有度使用数据源已转换好的 2–6 星，不能再加 1。两个来源的稀有度冲突时停止导入。
4. 在导入边界把 `career` 编号转换为灵感：1 岩、2 星、3 木、4 兽、5 灵、6 智、101 星与岩。未知编号保留原始记录、报告缺口，展示字段暂为空。
5. 默认皮肤来自映射中的“初始皮肤”标签或补充图鉴的明确默认字段；两个来源冲突时停止。没有证据时不自行取列表第一项。
6. 按精确 skin ID 查找静态图片，并实际解码检查、读取尺寸和计算校验值。不会把动画图集当成整张立绘，也不自动采用模糊的大背景图。
7. 所有准备结束后，在一个数据库事务内替换旧图鉴。删除和插入是一体的：任何一步失败，旧数据回滚保留。

`catalog_meta` 保存结构版本、导入时间、来源版本/校验值和完整缺口报告。原始角色映射、属性与皮肤映射也保存，方便排查来源问题。数据库含其他业务表时拒绝导入，防止误指向绑定数据库。

事务保证数据库替换一致，但不会为以后误导入一个合法却错误的快照提供历史版本管理；重要更新前仍应备份旧图鉴。

## 本机文件位置与复现

- 资源根目录：`D:\Reverse1999Assets\sources\Reverse-1999-CN-Asset`
- 资料快照和来源：`D:\Reverse1999Assets\catalog\character-sources`
- 图鉴数据库：`D:\Astrbot\data\plugin_data\astrbot_plugin_reverse1999\catalog.sqlite3`
- 账号绑定库：同目录的 `bindings.sqlite3`，与图鉴分离。

在 PowerShell 中可重复运行：

```powershell
& 'D:\Astrbot\.venv\Scripts\python.exe' `
  'D:\Astrbot\data\plugins\astrbot_plugin_reverse1999\tools\build_catalog.py' `
  --root 'D:\Reverse1999Assets\sources\Reverse-1999-CN-Asset' `
  --attributes 'D:\Reverse1999Assets\catalog\character-sources\arcanists.json' `
  --roster 'D:\Reverse1999Assets\catalog\character-sources\characters.json' `
  --provenance 'D:\Reverse1999Assets\catalog\character-sources\provenance.json' `
  --database 'D:\Astrbot\data\plugin_data\astrbot_plugin_reverse1999\catalog.sqlite3'
```

工具本身不联网，需要 Python 3.10+ 和 Pillow。本机 AstrBot 环境已安装 Pillow。换机器需一起提供资料快照和资源包；数据库不包含图片二进制。

## 来源与范围

- 美术映射：[myssal/Reverse-1999-CN-Asset](https://github.com/myssal/Reverse-1999-CN-Asset)，固定提交 `45e75248ba3b25053fd32e63ab13c2f9f54dd9df`。
- 稀有度和灵感：[improviser1999 使用的角色数据](https://r2.balthild.com/improviser1999/arcanists.json)，来源项目 [balthild/improviser1999](https://github.com/balthild/improviser1999)。该地址会更新，本机保存下载快照、下载时间和 SHA-256；不把项目代码提交号冒充数据版本。
- 补充默认皮肤及稀有度交叉检查：[UnderLotus/r1999-roster](https://github.com/UnderLotus/r1999-roster)，固定提交 `10f0e88112bcb0286d3ddf2b6a5ef37b70951ef3`。MIT 许可原文保存在资料快照目录 `LICENSE`。
- 双灵感含义核对：[灰机 Wiki 双生舞伶](https://res1999.huijiwiki.com/wiki/双生舞伶)。

这些是社区资料快照，不是官方实时角色名册。素材中含剧情角色和未知条目，不能把入库条目数称作“当前可抽取角色数”。补充图鉴中的 isReleased 指海外服，不能用于判断国服上线状态，本次不导入该字段。

本步不加入技能。语音下载仍见 `art-resources-todo.md`；真正渲染时须执行 `image-fallback.md`：当前皮肤 → 同角色默认皮肤 → 占位图，同时给出提示，不能修改玩家实际装备状态。图片入库后仍可能被移动/损坏，渲染端必须再处理读图失败。

## 2026-10-08 本机导入结果

- 139 个角色条目；138 个具备稀有度和灵感；9998 是未核实的未知条目。
- 424 个皮肤；420 张完整立绘、422 张角色头像、214 张皮肤预览，共 1,056 个图片索引。
- 已入库图片全部可解码，无损坏图；4 个皮肤没有精确 ID 对应的完整立绘：302902（斯奈德）、30660001（37）、30880001（塞梅尔维斯）、999801（未知角色）。
- 3029（斯奈德）没有能够核对的默认皮肤标记。缺图不会借用另一个角色的素材。
- 另有 4 张立绘文件、29 张头像文件没有对应皮肤映射，已列入报告，暂不猜测归属。
- 查询样例核对：槲寄生为 6 星木，十四行诗为 5 星岩，双生舞伶为 6 星星/岩；都能查到对应默认立绘。
- 15 项测试通过（8 项图鉴、7 项账号绑定），真实数据库 integrity_check 为 ok，外键检查无错误。这不等于验证了 QQ 图片发送；本步尚未接入该功能。

人类可读角色清单：`D:\Reverse1999Assets\catalog\characters.csv`。
完整缺口报告：`D:\Reverse1999Assets\catalog\static-index-report.json`，同一报告也在数据库中。
修改前旧模型和接口备份：`D:\Reverse1999Assets\catalog\plugin-backups\20261008-172406`。

## 2026-10-08 人工辨认后的修正

依据用户逐图辨认，规则保存在 `data/catalog_overrides.json`。导入工具命令行默认加载该文件；程序调用 build_catalog 时需传 overrides 路径。原始下载映射不修改，导入记录保存完整核对规则和 SHA-256，重建数据库也不会丢失修正。

- 诗的礼赞原映射的皮肤 ID 已是 302306。302305.png 与 302306.png 是同服装、主要为视图大小差异：保留 302306 的原展示立绘，增加 `portrait_variant` 指向 302305.png。不能仅凭图片文件名把 302305 当成新的游戏皮肤 ID。用户说明此皮肤可通过实体设定集兑换码获取，已记录来源为用户说明。
- 恶之果皮肤 310003 按用户最新选择，`portrait` 使用完整组合图 310003.png。310003_1.png、310003_2.png 分别以 `portrait_decoration_1`、`portrait_decoration_2` 关联为补充装饰；310003_3.png 以 `portrait_variant` 关联为人物主体补充图。三者不替代默认展示图，也不新建皮肤。
- 302902、30660001、30880001、999801 保留皮肤记录，缺图转入 `ignored_missing_portraits`。废案/占位是用户的暂定判断，未经官方核实；以后发现对应图片仍可重新入库，不永久屏蔽。
- 29 张未映射 headicon_middle 图片按用户辨认分类为 `enemy_chibi`（敌人局内 Q 版立绘），不虚构玩家皮肤关系。其余已映射图片仍沿用旧 kind=icon 标识以保持接口兼容；这个技术名称不代表它们都是头像。
- 报告中 `unmapped_images` 现在按实际被索引的文件路径统计，且扣除已人工分类的文件；不再通过“文件名等于皮肤 ID”判断是否已处理。
- 分类与展示不能同时占用同一路径；人工映射必须指向该角色已有皮肤，路径必须位于资源目录内并且文件存在。索引和报告仍在同一数据库事务里保存。

此前的“4 张未映射立绘、29 张未映射头像、4 个待处理缺图”是修正前的历史记录。当前结果以最新数据库报告为准；检查文件夹中的原图片与旧说明保留，另附处理结果说明。

前一次修正结果为 1,057 图片索引；下方记录用户再次选择完整组合图后的最新结果。

### 最新选择：完整主图与补充图片

恶之果完整组合图已恢复为主图，三个分件收录在同一皮肤下。主图与补充图通过 kind 区分，SQLiteCatalog.get_image 默认仍只取 portrait；需要补充图时显式传对应 kind。不修改数据库结构，不将补充装饰视作独立皮肤。

完整图和分件都是已有 PNG；目前依据用户的视觉偏好选择完整图，不能据此声称它在所有 Box 布局中兼容性更好。后续实际排版时再检查缩放、裁切及人物清晰度。

最新实库验证：139 角色、424 皮肤、1,060 图片索引；仅恶之果主图及3张补充图片记录变化，其余图片和全部角色/皮肤记录与修改前一致。17项测试通过，实际查询、数据库完整性和外键检查通过。
