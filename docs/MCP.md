# MCP：让外部 Agent 直接接管 Factorio 玩家

`bridge/mcp_server.py` 是一个 **stdio MCP server**。MCP 客户端（Qoder、Claude Desktop、自定义 Agent）通过它调用与内置 bot 相同的 RCON/scenario 控制面，直接观察世界、执行动作、读取控制台指令并做决策。

```
MCP client (Qoder/Claude/Agent)
        │ JSON-RPC over stdio
        ▼
bridge/mcp_server.py
        │ TCP RCON 127.0.0.1:27017
        ▼
Factorio server + agentbot scenario
        ▼
真实客户端 LLM-Bot（身体）+ 其他玩家可见
```

## 1. 启动顺序

1. 启动服务端（或让 Web 控制台启动）：
   ```bash
   python -m bridge.cli start \
     --save "<INSTALL_DIR>/server/agentbot.zip" \
     --mods "<INSTALL_DIR>/server/scenario-mods" \
     --settings "<INSTALL_DIR>/server/agentbot-server-settings.json" \
     --rcon-port 27017
   ```
2. 启动真实客户端 **LLM-Bot**（身体）：
   ```bash
   python -m bridge.bot_client --exe "<FACTORIO_DIR>/bin/x64/factorio.exe" --name LLM-Bot
   ```
   或在 Web 控制台点击“启动机器人”（会同时起服务端和客户端）。
3. 配置 MCP 客户端，见下一节。

MCP server 默认从 `state/webui.json` 读取 `bot.host/rcon_port/rcon_password`，因此不用重复配端口。环境变量优先级更高：

```text
FACTORIO_HOST
FACTORIO_RCON_PORT
FACTORIO_RCON_PASSWORD
```

也可以直接启动并覆盖：

```bash
python -m bridge.mcp_server --host 127.0.0.1 --port 27017 --password test
```

## 2. MCP 客户端配置

把 [mcp-config.example.json](mcp-config.example.json) 合并到客户端配置：

```json
{
  "mcpServers": {
    "factorio": {
      "command": "python",
      "args": ["-m", "bridge.mcp_server"],
      "cwd": "<INSTALL_DIR>",
      "env": {"PYTHONIOENCODING": "utf-8"}
    }
  }
}
```

`cwd` 必须是本项目根目录（或设置 `PYTHONPATH`）。服务端/客户端未启动时，MCP 仍能完成 `initialize`/`tools/list`，但 `tools/call` 会返回连接错误；先启动游戏。

## 3. 工具目录（53 个）

### 感知与上下文

| 工具 | 作用 |
|---|---|
| `decision_context` | **推荐第一步**：状态 + inbox + 事件 + 蓝图库 + 平台，一次取全 |
| `observe` | 紧凑文本观察（玩家、背包、附近资源/实体、任务、研究） |
| `get_state` | 完整 JSON 状态（可指定 radius） |
| `scan` | 更大范围扫描 |
| `nearby_entities` | 附近实体过滤表：半径/名称/类型、是否含自然资源、按距离排序，返回 unit_number |
| `find_water` | 最近水面、可用 offshore-pump 位置/朝向、岸边位置（校验 2x2 水面与可放置性） |
| `recipe_info` | 配方材料/产物（prototype 名称） |
| `recipes_query` | 批量配方库：名称/子串过滤、enabled、能耗、类别、材料、产物；默认包含未解锁配方 |
| `technologies` | 已启用未研究的科技、前置、trigger 信息 |
| `tech_tree` | 完整科技树：研究状态、前置/未满足前置、成本/次数、科研包、trigger |
| `entity_detail` | 深度实体信息：朝向、状态名、血量、可采、配方、全部库存、流体、电网、drop/mining 位置、爪过滤、传送带内容 |
| `production_stats` | 物品生产统计（产出/消耗累计），用于判断流水线产量；**只接受物品名**，石油气/硫酸等流体名会返回显式错误，省略 `items` 使用安全默认物品表 |
| `alerts` | 汇总停电、缺燃料、缺料、产物满、流体短缺、无资源等异常建筑 |
| `resource_patches` | 大范围资源簇：总量、tile 数、中心/包围盒，用于选址和输油路线 |
| `get_inbox` / `get_events` | 控制台指令 / 任务事件日志 |
| `get_blueprints` / `get_platforms` | 玩家蓝图库 / 太空平台 |

