# 架构：LLM 具身 Factorio Agent 连接器

## 1. 目标与约束

目标是让 LLM 在**真实运行**的 Factorio 服务器里持续玩游戏：看见世界、决定行动、承担真实后果（碰撞、挖矿时间、原料、冶炼时间、虫群），并能在多次会话之间保存/恢复。

硬约束：

- 不伪造游戏状态；世界由真实 Factorio 服务端推进。
- 不要求 GUI 客户端；服务端可在无人值守的 Windows 机器上跑。
- 不重写 Factorio 引擎，不逆向 UDP 锁步协议。
- LLM/框架可替换；工具调用协议用通用 OpenAI function calling。
- 失败可恢复：任务超时、角色死亡、卡住、存档/退出。

## 2. 方案对比

| 方案 | 做法 | 可行性 | 结论 |
|---|---|---|---|
| A. 协议客户端 | 直接实现 UDP 发现/加入/地图块/输入/CRC | 需要重写确定性模拟与地图/mod 加载 | 不可行（见 `PROTOCOL.md`） |
| B. 真实客户端 + 输入注入 | 启动 GUI 客户端，模拟点击/键鼠 | 可行但脆弱；需要显示/GPU/Steam；无法无头；LLM 只能看截图 | 可作为“可视化模式”，不作为主通道 |
| C. 无头服务端 + Lua 具身角色 + RCON | 服端 mod 创建真实 character，外部用 RCON 驱动 | 已实测：走路/挖矿/手搓/放置/冶炼/存档 | **主方案** |
| D. 假玩家 RPC（只调 API） | 直接 `game.print`/生成物品 | 不是“玩游戏”，没有真实过程 | 仅用于测试/管理 |

本项目选 C。B 可后续叠加：真人/观战客户端加入同一服务器，mod 把 Agent 的裸 character `associate_character` 给该玩家，即可“看见 Agent 在走”。C 的所有状态都在真实服务器里，LLM 通过工具改变世界。

## 3. 组件

```
┌────────────────────────────── Windows ──────────────────────────────┐
│                                                                     │
│  LLM / MCP client / CLI                                             │
│        │  OpenAI tool calls / JSON-RPC                             │
│        ▼                                                            │
│  bridge/ (Python)                                                   │
│   ├─ llm_agent.py   tool-calling loop, local/cloud provider          │
│   ├─ bot_loop.py    goal + memory + inbox long-run loop              │
│   ├─ bot_client.py  second real client (body for the bot)            │
│   ├─ settings.py    persisted web/bot config + key masking           │
│   ├─ webui.py       local HTTP console (state/logs/config/control)   │
│   ├─ mcp_server.py  stdio MCP server (44 tools)                     │
│   ├─ cli.py         start/stop/observe/tool/llm                     │
│   ├─ agent.py       AgentBridge: state/submit/wait/cancel/scan      │
│   ├─ rcon.py        Source-RCON client (no deps)                    │
│   └─ server.py      spawn/save/quit headless Factorio               │
│        │  TCP 127.0.0.1:27016 (RCON)                                │
│        ▼                                                            │
│  Factorio headless server (real simulation, 60 UPS)                 │
│   └─ mods/agentbridge/control.lua                                   │
│       ├─ remote interface: state / submit / cancel / scan / ...     │
│       ├─ job FSM: pathing → following → mining/crafting/...         │
│       ├─ real character entity (walking_state, mining_state, ...)    │
│       └─ event journal + save/respawn                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.1 为什么 mod 要自己创建角色

`LuaPlayer.character` 在断开时是 nil，`create_character()` 要求玩家在线。裸 `character` 实体不受此限制，且具备 `LuaControl` 的走路/挖矿/手搓/背包能力。它不是一个 `LuaPlayer`，所以：

- 优点：完全无头；不依赖 Steam/GUI/显卡；可在服务器上 24h 跑；存档可恢复。
- 缺点：不能用 `build_from_cursor`、蓝图、GUI、个人物流等只接受 `LuaPlayer` 的功能；建造由 mod 校验+扣物品+`surface.create_entity` 模拟。

## 4. 任务状态机

```
submit(action)
   │
   ▼
queued ──► running ──► pathing ──► following ──► mining / crafting / waiting
                        │              │                 │
                        │              └─ stuck/timeout ─┤
                        └─ no path ─────────────────────┤
                                                       ▼
                                                  done | failed | canceled
