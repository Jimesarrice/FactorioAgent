# 真实玩家 LLM Bot（Scenario 版）

> 目标：让 LLM 控制一名**真实玩家**，其他玩家能在玩家列表里看到它；能使用正常玩家的建造、蓝图、研究、太空平台等能力；能读取控制台/聊天指令；能自主推进游戏；不需要在服务端或普通客户端安装 mod。

## 1. 先讲硬约束

Factorio 的 `LuaPlayer` 只在**真实客户端连接**时存在；`LuaPlayer.create_character()` 也要求玩家 online。服务端 mod / RCON 不能凭空创建一个 `LuaPlayer`。

因此：

- **纯服务端 mod** 只能控制裸 `character`（上一版），它不在玩家列表里，也没有 `LuaPlayer` 的蓝图/太空平台/GUI 能力。
- 要“其他玩家能看到 + 所有玩家功能”，必须有一个**真实客户端**作为身体。
- 这个客户端可以是第二个 Factorio 客户端，与你的正常客户端同时运行；不需要在游戏里装 mod，因为控制逻辑放在**存档自带的 scenario**里，客户端下载地图时自动获得。

## 2. 架构

```
你的正常客户端 ─┐
                ├── 真实 Factorio 服务器（scenario 存档 agentbot.zip）
Bot 客户端 ─────┘        │  scenario control.lua
（LLM-Bot，真实玩家）     │   ├─ state / submit / inbox / space / blueprint
                          │   └─ 控制 LLM-Bot 的 LuaPlayer
                          │
                    RCON 27017
                          │
                  Python bridge + LLM
                  ├─ AgentBridge / bot_loop.py
                  ├─ BotClient（启动第二个真实客户端）
                  └─ LLM tool calls
```

- **Scenario，而非 mod**：`server/agentbot.zip` 里含 `script.dat`；客户端加入时下载存档，不需要安装 mod。服务器也用 `server/scenario-mods`（只有 base/DLC），没有 `agentbridge` mod。
- **Bot 客户端**：一个正常 Factorio 客户端，独立 `write-data`、独立 `player-data.json`，用户名 `LLM-Bot`；无 mod。它只是“身体”，由 scenario 控制。
- **你的正常客户端**：无 mod，正常玩；会看到 `LLM-Bot` 作为普通玩家。
- **控制面**：RCON 调 scenario 的 `agentbridge` 远程接口；scenario 调 `LuaPlayer` API。
- **LLM**：`bridge/bot_loop.py` 周期观察、读取 inbox、调用模型、执行工具。

## 3. Bot 客户端：唯一需要额外准备的东西

Factorio 没有 headless 客户端。你需要第二个客户端实例：

- 推荐：官方 **standalone** 客户端（factorio.com 下载，用你自己的账号）。它没有 Steam 单实例限制，最适合与正常客户端同时运行。
- Steam 版：不建议直接复制 exe 启动；它会报 `Steam requires game restart`，而且 Steam 通常不允许同账号双实例。若你有第二个账号/第二台机器，可自行处理。
- **同机 Steam 人类客户端 + standalone Bot 的完整方案、端口/模组/验证设置见 [COEXISTENCE.md](COEXISTENCE.md)。**
- 同机运行消耗：建议 `800x600`、very-low 图形、关闭音频；可以最小化。CPU/GPU 仍会跑完整模拟。

`bridge/bot_client.py` 会：

- 在 `bot-data/` 生成独立 `config.ini` 和 `player-data.json`；用户名同时写入 `username` 和 `service-username`（只写前者会得到空玩家名，已实测）；
- 以 `--mp-connect 127.0.0.1:34197` 启动客户端；
- 低画质/窗口化/可选最小化；
- 通过 scenario 的 `player.connected/name` 等待玩家上线；
- 退出时终止客户端（客户端的本地状态不重要）。

启动示例：

```bash
python -m bridge.bot_client \
  --exe "D:/FactorioStandalone/bin/x64/factorio.exe" \
  --server 127.0.0.1:34197 \
  --name LLM-Bot
```

（也可以由 `bot` 命令通过 `--start-client --client-exe` 调用。）