### 角色动作（全部为真实玩家动作，阻塞到完成）

| 工具 | 作用 |
|---|---|
| `walk_to` | 寻路行走；失败时自动直走回退 |
| `mine` | 挖固体资源；`resource="tree"` 伐木 |
| `craft` | 手工合成 |
| `place` | 放置建筑（真实 `build_from_cursor`） |
| `insert_item` / `take_item` | 装入/取出熔炉、箱子、lab 等 |
| `rotate_entity` | 旋转已放置建筑（可逆时针），需在 10 格内 |
| `dismantle_entity` | 拆除已放置建筑并把物品还给玩家，需在 10 格内 |
| `research` | 排队科技（trigger 科技会明确拒绝并提示 trigger） |
| `set_recipe` | 修改已有**装配机**的配方（按 unit_number；炼油厂/化工厂也属于 assembling-machine）。石炉是固定配方，会明确拒绝 |
| `build_entities` | 批量建设服务：按精确坐标放置实体、自动设配方/接线，**从真实玩家背包扣除物品**；适合一次建整条产线 |
| `wire_poles` | 修复/连接附近电线杆铜线（蓝图 revive 后的必要步骤） |
| `wait` | 等待游戏时间 |
| `say` | 游戏内聊天报告 |

### 蓝图与太空

`blueprint_create`、`blueprint_build`（cost/force/ghost）、`build_blueprint`（玩家蓝图库）、`space`（create/apply_starter_pack/enter/leave/land/pause/resume/schedule/go/add_stop/clear_schedule/hub）。

### 任务与控制

| 工具 | 作用 |
|---|---|
| `submit_job` / `wait_job` / `wait_idle` / `cancel_job` / `cancel_all` | 原始 job 提交/等待/队列空闲/取消（覆盖所有 job 类型） |
| `instruct` / `clear_inbox` | 写入/清空控制台指令 |
| `pause` / `resume` / `set_speed` | 暂停/恢复/加速 |
| `save` / `respawn` | 存档/重生 |
| `ping` | tick 心跳 |
| `set_bot_name` / `set_bare` / `set_eval` | 运维/实验开关，谨慎使用 |
| `lua_eval` | 默认关闭；开启 `set_eval` 后可执行任意 Lua，**绕过正常玩家约束** |

## 4. 推荐决策循环

1. 调用 `decision_context`。
2. 根据 `state`/`inbox` 选**一个**动作，调用对应工具；不要并行提交多个 job。
3. 读返回的 `ok/detail/result/observation`；失败就调整位置、材料或配方。
4. 每完成一个里程碑用 `say` 报告。
5. 要详细全量状态时用 `get_state`；平时用 `observe` 省 token。
6. 控制台指令优先级最高：每轮先读 `get_inbox`，处理完再继续自己的目标。

## 5. 覆盖审计：scenario/bridge 命令 → MCP

| scenario / bridge 命令 | MCP 工具 |
|---|---|
| `ping` | `ping` |
| `instruct` | `instruct` |
| `state` | `get_state` / `observe` / `decision_context` |
| `submit` | `submit_job` (+ `wait_job`) |
| `cancel` / `cancel_all` | `cancel_job` / `cancel_all` |
| `events` | `get_events` |
| `scan` | `scan` |
| `detail` | `entity_detail` |
| `recipe` | `recipe_info` / `recipes_query` |
| `techs` / `tech_tree` | `technologies` / `tech_tree` |
| `stats` | `production_stats` |
| `alerts` | `alerts` |
| `resource_patches` | `resource_patches` |
| `set_recipe` / `build_entities` / `wire` | `set_recipe` / `build_entities` / `wire_poles` |
| `inbox` / `clear_inbox` | `get_inbox` / `clear_inbox` |
| `set_eval` / `eval` | `set_eval` / `lua_eval` |
| `set_bot_name` / `set_bare` | `set_bot_name` / `set_bare` |
| `blueprints` / `platforms` | `get_blueprints` / `get_platforms` |
| `find_water` | `find_water` |
| `blueprint_create` / `blueprint_build` | `blueprint_create` / `blueprint_build` |
| `save` / `pause` / `speed` / `respawn` | `save` / `pause`+`resume` / `set_speed` / `respawn` |
| 高层动作 `walk/mine/craft/place/insert/take/rotate/dismantle/research/wait/say/space` | 同名工具（`insert`→`insert_item`，`take`→`take_item`） |

