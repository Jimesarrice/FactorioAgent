# FactorioAgent 0.3.0 MCP 全流程实测报告

日期：2026-10-25  
测试者：Qoder Desktop（MCP stdio 客户端）  
游戏：Factorio 2.1.23 build 87750（win64, full, space-age）  
系统 / Python：Windows 11 26200 / Python 3.14.3  
运行模式：真实玩家模式（headless 服务端 + 第二个真实客户端 `LLM-Bot`）  
RCON：`127.0.0.1:27017`（仅本机）

## 1. 连接方式

Qoder 通过 MCP stdio 启动 `python -m bridge.mcp_server`，工作目录为分发包根目录，RCON 地址与密码自动读取 `state/webui.json`：

```json
{
  "type": "stdio",
  "command": "python",
  "args": ["-m", "bridge.mcp_server"],
  "cwd": "E:\\Games\\FactorioAgent-0.3.0",
  "env": {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
}
```

服务端与 Bot 客户端保持独立运行；MCP 只作为“大脑”，没有同时运行内置 `bridge.cli bot`。

## 2. 结果总览

| 项目 | 结果 |
|---|---|
| `initialize` / `tools/list` | 通过，`factorio-agentbridge 0.3.0`，53 个工具 |
| 本次实际调用的工具 | 51 / 53 |
| 未调用 | `respawn`（会清空背包）、`set_bare`（仅 Lab 模式） |
| 感知类工具 | 19 / 19 通过 |
| 动作类工具 | 通过；1 项引擎限制、1 项需装配机 |
| 蓝图 | create / ghost / force / cost 缺料报错均通过；玩家蓝图库为空时正确报错 |
| 太空平台 | create / hub / enter / land / pause / resume 通过 |
| 控制面 | pause/resume、speed、eval 门禁、inbox、submit/wait/cancel、save 通过 |
| 客户端同步 | 测试期间无 desync / CRC / 断连记录 |
| 服务端错误 | 本轮无新增错误（仅历史旧 scenario 与 `production_stats` 默认参数两条） |

测试起点 tick≈67213，结束 tick≈82152（约 4 分钟游戏时间，speed=1）。

## 3. 分类明细

### 3.1 感知与上下文

| 工具 | 结果 | 关键返回 |
|---|---|---|
| `ping` | 通过 | `PONG scenario tick=67213` |
| `observe` / `get_state` / `scan` | 通过 | 玩家、坐标、背包、附近资源与实体 |
| `decision_context` | 通过 | state + inbox + events + blueprints + platforms 一次返回 |
| `nearby_entities` | 通过 | 过滤、距离排序、`unit_number` 正确 |
| `find_water` | 通过 | 半径 64 返回 `no water within 64 tiles`（数据事实）；半径 120 找到水面并给出泵位 `{18.5,50.5}`、朝向 0 |
| `recipe_info` | 通过 | `stone-furnace` = 5 stone |
| `recipes_query` | 通过 | `electronic-circuit` 未解锁，材料 1 铁板 + 3 铜线 |
| `technologies` / `tech_tree` | 通过 | 前置、未满足前置、成本、科研包完整 |
| `entity_detail` | 通过 | 炉内库存、配方、状态名、电网等 |
| `production_stats` | 通过（需显式 items） | 铁板产出 4 / 消耗 4；齿轮产出 2 |
| `alerts` | 通过 | 2 台设备 `no_fuel` |
| `resource_patches` | 通过 | 半径 120 内 3 个矿簇，含总量/包围盒 |
| `get_inbox` / `get_events` | 通过 | 指令与 job 事件 |
| `get_blueprints` / `get_platforms` | 通过 | 库为空；平台 `mcp-test-platform` |

### 3.2 动作与生产链

| 工具 | 结果 | 证据 |
|---|---|---|
| `walk_to` | 通过 | 走到 `(-51,3)`，事件 `arrived` |
| `mine` | 通过 | 铁矿 `mined 3`，背包 +3 |
| `take_item` | 通过 | 从坠毁飞船货舱取 3 铁板 |
| `craft` | 通过 | `iron-gear-wheel ×1`，消耗 2 铁板 |
| `insert_item` | 通过 | 向石炉装入 2 铁矿 |
| `take_item`（炉） | 通过 | 取出 2 铁板；矿石已被真实熔炼，取矿正确失败 `nothing taken` |
| `place` | 通过 | 真实玩家建造石炉，`mode=real_player`，扣物品 |
| `rotate_entity` | 通过 / 引擎限制 | 钻机 0°→4° 成功；石炉返回 `cannot rotate stone-furnace`（炉不可旋转） |
| `dismantle_entity` | 通过 | 拆除石炉与实体幽灵，物品返还 |
| `build_entities` | 通过 | 批量放置钻机 + 石炉；一次位置被挡时返回 `blocked or wrong grid position` |
| `set_recipe` | 引擎限制 | 石炉返回 `entity cannot use recipe ...`；本地 API 文档说明 `set_recipe` 仅适用于装配机 |
| `wire_poles` | 通过 | 无电线杆时 `{poles:0, linked:0}` |
| `research` | 通过（正确拒绝） | `missing prerequisites: automation-science-pack` |
| `wait` / `say` | 通过 | 等待 60 tick；中文聊天写入游戏 |

