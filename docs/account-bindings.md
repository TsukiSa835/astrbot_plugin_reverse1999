# 账号绑定

绑定是真实持久化的关联，查询目前仍使用 mock 数据源。保存 UID 不表示已验证账号存在或归属。

## 使用

- `/1999绑定 player-a`：新增绑定，已有绑定不会被覆盖。
- `/1999绑定 player-b`：同一聊天用户可以继续绑定其他账号。
- `/1999账号`：查看当前用户的绑定列表。
- `/1999解绑 player-a`：仅移除当前用户与此账号的关联。
- `/1999box`、`/1999皮肤`：没有绑定时提示绑定，只有一个时自动查询，多个时先列出对应查询指令。
- `/1999box player-a`、`/1999皮肤 player-a`：显式查询该账号，本次选择不会改变绑定或成为默认账号。

多账号选择通过重新发送完整查询指令完成，不处理单独的序号或 UID 回复，不保存待选会话。
显式指定账号的查询沿用原行为，不要求先绑定；真实数据源的访问权限由后续接入方案确定。

## 身份与存储

身份键使用 AstrBot 的平台类型 `get_platform_name()` 和发送者标识 `get_sender_id()`。
在以 QQ 号作为发送者标识的 QQ 适配器中，同一 QQ 在任意群聊、私聊和相同类型的机器人连接中共用绑定。
不使用群号、会话 ID 或机器人实例 ID。不同平台类型的同号用户相互独立。
不同适配器若使用不同身份体系，不自动合并；例如开放平台的用户标识不能直接当作 QQ 号。

SQLite 文件位于 `StarTools.get_data_dir("astrbot_plugin_reverse1999") / "bindings.sqlite3"`，使用 AstrBot 专用插件数据目录，不放入插件源代码目录。
表的主键为 `(platform, user_id, player_id)`，因此同一游戏账号可以属于多个聊天用户的绑定列表。
重复绑定无副作用；解绑只删除完整主键匹配的一条关联。每次写入使用数据库事务。

当前多个指令共用 BindingService 和 BoxService；绑定持久化不等于缓存游戏数据，每次查询仍调用数据源。

## 按调用顺序理解代码

### 1. main.py 识别聊天用户

`_chat_user()` 调用 `event.get_platform_name()` 和 `event.get_sender_id()`，分别取得平台类型和发送者标识。
两者缺失时抛出 `ValueError`，由指令转换为提示，不会保存一个所有人共用的空用户绑定。
`ChatUser(platform=platform, user_id=user_id)` 把框架事件转换为普通的业务数据。

### 2. domain/bindings.py 定义数据

`@dataclass(frozen=True)` 为 ChatUser 生成初始化方法，并禁止直接重新赋值其身份字段。
`platform: str` 和 `user_id: str` 是身份的两个组成部分。
AccountSelection 中的 `player_id` 是本次已选定的账号，`None` 表示尚未选定；`candidates` 是供选择的绑定列表。
这些类不导入 AstrBot 或 SQLite。

### 3. domain/ports.py 定义存储能力

BindingStore 是 Protocol，约定三个异步方法：`list_accounts` 返回账号列表，`bind` 新增关联，`unbind` 删除关联。
两个写入方法返回 bool：True 表示本次实际改变了存储，False 表示关联已经存在或待删除的关联不存在。
方法体的 `...` 表示此处只定义接口，具体行为由存储实现提供。

### 4. services/binding_service.py 处理规则

`validate_player_id` 的 `strip()` 清除首尾空白。条件分别检查空值、超过 128 个字符，以及标识内部包含空白。
`any(char.isspace() for char in player_id)` 表示只要有一个字符属于空白，就判定输入不合要求。
`raise ValueError(...)` 交给指令显示输入错误；`return player_id` 返回整理后的标识。

构造方法把外部传入的 BindingStore 保存为 `self._store`，避免业务代码自己创建数据库。
`bind`、`unbind` 先检查标识，再等待存储完成；`list_accounts` 直接读取当前用户的列表。
`select_account` 按顺序判断：显式指定则返回该账号；否则读取绑定；列表长度为一则自动选中；其余情况返回未选定和列表。
这里没有写入默认账号，因此显式查询一次后，下一次省略账号仍会重新按绑定数量判断。

### 5. storage/sqlite_bindings.py 保存数据

`Path` 表示数据库路径；`mkdir(parents=True, exist_ok=True)` 确保数据目录存在。
`CREATE TABLE IF NOT EXISTS` 只在表不存在时创建；复合主键限制的是完整三元组，不单独限制 player_id。

`_execute` 用 `sqlite3.connect(..., timeout=10)` 打开连接，在锁竞争时允许等待最多十秒。
外层 `closing(...)` 确保连接关闭，内层 `with connection` 在成功时提交事务、异常时回滚。
`connection.execute(sql, parameters)` 把 SQL 与参数分开传入；SQL 中的问号由参数填充，账号字符串不会被当成 SQL 执行。
`cursor.fetchall()` 返回查询的所有行，`cursor.rowcount` 返回该写入语句影响的行数。

异步方法通过 `await asyncio.to_thread(...)` 在线程中执行阻塞的数据库操作，使等待期间不阻塞机器人的事件循环。
`list_accounts` 用平台和用户号筛选，按账号标识排序，然后通过 `[row[0] for row in rows]` 提取每行的账号。
`bind` 的 `ON CONFLICT ... DO NOTHING` 让重复绑定无副作用；`changed == 1` 判断是否新增。
`unbind` 的 WHERE 同时限定平台、用户号和账号，确保不删除其他用户的关联。

### 6. presentation/accounts_text.py 生成提示

`render_account_selection` 在空列表时给出绑定提示；多账号时逐项生成完整查询指令。
`lines.extend(...)` 把每个账号对应的指令加入列表，`"\n".join(lines)` 将列表连接为多行文字。
`render_bound_accounts` 则用于 `/1999账号`，展示当前用户全部绑定。

### 7. main.py 组装和发送

插件初始化时用 StarTools 获取独立数据目录，创建 SQLiteBindingStore，再把它传入 BindingService。
`_resolve_player_id` 统一调用选择服务：输入错误返回提示，已选定返回账号，未选定调用展示函数生成提示。
其返回类型 `tuple[str | None, str]` 表示“账号或 None，以及提示文字”两个值。

Box 和皮肤指令都先调用这个辅助方法；没有选定账号就 `yield` 提示并 `return`，不会提前查询游戏数据。
绑定和解绑指令在缺少参数时显示用法，随后调用服务，依据返回的 bool 区分成功改变和重复操作。
`try` / `except ValueError` 将预期的输入问题转成回复；数据库错误不被伪装成绑定成功。

## 验证

`tests/test_bindings.py` 使用 unittest 的异步测试，每项测试创建自己的临时数据库，并在结束后清理。
覆盖多人共享账号、重复绑定、多账号选择、解绑隔离、跨平台隔离、重新打开数据库、并发更新和输入检查。
测试环境另验证了 AstrBot 的真实指令参数解析、发送者身份接口、跨群私聊、插件重建和独立进程读取。