只保留在内部、不暴露为 MCP 工具：`warmup`（连接握手自动执行）、`ensure`（角色懒创建）、`perform`（bridge 内部封装）。`wait_idle`/`wait_job` 已作为任务控制工具暴露，但正常决策优先使用阻塞式高层动作。

## 6. 实测

```bash
python tests/mcp_smoke.py          # initialize + tools/list，53 个工具
python tests/mcp_smoke.py --live   # 连接运行中的游戏，调用只读工具
```

2026-10-25 全流程实测报告见 [runs/MCP-FULLFLOW-TEST-2026-10-25.md](runs/MCP-FULLFLOW-TEST-2026-10-25.md)。MCP 0.3.9（客户端电力/科研/装配机 + 无人值守循环 + 同机共存 + 后台输入/内存），53 tools；客户端 MCP 49 tools；`initialize`、`tools/list`、`get_state`、`decision_context`、`ping`、`observe`、`scan`、`nearby_entities`、`find_water`、`recipe_info`、`recipes_query`、`technologies`、`tech_tree`、`entity_detail`、`production_stats`、`alerts`、`resource_patches`、`wire_poles`、`get_inbox`、`instruct`、`get_events`、`get_blueprints`、`get_platforms`、`pause`/`resume`、`set_speed`、`set_eval(false)`、`submit_job`+`wait` 均返回成功；`tools/call` 错误以 `isError:true` 返回，不中断会话。

## 6.5 客户端输入 MCP（无 RCON/无服务端 mod）

如果服务器是原版 freeplay、没有 `agentbridge` scenario 或没有开放 RCON，可以单独运行：

```bash
python -m bridge.client_mcp_server
```

它提供 49 个 `client_*` 工具（0.3.9 新增 2 个：set_recipe/recipe）：

- 输入：窗口列表/绑定/聚焦、截图（可内联返回图片）、按键、长按、走路、鼠标点击/长按、滚轮、文本、地图和背包开关；需要前台窗口。
- 高层后台动作：`client_action_attach/state/mine/mine_entity/pick/build/craft/insert/take/pick_ground/open/walk_to/stop/close_ui/status/detach`；使用正常客户端输入 + 只读 Lua 状态，不需要窗口焦点。
- 无人值守循环：`client_auto_start`（收矿/装炉/取板/分煤/工单合成/回锚点）、`client_auto_status`、`client_auto_stop`；也可用 `python -m bridge.client_autopilot` 独立运行。
- 配方 GUI：`client_action_set_recipe`（打开无配方机器→搜索→双击结果→自校验）、`client_action_recipe`（只读 get_recipe/status）。
- 自动供料：燃烧机械臂/木箱/传送带都可用 `client_action_build` 摆放；机械臂拾取在朝向前方、投放在背后（`e.pickup_position`/`e.drop_position` 可读）。
- 后台读取：`client_memory_attach/status/observe/inventory/detach`，通过 Frida 只读 Lua 桥读取位置、血量、背包、附近资源/实体和研究，不需要窗口焦点。

输入工具不修改内存/游戏状态；内存工具只读，但需要安装 `frida`。

配置示例：[client-mcp-config.example.json](client-mcp-config.example.json)。完整说明见 [CLIENT-INJECTION.md](CLIENT-INJECTION.md)。

## 7. 安全边界

- RCON 只绑 `127.0.0.1`，MCP 没有额外认证；不要暴露到公网。
- `lua_eval`、`set_eval`、`set_bare` 是运维逃生口，普通游戏请保持关闭。
- MCP server 会读取本机 `state/webui.json` 中的 RCON 密码；不要在共享机器上泄露该文件。
- 每个 `tools/call` 都是真实游戏动作，可能消耗材料/时间；Agent 应先观察再执行。