## 4. 服务端启动

```bash
cd <INSTALL_DIR>
python -m bridge.cli start \
  --save "<INSTALL_DIR>/server/agentbot.zip" \
  --mods "<INSTALL_DIR>/server/scenario-mods" \
  --settings "<INSTALL_DIR>/server/agentbot-server-settings.json" \
  --rcon-port 27017
```

- `agentbot.zip` 是 scenario 存档；不要用旧的 `lab.zip`。
- `scenario-mods` 只有 base/DLC；普通客户端不需要装任何 mod。
- `auto_pause=false`，否则没有玩家时世界不推进。
- 你的正常客户端可以连接 `127.0.0.1:34197`；如果客户端有额外 mod，会和服务器 mod 集不匹配，请用干净 profile（或把服务器 mod 集配成一致）。

## 5. 指令：控制台/聊天

Scenario 的 inbox 支持三种来源：

| 来源 | 形式 | 事件 |
|---|---|---|
| 服务器控制台/脚本 | `/c remote.call("agentbridge","instruct","mine iron")` 或 Python `bridge.instruct(...)` | `inbox` kind=console |
| 自定义命令 | `/bot mine iron-ore 20` | kind=command |
| 聊天 | `@bot mine iron` / `bot: mine iron` / `!bot mine iron` | kind=chat |

LLM loop 每轮读取新指令，作为**最高优先级**放进 prompt；也会用 `say` 在游戏里回复。普通聊天（`on_console_chat`）也会记录到 events。

> 注意：Factorio 没有 `/say` 这个服务器命令；用 `/bot ...`、玩家聊天或 `/c remote.call(... "instruct", ...)`。

## 6. LLM 自主循环

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4o-mini   # 或 DeepSeek/Qwen 的 OpenAI-compatible model

python -m bridge.cli bot \
  --start-server --rcon-port 27017 \
  --start-client \
  --client-exe "D:/FactorioStandalone/bin/x64/factorio.exe" \
  --player-name LLM-Bot \
  --goal "从零开始，完成 Space Age，最终抵达 Shattered Planet" \
  --interval 8 --turns 8 --turn-based