```

- 每个 job 有 `id/kind/phase/detail/started_tick`，状态通过 `state()` 和 `events()` 暴露。
- `pathing` 使用 `surface.request_path`，由 `on_script_path_request_finished` 异步回填；`following` 每个 tick 设 `walking_state.direction`。
- 卡住检测：每 90 tick 比较位置；连续 3 次几乎没动则失败。
- 超时：walk 3 分钟、mine 8 分钟、craft 10 分钟（可在 action 里传 `timeout_ticks`）。
- 取消：`cancel(id)`/`cancel_all` 立即停止走路/挖矿并清队列；下一 tick 启动下一个 job。
- 角色死亡：`on_entity_died` 清 `char_id`，每 120 tick 自动重生（可在 mod 里关 `auto_respawn`）。死亡会丢失背包，符合真实规则。

## 5. 动作（mod API）

所有动作通过 `remote.call("agentbridge", "submit", json_string)` 提交；返回 `{ok, id}`。

| kind | 参数 | 行为 |
|---|---|---|
| `walk` | `x,y,timeout_ticks?` | 碰撞感知寻路走到目标 |
| `mine` | `name,count,radius?,timeout_ticks?` | 找最近同类资源，走到 2.2 tile 内，挖到数量 |
| `craft` | `recipe,count,timeout_ticks?` | 校验配方/原料，`begin_crafting`，等待产出 |
| `place` | `name,x?,y?,direction?,recipe?` | 校验物品/碰撞，扣 1 个物品，`create_entity`；位置冲突时在附近找空位 |
| `insert` | `target?,entity_name?,item,count,radius?` | 从角色背包插入附近实体 |
| `take` | `target?,entity_name?,item,count,radius?` | 从实体取到角色背包 |
| `research` | `tech` | 校验前置科技，`force.add_research` |
| `wait` | `ticks` | 等待 |
| `say` | `message` | `game.print` |

查询：`state(radius?)`、`scan(radius?)`、`recipe(name)`、`techs(limit?)`、`events(since?)`。
管理：`ensure`、`respawn(x?,y?)`、`cancel`、`cancel_all`、`pause`、`speed`、`save`。
启动：`warmup`（吃掉 achievements 确认）。

### 5.1 资源与目标定位

`state()` 返回按资源类型聚合的 `resources`：

```json
{"name":"iron-ore","tiles":4739,"total_amount":33144361,
 "nearest":{"x":-14.5,"y":-33.5,"distance":1.1,"amount":1577050}}
