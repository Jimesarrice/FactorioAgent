# 复用 airi-factorio 的分析

上游：`https://github.com/moeru-ai/airi-factorio`（MIT，已克隆到 `<WORKSPACE>\airi-factorio`）。它是「真实 Factorio 客户端 + headless 服务端 + RCON REST + 日志 WebSocket + mod 任务队列 + OpenAI」的完整实验。本项目的连接器是在它的思路基础上重写的一个**无 GUI、可存档、无外部服务依赖**的版本。

## 1. 上游结构

| 包 | 作用 | 关键文件 |
|---|---|---|
| `packages/factorio-wrapper` | 启动 headless 服务端，把 stdout 推到 WebSocket | `src/main.ts`, `src/config.ts` |
| `packages/agent` | 消费 WebSocket 日志，解析聊天/mod 输出，调 OpenAI，发 RCON 命令 | `src/main.ts`, `src/parser.ts`, `src/llm/*` |
| `packages/autorio` | 服务端 mod：远程接口 + 玩家任务状态机 | `src/control.ts`, `src/task_manager.ts`, `src/tools.ts` |
| `factorio-rcon-api`（外部项目） | 把 RCON 包装成 REST | 不是本仓库，agent 通过 HTTP 调用 |
| `tstl-plugin-reload-factorio-mod` | TypeScript→Lua 热重载 | 本项目未用（直接写 Lua） |

## 2. 直接复用/改编的逻辑

| 能力 | 上游做法 | 本项目做法 |
|---|---|---|
| 服务端启动参数 | `--start-server save --rcon-password --rcon-port`（`factorio-wrapper/src/main.ts`） | 相同，另加 `--server-settings`、`--enable-lua-udp`、`--no-log-rotation` |
| RCON 控制 | `v2FactorioConsoleCommandRawPost({input:"/c ..."})`（`agent/src/main.ts`） | 自实现 Source-RCON 客户端（`bridge/rcon.py`），无 REST 服务、无 npm 依赖 |
| 远程接口 | `remote.add_interface("autorio_operations"/"autorio_tools", ...)`（`autorio/src/control.ts`, `tools.ts`） | 单个 `agentbridge` 接口，`submit(json)` 统一动作，`state()` 返回 JSON |
| 任务队列 | `new_task_manager()`：`IDLE/WALKING_TO_ENTITY/MINING/PLACING/MOVING_ITEMS/CRAFTING/...`（`task_manager.ts`） | 保留状态机思想；改为 JSON job + 超时 + 卡住检测 + 取消 + 事件日志 + 持久化 |
| 寻路 | `surface.request_path{...}` + `on_script_path_request_finished` + `walking_state`（`control.ts` 399-420, 477-531） | 复用；改为每 job 保存 `path/id`，90 tick 卡住检测，路径请求重试 |
| 挖矿 | `player.update_selected_entity()` + `player.mining_state = {mining=true, position=...}`（`control.ts` 314-318） | 复用；改为裸 character，按背包增量计数，资源耗尽自动换 tile |
| 手搓 | `player.begin_crafting({recipe,count})` + 监听 `on_player_crafted_item` | 直接 `character.begin_crafting`，轮询 `crafting_queue`/背包，不依赖玩家事件 |
| 放置 | `surface.create_entity{name, position, force, raise_built=true, player}` + 手动扣物品 | 保留思路；先 `can_place_entity`，冲突时找附近空位，按 `items_to_place_this` 扣正确物品 |
| 物品搬运 | `inventory.insert/remove` 遍历实体库存 | 复用；修复上游的计数/回滚 bug（见下） |
| LLM 工具 | `agent/src/llm/tools.ts`（2 个工具）+ `message-handler.ts`（OpenAI agent） | 22 个 LLM 工具 + 40 个 MCP 工具 + 通用的 OpenAI-compatible `/chat/completions`（本地/云端），不锁定模型 |
| 状态观测 | `log_player_info`（位置、背包、附近实体、科技、合成队列） | 相同信息 + 聚合资源 + 当前 job + 事件 seq；`observe_text` 面向 LLM |
| 聊天触发 | 解析 `[CHAT]` 日志，把玩家聊天当输入 | 保留为可选：mod 记录 `on_console_chat`；主入口是 CLI/LLM/MCP |

## 3. 上游的关键限制（本项目为何要改）

### 3.1 必须有真实客户端在线

`autorio/src/control.ts` 的 `on_tick`、`log_player_info`、`craft_item` 都取：

```lua
local player = game.connected_players[0]
if (player === undefined || player.character === undefined) return
```

