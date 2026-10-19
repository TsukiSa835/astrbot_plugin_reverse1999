# 静态图鉴与模拟映射规范

状态：离线导入工具、SQLite 只读查询和模拟映射已实现；尚未接入 Bot 的 Box 指令。图鉴保存公共角色资料，玩家的拥有状态、养成与当前装扮由 `PlayerBox` 表示。

## 数据结构与查询接口

模型与模块依赖见[架构说明](architecture.md)。当前数据库结构版本为 `1`。

| 表 | 内容 |
| --- | --- |
| `characters` | 角色 ID、名称、英文名、稀有度、灵感、默认皮肤 ID，以及原始映射和属性记录 |
| `skins` | 皮肤 ID、所属角色、名称、描述及原始皮肤映射 |
| `images` | `(skin_id, kind)` 主键、资源相对路径、尺寸、SHA-256 |
| `catalog_meta` | 结构版本、来源记录、导入时间、完整检查报告 |

[CharacterCatalog](../domain/ports.py) 提供三个异步查询：

- `get_character(character_id)`：查询公共角色资料。
- `get_skin(character_id, skin_id)`：查询指定角色所属的皮肤。
- `get_image(character_id, skin_id, kind="portrait")`：查询指定用途的静态图片。

[SQLiteCatalog](../storage/sqlite_catalog.py) 使用参数化 SQL，通过角色归属检查防止串用皮肤。连接以 `mode=ro` 打开；数据库不存在或无法打开时抛出异常，匹配记录不存在才返回 `None`。同步查询通过 `asyncio.to_thread` 执行，每次独立打开并关闭连接。

路径相对于资源根目录，例如 `singlebg/headicon_img/300301.png`。更换部署位置无需修改 domain；资源根目录由使用图片的外层确定。查询不会重新解码或校验文件，运行时错误需由后续渲染流程处理。

## 离线导入

[build_catalog.py](../tools/build_catalog.py) 不联网，依赖 Python 3.10+ 与 Pillow。输入需预先准备：

| 参数 | 内容 |
| --- | --- |
| `--root` | 素材根目录，包含 `mappings/ArcanistMap.json` 与图片目录 |
| `--attributes` | 以角色 ID 字符串为键的属性表；记录包含 `id`、`name.zh`、`name.en`、`rarity`、`career` |
| `--roster` | 补充图鉴数组，以 `baseId` 标识角色，读取 `rarity` 和 `defaultVariant` |
| `--provenance` | 来源记录；`mapping`、`attributes`、`roster` 项须包含对应文件的 `sha256`，并应保留 URL、提交号或获取日期 |
| `--database` | 输出图鉴数据库路径；不得指向绑定库 |
| `--overrides` | 人工核对规则；命令行默认读取仓库的 `data/catalog_overrides.json` |

素材、属性快照、补充图鉴及来源记录不随仓库分发。克隆项目本身不能重现某次完整导入，必须取得匹配的输入快照；尤其不能将更新后的在线属性表继续标作旧快照。来源记录中的校验值应来自实际输入文件，不应仅为绕过校验而修改。

以下为仓库根目录下的 PowerShell 示例；将示例资源目录替换为实际位置，`python` 应指向具备 Pillow 的环境：

```powershell
python tools/build_catalog.py `
  --root 'E:/Reverse1999Assets/sources/Reverse-1999-CN-Asset' `
  --attributes 'E:/Reverse1999Assets/catalog/character-sources/arcanists.json' `
  --roster 'E:/Reverse1999Assets/catalog/character-sources/characters.json' `
  --provenance 'E:/Reverse1999Assets/catalog/character-sources/provenance.json' `
  --database 'E:/Reverse1999Assets/catalog/catalog.sqlite3' `
  --overrides 'data/catalog_overrides.json'
```

Python 直接调用 `build_catalog(...)` 时，`overrides` 默认是 `None`，须显式传入路径才能应用人工规则；这与命令行默认行为不同。

### 转换与校验规则