```

这避免了一片铜矿把 80 条明细全部占满、反而看不到远处的铁。`mine` 内部仍按 tile 找最近目标，不依赖外部传坐标。

### 5.2 建造与真实约束

- 物品检查：`prototypes.entity[name]`、`items_to_place_this[1]`、背包数量；
- 位置：显式坐标或角色附近 `find_non_colliding_position`；
- 碰撞：`surface.can_place_entity{name,position,direction,force}`；
- 扣物品、`create_entity{..., force=character.force, raise_built=true}`；
- 如果指定点被占用，自动在 5 tile 内找可用点，返回实际位置；
- 不支持旋转的多格复杂连接（传送带/管道会自动连接，但地下带/分流器等高级摆放未专门处理）。

## 6. 观察与决策

`AgentBridge.observe_text()` 给 LLM 的紧凑视图：

```
Tick 21448 | UPS 60.0 | character (12.88, -17.30) hp 250/250
Inventory: copper-plate x1, iron-ore x5, iron-plate x5
Crafting: none
Resources nearby: copper-ore @(16.5,-22.5) d=6.3 tiles=252 total=1664536
Entities nearby: stone-furnace#2 @(11,-19) d=2.5
Current job: idle
Research: automation 0.0%
```

原则：

- 只给决策需要的信息；完整 JSON 通过 `state()` 按需取。
- 坐标是地图 tile 坐标；方向 0/4/8/12（对角线 2/6/10/14）。
- 所有动作阻塞到完成/失败；工具结果显式 `ok/done` 或 `failed + detail`。
- LLM 循环支持 `--turn-based`：思考时 `game.tick_paused=true`，执行动作时 resume，动作完成后再次暂停。这样模型看到的是稳定世界，也避免在模型思考时被虫群偷袭；代价是真实时间不连续。

## 7. 多 Agent 扩展

当前 mod 管理**一个**角色（`storage.char_id`）。多 Agent 的可行扩展：

1. 每个 agent 一个 `character`，在 mod 里用 `agents[id] = {char_id, job, queue}` 替代单例；
2. 每个 agent 一个 force（最多 61 个新 force），研究/科技/战斗互不干扰；
3. RCON 接口带 `agent_id` 参数；或每个 agent 一个独立 mod 实例（不推荐，存档会混乱）；
4. 共享地图时注意实体碰撞、资源争抢、服务器 UPS；建议每人一个独立存档/服务器，或明确分区。

## 8. 运行与运维

- 专用存档：不要拿主存档直接跑 Agent；先复制或用新存档。
- `auto_pause=false`：否则无玩家时世界冻结。
- RCON 只绑本机：`--rcon-bind 127.0.0.1:27016`，强密码；不要暴露公网。
- 退出：`save()` 后 `/quit`；`FactorioServer.stop()` 已封装。
- 日志：服务端 stdout/console log；mod 的 `log("[AGENT] ...")` 会进 `factorio-current.log`。
- 备份：`server/lab.zip` 是实验存档；投产前做版本化备份。
- 性能：默认 60 UPS；`state` 扫描半径默认 18，资源聚合上限 16 类、实体 60 个；需要更大范围用 `scan(radius)`。RCON 轮询在 LLM 场景下不是瓶颈，真正的耗时是挖矿/走路/冶炼。
- 存档命名空间：mod 状态放在 `storage.agentbridge` 下，避免与同服其他 mod 的 `storage` 键冲突；旧实验存档会自动迁移。

## 9. 已知限制

- 裸 character 不是 `LuaPlayer`：无 GUI、蓝图、个人物流、`build_from_cursor`、部分只接受玩家的 API。要全部玩家能力，使用真实玩家 scenario（见第 10 节）。
- 真实玩家模式的复杂蓝图缺模块/燃料/线缆/配方参数；太空平台跨行星航行仍需真实推进器与燃料。
- 不支持载具、火车、蜘蛛机甲、电路网络 UI、流体手工混合等；可逐步扩展。
- `mine` 只支持固体资源（铁/铜/煤/石/铀）；砍树/采石（tree/rock）未实现。
- 研究能否推进取决于存档里是否有实验室和科技包；连接器只负责排队。
- 无头 `--create` 存档缺少“起始科技”，实验室用 `init-lab` 补齐；真实存档不需要。
- `helpers.send_udp` 在无玩家专用服务器上出站不可用；当前用 RCON 请求/响应。
- 没有做 UDP 游戏协议字节级兼容；这是设计选择，不是未完成的 TODO。

## 10. 真实玩家 scenario 与 Web 控制台（v0.5）

实验室裸角色适合验证控制面，但不能用 `LuaPlayer` 专属功能（蓝图、太空平台、个人物流、GUI）。完整玩法切到**真实玩家 scenario**：

```
真实客户端 A (LLM-Bot) ──加入──┐
                               ├─ 服务端（存档自带 scenario，无 mod）
真实客户端 B (Watcher) ──加入──┘        │ RCON 27017
                                        ▼
                              Python bridge / Web UI
                               ├─ AgentBridge → remote.call("agentbridge", ...)
                               ├─ LLMBot loop → 云端或本地 OpenAI-compatible
                               └─ Web UI (127.0.0.1:8090)
```

- scenario 源码：`scenarios/agentbot/control.lua`；运行时应放在 **write-data 的** `server-data/scenarios/agentbot/`。
- 客户端不需要装 mod：加入时下载含 scenario 的存档；服务端也只有 base/DLC。
- 真实 `LuaPlayer` 由第二客户端提供；scenario 通过 socket/RCON 指令驱动这个玩家的 `character`，所以其他玩家能在玩家列表/世界中看到它。
- 蓝图：`build_blueprint` 只产生 entity/tile ghost，随后 `revive` 真实化；`cost` 先检查/扣除玩家背包，`force` 不扣料。
- 太空平台：`create` 后必须 `apply_starter_pack` 才有 hub；`enter/land` 操作真实玩家；`land_on_planet` 是异步的，轮询到行星表面或用传送回退。
- Web UI 是纯标准库 HTTP 服务，轮询 `/api/state`、`/api/logs`、`/api/config`、`/api/models`；启动 Bot 时用子进程 `python -m bridge.bot_loop --config state/webui.json`，停止用 flag + 进程回收。
- LLM 选择：`provider=local/cloud/auto`；本地任何 OpenAI-compatible `/v1`；`fallback_cloud` 在本地失败时切云端。provider 返回的 `reasoning_content` 原样展示，不生成/伪造隐藏思维链。
- Web UI 默认只绑 `127.0.0.1`；API key 掩码返回，明文只落本机 `state/webui.json`；子进程强制 UTF-8，避免中文日志乱码。