这要求有一个 GUI 客户端连上服务器；否则 `connected_players` 为空，mod 完全不工作。上游的 README 也是让人类客户端加入后聊天触发。

本项目改用**裸 character 实体**，不再依赖 `LuaPlayer`：

```lua
local e = s.create_entity({name="character", position=p, force=game.forces.player})
e.walking_state = {walking=true, direction=...}
e.mining_state = {mining=true, position=...}
e.begin_crafting({recipe=..., count=...})
```

实测可行（见 `docs/TEST-REPORT.md`）。这是两者最大的架构差异。

### 3.2 `player.position` / `player.character`

上游混用 `player.position`、`player.walking_state`、`player.mining_state`。在 2.x 中这些能力实际在 `LuaControl`/`character` 上；裸 character 场景必须用 `character.*`。`LuaPlayer.character` 断开时为 nil，`create_character` 要求在线，这两点决定了不能走 `LuaPlayer` 路线。

### 3.3 放置没有真实约束

`state_placing` 里：

- 用 `inventory.find_item_stack(entity_name)` 找**实体名**，但背包里是**物品名**（例如 `stone-furnace` 恰好同名；对 `assembling-machine-1` 与 `assembling-machine-1` 可能同名，但对带放置结果的物品不总成立）；
- 直接 `create_entity`，没有 `can_place_entity` 碰撞检查；
- 扣物品是在创建成功后 `item_stack.count - 1`，如果创建失败/位置非法没有统一回滚；
- 不支持指定方向/配方/附近空位回退。

本项目：`can_place_entity` → `create_entity` → 按 `items_to_place_this` 扣物品；指定点冲突时在附近找空位并返回实际坐标；支持 `direction`/`recipe`。

### 3.4 物品搬运计数 bug

`control.ts` 的 `state_moving_items` 从实体取出物品时：

```ts
const removed = inventory.remove(...)
...
if (inserted < removed) { inventory.insert(remaining); moved_total += inserted }
else { moved_total += removed }
moved_total += removed   // 又加了一次
```

第二行会重复计数，导致 `max_count` 提前满足/日志错误。本项目重写为「先取、再插、按实际插入量记账、插入失败回滚」，不累加两次。

### 3.5 任务没有超时/卡住/持久化

`task_manager.ts` 只有队列和状态，没有：

- 路径失败/卡住的处理；
- 挖矿/合成超时；
- 取消当前动作时的停止（走路/挖矿状态可能残留）；
- 存档/读档后的任务恢复；
- 事件流（只有 `log` 文本）。

本项目每个 job 有 deadline、phase、detail；`cancel`/`cancel_all` 会停 `walking_state`/`mining_state`；事件带 seq 可被外部轮询；角色/背包由 Factorio 存档持久化，重启后 `ensure` 自动补角色。

### 3.6 依赖链过重

上游需要 Node/pnpm、`factorio-rcon-api` REST 服务、WebSocket 服务、`neuri/openai`、`execa` 等。本项目：

- Python 3 标准库即可（urllib/socket/subprocess）；
- RCON 直接在进程内；
- LLM 只依赖 OpenAI-compatible HTTP；
- MCP server 也是标准库。

### 3.7 模型写死

`message-handler.ts` 里 `model: 'gpt-4o'`。本项目用 `OPENAI_MODEL`/`--model`，可接 Qwen/DeepSeek/本地 OpenAI-compatible 服务。

## 4. 保留的宝贵经验

- **用服务端真实模拟，而不是脚本变魔术**：上游的 walk/mine/craft/place 都是真实 API，本项目延续。
- **`request_path` + `walking_state` 是可靠的移动组合**：裸 character 同样适用。
- **`mining_state` 比 `player.mine_entity()` 更真实**：保留挖矿动画/时间。
- **任务队列而不是一次执行一大段 Lua**：LLM 的每次动作都可观测、可取消。
- **日志/事件是异步世界的自然接口**：上游用 stdout→WebSocket；本项目用 RCON state/events + 可选文件/UDP。
- **mod 的 `info.json` 结构、`remote.add_interface` 命名、`serpent`/JSON 输出**：直接沿用。

## 5. 许可证与致谢

airi-factorio 为 MIT。本项目的 Lua/Python 代码是重新实现，未直接复制上游源文件；架构思想、API 用法和部分状态机命名来自上游。建议在发布时保留以下致谢：

```
Inspired by moeru-ai/airi-factorio (MIT):
https://github.com/moeru-ai/airi-factorio
Original idea: https://github.com/naklecha/factorio-automation
```

如果后续直接复制上游代码片段，请在该文件头保留 MIT 版权声明与许可文本。