1. 校验三份资料的 SHA-256；拒绝空角色资料、非法或重复 ID、属性字典键与记录 ID 不一致。
2. 按角色 ID 合并美术映射与属性表，不按姓名模糊匹配。仅属性表存在的角色也入库，并报告缺少素材映射。
3. 稀有度使用已转换的 2–6 星，不再加 1；两个来源有明确数值且冲突时终止导入。
4. `career` 在导入边界转换为灵感元组；未知编号保留原记录、展示字段置空并列入报告。
5. 默认皮肤取“初始皮肤”标签或补充图鉴的 `defaultVariant`，且必须存在于该角色映射中；来源冲突时终止，缺失时不取列表第一项代替。
6. 每个皮肤 ID 必须唯一归属一个角色。按精确文件名建立候选，再应用人工图片规则。
7. 对存在的图片实际解码，检查 PNG 格式、读取尺寸并计算 SHA-256。损坏图不入库，记录原因；路径越出资源根目录则终止。
8. 完成检查后，在显式事务中建表并替换图鉴记录；数据库写入失败则回滚旧数据。含其他业务表或不支持的结构版本时拒绝写入。

| career | 灵感 |
| --- | --- |
| 1 | 岩 |
| 2 | 星 |
| 3 | 木 |
| 4 | 兽 |
| 5 | 灵 |
| 6 | 智 |
| 101 | 星、岩 |

事务防止部分写入，不提供历史快照管理；更新前仍需保存可恢复的旧图鉴与输入版本。

## 图片用途

| kind | 默认目录或用途 |
| --- | --- |
| `portrait` | `singlebg/headicon_img`，默认展示立绘 |
| `icon` | `singlebg/headicon_middle`；沿用现有接口名称，内容可为 Q 版立绘，不能统一解释为头像 |
| `skin_preview` | `singlebg/headskinicon_middle`，皮肤预览 |
| `portrait_variant` | 人工关联的补充立绘 |
| `portrait_decoration_1`、`portrait_decoration_2` | 人工关联的装饰分件 |

动画图集不能直接当作完整立绘。`headskinicon_large` 中已检查的样例是模糊背景，不作为默认主图来源。文件名不一定等于皮肤 ID；动画目录也不能仅按皮肤 ID 推导，例如皮肤 `300302` 的原映射指向 `300303` 动画目录。

## 映射冲突校正

正式规则保存在 [catalog_overrides.json](../data/catalog_overrides.json)，不直接修改下载的原始映射。规则版本为 `1`；完整决策和文件 SHA-256 随来源写入 `catalog_meta`，可随导入复现。

- `images`：按角色、已有皮肤和用途指定路径；拒绝错误归属、重复用途、未知用途及不存在或越界路径。
- `classified_images`：记录不归入玩家皮肤的素材用途，同一路径不得重复分类，也不得与显式图片规则冲突。
- `ignored_missing`：将指定皮肤的主图缺失移入单独报告，不删除皮肤记录、不永久禁止以后补图。

### 诗的礼赞

角色 `3023`，皮肤 `302306`。保留 `302306.png` 为主图，`302305.png` 以 `portrait_variant` 收录。两图服装一致，主要是视图大小差异，不能因文件名不同重复创建游戏皮肤。

### 恶之果

角色 `3100`，皮肤 `310003`。以下图片均位于 `singlebg/headicon_img`：

| 文件 | 用途 |
| --- | --- |
| `310003.png` | `portrait`：包含人物和两侧装饰的完整组合图 |
| `310003_1.png` | `portrait_decoration_1`：装饰分件 |
| `310003_2.png` | `portrait_decoration_2`：装饰分件 |
| `310003_3.png` | `portrait_variant`：人物主体补充图 |

采用完整组合图以保留构图内容；分件仍关联同一皮肤，不新增皮肤。当前没有完成 Box 排版验证，不能据此断言完整图在所有布局中更清晰或更兼容。

### 暂时忽略的主图缺失

| 角色 ID | 皮肤 ID | 处理依据与限制 |
| --- | --- | --- |
| `3029` | `302902` | 斯奈德进阶皮肤，暂按未实装／废弃内容候选处理；原动画映射指向 `302901`，默认皮肤仍未可靠确认 |
| `3066` | `30660001` | “37 的往日”，已确认角色无法装备；仅主页展示，默认Box排除，主页功能保留 |
| `3088` | `30880001` | “塞梅尔维斯的往日”，已确认角色无法装备；仅主页展示，默认Box排除，主页功能保留 |
| `9998` | `999801` | `Machine D III`／未知角色，暂按占位候选处理；原 Spine 指向玛丽莲 `301101_malilian`，不能据此借用图片或确认身份 |

