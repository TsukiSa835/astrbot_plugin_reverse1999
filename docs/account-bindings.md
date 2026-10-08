# 账号绑定规范

状态：已实现 SQLite 持久化；Box 查询仍使用模拟数据源。绑定仅保存关联，不验证游戏账号存在、归属或访问权限。

## 身份与关联

身份键为 `ChatUser(platform, user_id)`，由 AstrBot 的 `get_platform_name()` 和 `get_sender_id()` 构造。平台或发送者标识缺失时返回错误，不保存空身份。

绑定不包含群号、会话 ID 或机器人实例 ID。在共用同一绑定库、且发送者标识为 QQ 号的同类型适配器中，同一 QQ 的群聊和私聊共用绑定。不同平台类型或不同身份体系不自动合并；独立部署且不共享数据库的机器人也不自动同步。

表 `account_bindings` 的主键为 `(platform, user_id, player_id)`，支持：

- 一个聊天账号绑定多个游戏账号。
- 同一游戏账号由多个聊天账号绑定。
- 重复绑定不产生重复记录。
- 解绑只删除当前身份与指定游戏账号之间的关联。

## 输入与账号选择

账号标识去除首尾空白后须为 1–128 个字符，内部不能包含空白。该校验不要求纯数字，以兼容模拟标识及后续数据源。

| 查询条件 | 行为 |
| --- | --- |
| 显式指定合法账号标识 | 直接查询；不要求已绑定，不写入绑定或默认账号 |
| 未指定账号，绑定数量为 0 | 提示绑定 |
| 未指定账号，绑定数量为 1 | 自动查询该账号 |
| 未指定账号，绑定数量大于 1 | 列出各账号的完整查询指令，等待重新发起查询 |

不保存待选会话，不处理单独的序号或 UID 回复。显式查询一次不会改变后续选择规则。

`AccountSelection.player_id` 为 `None` 时表示尚未选定，`candidates` 保存候选账号。当前多账号流程不是多轮消息会话。

## 实现职责

| 文件 | 职责 |
| --- | --- |
| [main.py](../main.py) | 将平台事件转换为 ChatUser；统一解析查询账号；发送结果或输入错误 |
| [domain/bindings.py](../domain/bindings.py) | 定义不可重新赋值的 ChatUser 和账号选择结果 |
| [domain/ports.py](../domain/ports.py) | 定义 BindingStore 的查询、绑定和解绑接口 |
| [services/binding_service.py](../services/binding_service.py) | 校验输入并执行账号选择规则，通过构造参数接收存储实现 |
| [storage/sqlite_bindings.py](../storage/sqlite_bindings.py) | 执行参数化 SQL、管理连接和事务 |
| [presentation/accounts_text.py](../presentation/accounts_text.py) | 生成账号列表及选择提示 |

`bind`、`unbind` 返回是否实际改变记录的布尔值，分别区分新增／已存在和删除／不存在。预期的 `ValueError` 转换为指令提示；数据库异常不伪装成绑定成功。

## 存储与并发

数据库位置为 `StarTools.get_data_dir("astrbot_plugin_reverse1999") / "bindings.sqlite3"`，与插件源代码、公共图鉴分离。

存储初始化创建目录并执行 `CREATE TABLE IF NOT EXISTS`。每次操作通过 `asyncio.to_thread` 执行同步 SQLite 工作，独立打开连接、等待锁最多 10 秒，结束后关闭。写入使用事务，异常时回滚。

SQL 使用占位符传参。重复插入通过复合主键和 `ON CONFLICT ... DO NOTHING` 处理，解绑条件包含完整主键。列表按账号标识排序。上述规则避免多人关联同一游戏账号时互相覆盖。

## 验证与边界

[绑定测试](../tests/test_bindings.py) 使用临时数据库，覆盖重复操作、多账号选择、多人共享账号、跨平台隔离、解绑隔离、重新打开数据库、并发更新和输入检查。

单元测试不直接证明特定 QQ 适配器的真实收发行为。历史验证记录见[开发记录](development-log.md)，指令用法见 [README](../README.md)。