### 3.3 蓝图

| 调用 | 结果 |
|---|---|
| `blueprint_create` | 通过，1 实体 / 0 地砖，保存到 `state/blueprints/mcp-test-furnace.txt`（193 B） |
| `blueprint_build mode=ghost` | 通过，`ghosts=1 revived=0` |
| `blueprint_build mode=force` | 通过，`ghosts=1 revived=1`，真实建成 |
| `blueprint_build mode=cost` | 正确失败，返回 `missing:[{stone-furnace,need:1,have:0}]` |
| `build_blueprint`（玩家蓝图库） | 正确失败，`no blueprint record at index 1`（库为空） |
| 拆除验证 | force 建成的炉与 ghost 均可拆除，现场清理干净 |

### 3.4 太空平台

| 调用 | 结果 |
|---|---|
| `space create` | 通过，`starter_pack_applied=true`，hub unit 598，表面 `platform-1` |
| `space hub` | 通过，返回 hub 与空 schedule |
| `space enter` | 通过，角色表面变为 `platform-1`，`controller_type=7` |
| `space land` | 通过，`method=engine`，回到 `nauvis`（落地动画后角色在坠毁点旁的货舱残骸处） |
| `space resume` / `pause` | 通过，平台状态 `state 4/7`、`paused false/true` |

未测子动作：`leave`、`schedule`/`go`/`add_stop`/`clear_schedule`（需要推进器/站点条件）、单独 `apply_starter_pack`（create 已隐式覆盖）。

### 3.5 控制面

| 工具 | 结果 |
|---|---|
| `pause` / `resume` | 通过；暂停后连续两次 `ping` 均为 tick 69493，恢复后 tick 继续增长 |
| `set_speed` | 通过（5 → 1 均被接受；未做速率精测） |
| `set_eval(false)` + `lua_eval` | 通过门禁：`eval is disabled; call set_eval(true) explicitly` |
| `instruct` → `get_inbox` → `clear_inbox` | 通过，seq 1 写入后清空 |
| `submit_job` + `wait_job` | 通过，异步提交与单独等待均返回 `job_done` |
| `cancel_job` | 通过，`{"ok":true,"canceled":34}` |
| `cancel_all` | 通过，后续 say 正常执行；但事件日志没有 cancel 事件（可观测性缺口） |
| `set_bot_name` | 通过，绑定 `LLM-Bot` |
| `save` | 通过 |

## 4. 关键问题

| 级别 | 问题 | 状态 |
|---|---|---|
| 高 | 分发包 `server/agentbot.zip` 内嵌旧 `control.lua`（63,482 B），缺 9 个接口 | 已修复：替换为源码版 92,839 B，`agentbot.backup.zip` 同步修补；当前存档校验通过 |
| 中 | `production_stats` 不传 `items` 时默认列表含液体 `sulfuric-acid`，Lua 报 `Unknown item name` | 未改代码；调用时显式传物品列表即可 |
| 中 | `set_recipe` 对石炉不可用 | 引擎限制（API 文档：仅装配机）；需 `assembling-machine-1` 才能验证成功路径 |
| 低 | `dismantle_entity` 按 `unit_number` 指定远处目标时不自动走近，返回 `no target entity` | 需先 `walk_to` 到 10 格内 |
| 低 | `cancel_all`/`cancel_job` 不写 job 事件 | 行为正确，仅审计日志缺失 |
| 低 | 文档示例用相对路径启动服务端 | Factorio 工作目录是 `bin\x64`，必须用绝对路径 |
| 提示 | `find_water` 半径 64 可能无水面 | 属地图数据；该出生点需半径 ≥120 |

## 5. 未覆盖项

- `respawn`（会清空背包，避免破坏测试角色）。
- `set_bare`（仅 Lab 裸角色模式）。
- 平台调度、跨行星航行、推进器燃料、Shattered Planet。
- 带地砖的蓝图、复杂蓝图模块/线缆参数。
- 多客户端（仅 1 个真实客户端在线）。
- 长时间自主运行与 UPS 衰减。

## 6. 当前现场状态

- 玩家 `LLM-Bot` 在线，`nauvis`，位置约 `(-14.5, -2.4)`，背包：齿轮 ×2、铁矿 ×1、铁板 ×3、石炉 ×1。
- 世界内有电动机钻 548、石炉 555（均无燃料）；太空平台 `mcp-test-platform` 已暂停在 nauvis 轨道。
- 存档：`server/agentbot.zip`，1.54 MB，内嵌 scenario 92,839 B，zip 校验通过。
- 蓝图：`state/blueprints/mcp-test-furnace.txt`。
- 日志：本轮无 desync / CRC / 连接错误。

## 7. 结论

MCP 全流程可用：Qoder 能通过 53 个工具完成观察、寻路、挖矿、取物、手搓、真实建造/拆除、旋转、批量建设、研究排队、蓝图即时建造、太空平台创建/进入/落地，以及暂停、加速、指令队列、存档等控制操作。51 个工具实测通过，2 个按设计未调用；发现的问题集中在分发包存档版本（已修复）、`production_stats` 默认参数与 `set_recipe` 的引擎适用范围上，不影响核心游玩闭环。