```

`bot_loop.py` 每轮：

1. `state()` + `inbox(since)`；
2. 把 goal、上一轮摘要、控制台指令、当前观察拼成 prompt；
3. 调用 LLM 的 tool-calling；
4. 工具执行真实玩家动作；
5. 保存模型回复作为短期 memory，等待下一轮。

`--turn-based` 会在模型思考时暂停游戏，动作执行时恢复；适合慢模型，代价是时间不连续。

## 7. 能力面

已提供的高层动作：

- `walk`、`mine`、`craft`、`place`（真实玩家 `pipette` + `build_from_cursor`）、`insert`、`take`、`research`、`wait`、`say`；
- 蓝图：`blueprint_create`（抓取并保存字符串）、`blueprint_build`（字符串）、`build_blueprint`（玩家蓝图库）；`mode=ghost` 只放幽灵，`mode=cost` 即时建成并扣背包材料，`mode=force` 即时建成不扣材料；
- 太空平台：`create`（默认自动 `apply_starter_pack` 生成 hub）、`apply_starter_pack`、`enter`/`leave`/`land`、`pause`/`resume`、`schedule`/`go`/`add_stop`/`clear_schedule`/`hub`；
- `blueprints()`、`platforms()`、`planets` 查询；
- `instruct`/`inbox` 控制台队列；
- Web 控制台：`python -m bridge.webui --port 8090`（本地/云端 LLM、reasoning、决策日志、配置；详见 [WEBUI.md](WEBUI.md)）；
- `lua_eval`（可选，默认关闭）。

`lua_eval` 是“访问所有玩家 API”的逃生口：它能在 scenario 里执行任意 Lua，配合 `game.get_player("LLM-Bot")` 可调用所有 `LuaPlayer`/`LuaEntity`/`LuaForce`/太空平台 API。默认关闭；开启：

```bash
python -m bridge.cli raw '/c remote.call("agentbridge","set_eval",true)'
```

它也能创建物品、传送、改研究——**这会绕过正常玩家约束**。LLM 的 prompt 明确禁止用它作弊；如果你想严格限制，请不要开启，只使用高层动作，并把缺口反馈给我补工具。

仍未封装成专用工具的：载具/火车驾驶、蜘蛛机甲、电路网络 GUI、物流网络配置、平台调度条件编辑、复杂蓝图的模块/燃料/线缆/配方参数。`lua_eval` 可以调用对应 API，但没有经过“正常玩家”校验。

蓝图实现要点：`LuaItemCommon.build_blueprint` 只创建施工幽灵（实体和地砖都会返回）；`cost` 模式先按原型 `items_to_place_this` 检查并扣除玩家背包，再逐个 `ghost.revive{raise_revive=true}`；`force` 模式跳过扣料。`cost`/`force` 使用 `defines.build_mode.forced`，会自动清除树木/岩石等自然障碍，但不会拆除玩家建筑；`ghost` 使用 normal。位置参数是蓝图包围盒中心。阻挡地形/建筑会导致 0 个幽灵，工具会明确报错而不是假成功。

## 8. 完整通关：能力 ≠ 智力

这个连接器能提供：

- 真实玩家身份与完整游戏状态；
- 从手挖到太空平台的行动 API；
- 控制台指令优先级、长期目标、短期记忆；
- 可选 turn-based 思考；
- `lua_eval` 补齐 API 缺口。

但“LLM 能否完整通关 Space Age 到 Shattered Planet”是模型规划/长时记忆/错误恢复的研究问题，不是连接器能保证的。不要把“能力面齐全”宣传成“已证明可通关”。要验证，需要实际跑一局并记录里程碑；这是一个长期 benchmark。

## 9. 已验证 / 未验证

环境：`<FACTORIO_DIR>` 独立安装 **2.1.23**（含 Space Age），另一台真实客户端与服务器同机运行。

已实测通过：

- scenario 无 mod 加载；客户端下载 865 KB 存档后进入 `InGame`；
- 玩家名 **LLM-Bot** 出现在服务端的 `game.players` / 玩家列表；
- 真实 `LuaPlayer` 被 scenario 控制：
  - 走路：`(0,0)` → `(6.85,0.32)`；
  - 挖矿：挖到 5 stone、5 iron-ore；
  - 手搓：stone-furnace ×1；
  - 真实建造：`place` 在 `(20,-25)` 放下 stone-furnace（unit 69），`mode=real_player`，消耗物品；
- `/bot <text>` 自定义命令写入 inbox；`instruct` 写入 inbox；`say` 正常；
- `eval` 默认关闭；开启后返回 `LLM-Bot/nauvis/char=68`；
- **freeplay 标准开局**：Bot 出生在坠毁飞船旁，拿到 burner-mining-drill/stone-furnace/wood，cutscene 被清除（controller=1）；
- **双真实客户端**：`LLM-Bot#1` 与 `Watcher#2` 同时在线（`players=2`），Bot 走路 `(0,0)→(7.13,7.26)`、挖 2 stone，两个客户端均无 desync/CRC/连接错误；
- 单客户端与双客户端下，RCON 触发的 scenario 状态修改都在客户端生效。
- **蓝图**：`blueprint_create` 抓 1 台石炉/16 格石路；`blueprint_build` 的 `cost` 模式真实建成并扣 1 石炉或 16 石砖，`ghost` 只留幽灵，`force` 不扣料；两台石炉的蓝图 `revived=2`；阻挡位置返回明确错误；
- **太空平台**：`space create` 自动生成 hub；`hub` 返回 hub 实体/表面；`enter` 后玩家出现在 `platform-1`；`land` 触发引擎异步落地并最终回到 `nauvis`（约 8 秒）；
- **Web 控制台**：配置保存、API key 掩码、模型列表、启动/停止、`phase=stopped`、中文 UTF-8 日志、reasoning/决策事件渲染均实测通过（fake-local 端点）。

两个实测踩坑（已修）：