这些是暂定分类，不是官方废案结论。缺少精确同名主图也不代表整个资源包不存在相应形象。未知角色的稀有度和灵感继续为空。

### 敌人 Q 版立绘

29 张原未映射的 `headicon_middle` 图片归类为 `enemy_chibi`，不关联玩家皮肤。逐项文件路径保留在人工规则中，尚未逐项确认敌人名称。已在headicon_monster和roles中找到其他敌人头像及骨骼贴图；29张只是旧扫描目录的剩余图片，非全部敌人或未上架资源，见[美术资源计划](art-resources-todo.md)。

## 报告与异常边界

| 报告字段 | 内容 |
| --- | --- |
| `missing_attributes`、`unknown_careers` | 属性缺失或未知灵感编号 |
| `missing_mapping`、`missing_default` | 美术映射缺失或默认皮肤未确认 |
| `missing_portraits` | 需继续处理的主图缺失 |
| `ignored_missing_portraits` | 已暂时忽略的主图缺失及理由 |
| `invalid_images` | 无法解码或格式不符的图片及错误 |
| `unmapped_images` | 所扫描目录中未实际入库、且未人工分类的文件 |
| `classified_images` | 已核对用途的独立素材 |

命令行输出报告，完整报告同时存入 `catalog_meta`。统计依据实际图片路径；补充图已入库后不再计作未映射。损坏图不会假造可用路径。人工映射指定路径不存在会直接终止；普通候选图片不存在则记录缺口。

本工具仅索引列出的静态目录，不扫描整个资源包。未映射数为零不等于全量素材已全部识别。实际图片回退遵循[回退设计](image-fallback.md)，目前尚未实现。

## 数据来源与版本

| 来源 | 固定版本或记录方式 | 用途 |
| --- | --- | --- |
| [myssal/Reverse-1999-CN-Asset](https://github.com/myssal/Reverse-1999-CN-Asset) | `45e75248ba3b25053fd32e63ab13c2f9f54dd9df` | 角色／皮肤映射与素材 |
| [公开 arcanists.json](https://r2.balthild.com/improviser1999/arcanists.json)，项目 [improviser1999](https://github.com/balthild/improviser1999) | 保存实际下载时间与文件 SHA-256；在线地址会更新 | 稀有度和灵感 |
| [UnderLotus/r1999-roster](https://github.com/UnderLotus/r1999-roster) | `10f0e88112bcb0286d3ddf2b6a5ef37b70951ef3` | 默认皮肤补充、稀有度交叉核对 |

项目代码提交号不能替代远程属性数据的版本。补充图鉴的 `isReleased` 指海外服，不作为国服实装判断，本工具不导入该字段。图鉴未加入技能数据，也不宣称社区快照覆盖当前全部可获取角色。

代码许可见 [LICENSE](../LICENSE)。`r1999-roster` 采用 MIT 许可，已有资料快照保留其 LICENSE；其他第三方资料与游戏资源应分别核对适用条款，不因导入图鉴而转为本项目代码许可。

[图鉴测试](../tests/test_catalog.py) 覆盖重复导入、查询归属、双灵感与未知状态、损坏图、输入校验、事务回滚、人工映射和忽略条目。具体历史导入规模与验证记录见[开发记录](development-log.md)。


## 0.8.0独立目录补全

心相定义已由33条补至135条，普通125、材料7、测试3。26张缺完整定义的图片按候选保留，不默认计入收藏；28款衣着的额外获取编码均对应活动ID。skinLevel区分None/Common/Good/GARMENT/ADVANCED/UNIQUE。

当前独立目录使用448条皮肤定义；早期正式图鉴的424条是另一版本历史基线，不混称为一次导入。本人当前快照84位角色、672条仓库记录均可映射。默认Box收藏分母采用维护者批准的国服资源目录范围，排除材料、测试、剧情/占位与未知素材，不冒充官方实时可获取池。完整过程见[Box里程碑](box-development.md)。