1. **玩家名**：只写 `player-data.json` 的 `username` 会得到空名字；必须同时写 `"service-username": "LLM-Bot"`（BotClient 已这样生成）。
2. **`pipette` 对 stone-furnace 返回 false**：改为先从玩家背包取 1 个物品放进 cursor stack，再 `can_build_from_cursor` / `build_from_cursor` / `clear_cursor`；真实建造验证通过。
3. **freeplay `on_init` 被 scenario 的 `script.on_init` 覆盖**：scenario 内显式调用 `freeplay_module.on_init`（并做首次 tick 懒初始化），否则首次玩家创建时 crash-site 会因 `crashed_ship_items=nil` 崩溃。

仍未验证：

- 跨行星长距离航行（需要推进器/燃料/完整平台建造）与 Shattered Planet；
- 真实云/本地 LLM API 的长时间自主通关（无 API key；仅 fake-local 与 mock 验证）；
- GUI-only 操作（少量需要输入注入或后续补 API）；
- 你的正常客户端与 Bot 在**同一 GPU/桌面**长时间并行的性能。

结论：**“真实玩家 + freeplay 标准开局 + 基础控制 + 真实建造 + 双客户端可见/同步 + 蓝图即时建造 + 太空平台创建/进入/落地 + Web 控制台”已经跑通**；完整 Space Age 通关和跨行星航行仍需继续验证。

## 9.1 存档起点

`server/agentbot.zip` 已并入 base/freeplay 的 `on_init`/`on_player_created`，是**标准 Space Age 自由模式开局**：

- 首个玩家加入时创建坠毁飞船/残骸，并获得起始物资；
- Bot 会退出 crash-site cutscene，进入正常 character 控制；
- 存档本身保持“无玩家”的干净起点，任何玩家（Bot 或你的正常客户端）第一次加入都会得到标准开局。

如果要继续**已有存档**，需要 scenario 转换或 mod 变体；当前 `agentbot.zip` 是新游戏。

## 9.2 修改 scenario 后重建干净存档

Factorio 用 `--config server-data/config.ini` 启动时，scenario 从 **write-data** 的 `server-data/scenarios/` 读取，而不是仓库里的 `scenarios/`。改完 `scenarios/agentbot/control.lua` 后：

```bash
cp scenarios/agentbot/control.lua server-data/scenarios/agentbot/control.lua

# 1) 从 scenario 生成一张全新地图（不要 --start-server 旧存档）
<FACTORIO_DIR>/bin/x64/factorio.exe --start-server-load-scenario agentbot \
  --mod-directory server/scenario-mods \
  --server-settings server/agentbot-server-settings.json \
  --config server-data/config.ini --rcon-port 27017 --rcon-password test

# 2) 保存并退出（控制台或 RCON）
/c game.server_save()
/quit

# 3) 用新生成的干净地图替换交付存档
cp server-data/saves/agentbot.zip server/agentbot.zip
```

`server/agentbot.zip` 应保持“无玩家”的 500 KB 级干净起点；首次加入才生成 crash site。若只想给现有地图换 scenario 代码，也可以在停机时替换存档 zip 内的 `<name>/control.lua`（本项目实测可行），但公开发布前应重新生成干净存档。

## 10. 文件

| 文件 | 作用 |
|---|---|
| `scenarios/agentbot/control.lua` | scenario 控制逻辑（真实玩家/裸角色 fallback/任务/蓝图/太空/inbox/eval） |
| `server/agentbot.zip` | 含 scenario 的存档；客户端下载它，不需要 mod |
| `server/scenario-mods/mod-list.json` | 只启用 base/DLC |
| `server/agentbot-server-settings.json` | auto_pause=false、局域网、无验证 |
| `bridge/bot_client.py` | 第二客户端的启动/配置/等待/最小化 |
| `bridge/bot_loop.py` | 长时 LLM 循环（goal + memory + inbox） |
| `bridge/agent.py` | RCON 接口 + LLM 工具（含 blueprint/space/eval） |
| `bridge/settings.py` | Web/Bot 配置默认值、掩码、API key 保留 |
| `bridge/webui.py` + `webui/` | 本地 Web 控制台（进程管理/事件/配置） |
