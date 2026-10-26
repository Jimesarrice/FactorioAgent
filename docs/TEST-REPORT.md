# 动态验证报告

> 2026-10-25 新增真实玩家模式 + MCP 全流程实测：[MCP-FULLFLOW-TEST-2026-10-25.md](runs/MCP-FULLFLOW-TEST-2026-10-25.md)。

环境：Windows，Factorio **2.1.23**，headless 服务端，RCON `27016`，Lua UDP `35000`，实验存档 `server/lab.zip`。所有测试均在本机实际运行，不是 mock。

## 1. 结果总表

| # | 测试 | 结果 | 证据 |
|---|---|---|---|
| 1 | RCON 认证/命令/大输出 | 通过 | 认证响应 `(10,1,2,'')`；`/version` → `2.1.23`；200 KB `rcon.print` 完整返回 |
| 2 | RCON 端口冲突 | 发现并规避 | `127.0.0.1:27015` 被 Apple Mobile Device Service 占用；改用 27016 |
| 3 | `auto_pause` 对无玩家服务器的影响 | 通过（关闭后） | 默认 true 时 tick 停在个位数；`auto_pause:false` 后 10 秒到 tick 620 |
| 4 | 首次 `/c` 的 achievements 确认 | 通过 | 第一次返回空并记日志；第二次执行 |
| 5 | Lua UDP 入站（实验版 mod） | 通过 | `[AGENT] udp rx from port 54943: {"cmd": "ping", "n": 1}` |
| 6 | Lua UDP 出站（无玩家，实验版 mod） | **不可用** | `helpers.send_udp(...,0,35001)` 无异常，但外部收不到 |
| 7 | 裸 character 创建/走路 | 通过 | 单位 1，`(0,0)` → `(6.33,-6.33)`（direction=2，60 tick） |
| 8 | 寻路 | 通过 | `path result id=1 path=21`；走到 `(9.17,9.17)` |
| 9 | 挖矿 | 通过 | 铜/铁/石/煤；背包 `iron-ore x10`、`stone x5`、`coal x5` |
| 10 | 手搓 | 通过 | `iron-gear-wheel x4`（消耗 8 铁板）；`stone-furnace x1`（消耗 5 石） |
| 11 | 放置/碰撞回退 | 通过 | 指定 (11,-19) 被占，自动放到 (10.5,-17.5)，unit 5 |
| 12 | 装入/取出 | 通过 | 熔炉 unit 2：插入 2 铜矿、取 1 铜板；插入 5 铁矿、取 5 铁板 |
| 13 | 冶炼 | 通过 | 5 铁矿 + 煤 → 5 铁板（真实熔炉时间） |
| 14 | 存档/重启持久化 | 通过 | 重启后角色、位置、背包、熔炉仍在 |
| 15 | `game.get_entity_by_unit_number` 用于建筑 | **返回 nil** | 熔炉 unit 2 存在但 API 返回 nil；改为按 `unit_number` 扫描 |
| 16 | 控制台读 mod `storage` | **不可用** | 控制台 `storage` 是关卡存储，`char_id` 为 nil；必须走 `remote.call` |
| 17 | 研究前置检查 | 通过 | `automation` 因缺 `automation-science-pack` 被拒；补齐起始科技后 `add_research` 成功 |
| 18 | CLI | 通过 | `start` → `observe` → `tool place` → `stop` |
| 19 | MCP stdio | 通过 | `initialize`、`tools/list`（44 个 MCP 工具，25 个 LLM 工具 + 19 个 MCP 扩展）、`tools/call observe` |
| 20 | LLM tool-calling 循环（mock） | 通过 | `tests/llm_mock.py`：observe → walk_to → 结束；turn-based 暂停/恢复正确 |
| 21 | LLM 真实 API 调用 | **未测** | 环境中没有 `OPENAI_API_KEY`；工具层与循环已分别实测 |
| 22 | `storage` 命名空间/迁移 | 通过 | 重启后仍为原角色 unit 4、原位置、原背包；未被 `--create` 新角色覆盖 |

## 2. 关键输出摘录

### 2.1 RCON

```
auth -> 0e0000000100000003000000746573740000
auth resp: (10, 1, 2, '')
/c rcon.print("A"..game.tick) -> (13, 2, 0, 'A1\n')
/version -> (17, 7, 0, '2.1.23\n')
```

大输出：

```
5000 -> 5001 chars
50000 -> 50001 chars
200000 -> 200001 chars
```

### 2.2 auto_pause

默认 `auto_pause:true` 时：

```
tick=1  (17 秒后)
tick=3
tick=4
```

改为 `auto_pause:false` 后：

```
tick=620（启动约 10 秒）
```

`on_tick` 不跑时，UDP `recv_udp` 也不会被调用；这曾经导致“UDP 没反应”的假象。

### 2.3 裸 character

```
spawn -> {"ok":true,"unit_number":1,"position":{"x":0,"y":0}}
walk(2,60) -> position {"x":6.328125,"y":-6.328125}  -- direction 2 是 NE
mine_nearest("copper-ore",6) -> inventory {"copper-ore",count=1}
insert_item("iron-plate",20)
craft("iron-gear-wheel",2) -> inventory iron-gear-wheel 2, iron-plate 16
```

注意 direction 的枚举：0=N，2=NE，4=E，6=SE，8=S，10=SW，12=W，14=NW。测试中 `walk(2)` 走向东北而不是东，验证了这一点。

### 2.4 寻路

```
[AGENT] path result id=1 path=21
```

任务随后走到 `(9.17,9.17)` 完成。

### 2.5 完整脚本循环

`tests/demo_loop.py`：

```
resource types within 96:
  copper-ore  (22.0, 2905 tiles, 24,944,543)
  iron-ore    (36.4, 4739 tiles, 33,144,361)
  stone       (45.0,  781 tiles,  6,664,175)
  coal        (77.2, 1209 tiles, 13,497,439)

mine iron-ore: mined 10
mine stone: mined 5
mine coal: mined 5
craft furnace: crafted 1
place furnace: 失败（(92,14) 被树挡住）  -- 这是真实碰撞，不是 bug
```

`tests/smelt_check.py` + 续跑：

```
insert coal: inserted 5
insert iron-ore: target refused iron-ore  -- 炉内还有铜矿，先炼完
wait: waited
take copper plate: took 1
insert iron-ore: inserted 5
wait: waited
take iron plate: took 5
```

这验证了熔炉的**真实配方占用**：炉内已有铜矿时不能混入铁矿；必须先清空/炼完。这是很好的 LLM 决策素材。

### 2.6 持久化

重启后：

```
char: alive=true, unit_number=1, position=(7.59,-19.42),
      inventory=[copper-ore x3]
furnace: unit 2 at (11,-19) 仍在
```

角色、背包、建筑均由 Factorio 存档保存，不依赖 Python 进程。

### 2.7 放置回退

```
请求 place at (11,-19)（已有熔炉）
-> {"ok":true,"unit_number":5,"position":{"x":10.5,"y":-17.5}}
```

### 2.8 MCP

```
initialize -> protocolVersion 2024-11-05, serverInfo factorio-agentbridge
tools/list -> 44 tools
tools/call observe -> Tick 21448 | UPS 60.0 | character (12.88,-17.30) ...
```

## 3. 实验环境注意

- `--create` 生成的无玩家存档没有自动授予起始科技（`electronics`/`steam-power` 等都不是 researched）。真实存档不会这样。实验室用 `python -m bridge.cli init-lab` 补齐；补齐后 `add_research("automation")` 成功、`current_research=automation`。
- 裸 character 的 `unit_number` 不能用于 `game.get_entity_by_unit_number`（该 API 只覆盖带 `get-by-unit-number` 标志的原型）；mod 用 `surface.find_entities_filtered` + `unit_number` 匹配建筑。
- 控制台 `/c` 里的 `storage` 与 mod 的 `storage` 不是一个东西；调试时用 `remote.call`。
- RCON 27015 被 Apple Mobile Device Service 占用；这不是 Factorio 的问题，但很容易误判为“RCON 协议不对”。

## 4. 未验证/未覆盖

- UDP 游戏协议字节级解析、加密/压缩、desync 复现、多客户端并发。
- 长期运行（数小时）稳定性、UPS 下降、内存增长。
- 真实云端 LLM API 的 tool-calling（无 key）；本地 Ollama Q3.5-9B 已完成真实 tool-calling 验证（见 6.5）。
- 虫群攻击/角色死亡/自动重生（代码有，未构造战斗场景）。
- 载具、火车、蜘蛛机甲、电路网络、流体。
- 复杂蓝图的模块/燃料/线缆/配方参数/参数化；跨行星长距离航行与 Shattered Planet。
- Windows 之外的服务端（代码是跨平台的，但只在 Windows 实测）。

## 5. 真实玩家 Scenario（v0.4）验证

环境：`server/agentbot.zip`（scenario 存档）+ `server/scenario-mods`（只有 base/DLC）+ `server/agentbot-server-settings.json`，RCON 27017。先用无客户端验证控制面；随后用 `<FACTORIO_DIR>` **2.1.23 standalone** 真实客户端做单客户端联调。

| 测试 | 结果 | 证据 |
|---|---|---|
| scenario 无 mod 加载 | 通过 | 日志 `[AGENT] agentbridge v2 loaded`；无 `agentbridge` mod 校验和 |
| `state` / `ping` | 通过 | `player.connected=false`；`PONG scenario tick=...` |
| 无真实玩家时不创建裸角色 | 通过 | `character.alive=false`，`allow_bare=false` |
| `instruct` 写入 inbox | 通过 | `instruct('please mine iron')` → seq 3 |
| `/bot <text>` 自定义命令 | 通过 | `/bot craft iron-gear-wheel 2` → inbox kind=command |
| `/say` | **不存在** | Factorio 无此服务器命令；用 `/bot`/聊天/`instruct` |
| `eval` 默认关闭 | 通过 | `{'ok': False, 'error': 'eval is disabled...'}` |
| `set_eval(true)` + `return 1+1` | 通过 | `{'ok': True, 'result': '2'}` |
| `save` 生成 scenario 存档 | 通过 | `server/agentbot.zip`，753 KB，inbox 已清空，eval 关闭 |
| `BotClient.prepare` | 通过 | 生成独立 `bot-data/config.ini`、`player-data.json`（username + service-username）；参数正确 |
| **真实客户端连接/可见** | **通过** | `<FACTORIO_DIR>` 2.1.23 standalone；`PLAYER name=[LLM-Bot] index=1 connected=true` |
| **freeplay 标准开局** | **通过** | 出生在 crash-site 旁；起始物资 burner-mining-drill/stone-furnace/wood；cutscene 清除，controller=1 |
| **真实 LuaPlayer 被 scenario 控制** | **通过** | 走路 `(0,0)→(6.85,0.32)`；挖 5 stone + 5 iron-ore；手搓 stone-furnace |
| **pipette/build_from_cursor 真实建造** | **通过（使用回退）** | `pipette` 对 stone-furnace 返回 false；改为背包→cursor stack→`build_from_cursor`；放下 unit 69 @ (20,-25) |
| **双真实客户端可见** | **通过** | `LLM-Bot#1` 与 `Watcher#2` 同时在线，`players=2`，controller=1 |
| **双客户端下 Bot 控制/同步** | **通过** | 走路 `(0,0)→(7.13,7.26)`，挖 2 stone；两个客户端和服务端均无 desync/CRC/连接错误 |
| 蓝图创建/构建 | **通过** | 见第 6 节：单实体、双实体、16 格地砖、cost/ghost/force、阻挡报错 |
| 太空平台创建/进入/落地 | **通过** | 见第 6 节：create 自动 apply starter pack、enter 到 `platform-1`、异步 land 回 `nauvis` |
| Web 控制台 + 本地 LLM | **通过（fake-local + 真实 Ollama）** | 模型列表、reasoning/决策日志、start/stop、UTF-8、API key 掩码；Q3.5-9B 真实 tool-calling 见 6.5 |
| `bot_loop` + 真实云端 LLM API | **未验证** | 无云端 API key；本地 Ollama 已通过 |

### 结论

Scenario 控制面、freeplay 标准开局、真实玩家身份/可见性、走路/挖矿/手搓/真实建造、双客户端在线、inbox、eval 门禁、蓝图即时建造、太空平台创建/进入/落地、Web 控制台均已实测；**单/双客户端下 RCON 动作没有 desync**。剩余风险是跨行星长距离航行、复杂蓝图和真实 LLM 长时通关；本地 Ollama Q3.5-9B 的短程真实 tool-calling 已通过。玩家名必须由 `player-data.json` 的 `service-username` 提供，只写 `username` 会是空名字；stone-furnace 的 `pipette` 会失败，已用 cursor stack 回退；scenario 内需显式调用 freeplay `on_init`，否则 crash-site 会因 `crashed_ship_items=nil` 崩溃。

## 6. 蓝图 / 太空平台 / Web 控制台（v0.5）验证

环境：`<FACTORIO_DIR>` 2.1.23 standalone 服务端 + 真实客户端；干净 `server/agentbot.zip` 的测试副本；RCON 27017；fake OpenAI-compatible 本地端点 `127.0.0.1:11435/v1`。详细原始输出见 [evidence/blueprint-space-webui.txt](evidence/blueprint-space-webui.txt)。

### 6.1 蓝图

| 测试 | 结果 | 证据 |
|---|---|---|
| 抓图 | 通过 | 石炉 1 实体、石路 16 地砖；保存 `state/blueprints/*.txt` |
| `mode=cost`（单实体） | 通过 | `ghosts=1 revived=1`，背包石炉 1→0，真实 furnace 出现 |
| `mode=cost`（地砖） | 通过 | `ghosts=16 revived=16`，16 格 stone-path，扣 16 stone-brick |
| `mode=cost`（双实体） | 通过 | `ghosts=2 revived=2`，扣 2 stone-furnace，两台实体位置正确 |
| `mode=ghost` | 通过 | `ghosts=1 revived=0`，背包不变，留下 entity-ghost |
| `mode=force` | 通过 | `ghosts=1 revived=1`，背包不变，真实实体 |
| 阻挡位置 | 通过（明确失败） | 返回 `nothing could be placed ... (blocked terrain, existing entity, or fog of war)`，无假成功 |
| 缺少材料 | 通过（明确失败） | 返回 `missing` 清单和 `requirements`，不扣料、不建造 |

实现修正：`build_blueprint` 必须传 `surface`；它返回的表中同时含实体幽灵和 **tile-ghost**，不要再额外扫描地砖（会重复计数）；`LuaItemCommon`/`LuaRecord` 的方法全部用 dot 调用。

### 6.2 太空平台

| 测试 | 结果 | 证据 |
|---|---|---|
| `create` + 自动 starter pack | 通过 | `starter_pack_applied=true`，hub `space-platform-hub` @ `(0,0)`，表面 `platform-1` |
| `hub` | 通过 | 返回 hub 实体 unit/surface 和 schedule |
| `go` / `add_stop` / `schedule` | 通过 | 记录 `vulcanus`/`fulgora`，`temporary`/index 正确 |
| `pause` / `resume` | 通过 | `paused` 状态切换 |
| `enter` | 通过 | 玩家/角色表面变为 `platform-2`，控制器切到平台控制 |
| `land` | 通过（引擎异步） | `land_on_planet()` 返回 true 后约 8 秒角色到 `nauvis`，位置 `(120,-240)`、controller=1 |
| `apply_starter_pack` | 通过 | 对未应用平台补建 hub |

注意：`land_on_planet` 不是同步的，工具会轮询最多 60 秒；平台不在站点时引擎可能拒绝，此时自动回退为“角色传送到当前行星 + `set_controller`”，结果里 `method=teleport`。跨行星航行仍需真实推进器/燃料。

### 6.3 Web 控制台 / 本地 LLM

| 测试 | 结果 | 证据 |
|---|---|---|
| 页面加载 | 通过 | Dashboard/Settings/Decisions 三页；无 console error |
| 中文默认 + 英文切换 | 通过 | 全新浏览器默认中文；右上角切换 English 后静态标签、状态卡、决策日志全部变为英文，切回中文即时生效；选择写入 `localStorage` 刷新后保持 |
| 配置保存 | 通过 | provider/local model/base URL 写入 `state/webui.json` |
| API key 掩码 | 通过 | `/api/config` 返回 `***`；留空保存保留旧值 |
| 模型列表 | 通过 | `/api/models?provider=local` → `["fake-local"]` |
| 启动 Bot | 通过 | `phase=running`，`pid` 有值，连续 cycles 写事件 |
| reasoning | 通过 | assistant 事件含 provider 的 `reasoning`；UI 显示 “REASONING (provider-supplied)” |
| 停止 Bot | 通过 | `phase=stopped`、`exit_code=0`、pid 清空；UI 显示 `STOPPED` |
| 中文日志 | 通过 | `state/webui-bot.out` 与 `/api/logs` 均为合法 UTF-8（子进程注入 `PYTHONIOENCODING/PYTHONUTF8`） |
| 云端/本地切换 | 通过（配置层） | provider `auto/local/cloud` 与 `fallback_cloud`；真实云端请求未测 |

### 6.4 新增工具数

`TOOL_SCHEMAS` 为 25（原 16 + `find_water` + `nearby_entities` + `rotate_entity` + `dismantle_entity` + `build_blueprint` + `lua_eval` + `blueprint_create` + `blueprint_build` + `space`）；MCP 在它之上增加 19 个感知/控制工具，共 44 个。

### 6.5 真实本地 Ollama（Q3.5-9B）

环境：Ollama `127.0.0.1:11434`，模型 `Q3.5-9B:latest`（Qwen3.5-9B Q8_0，262144 上下文，capabilities: tools/thinking/completion），Web UI provider=local，真实服务端 + 真实客户端。详细输出见 [evidence/ollama-q3.5-9b.txt](evidence/ollama-q3.5-9b.txt)。

| 测试 | 结果 | 证据 |
|---|---|---|
| Ollama OpenAI `/v1/models` | 通过 | 返回 `Q3.5-9B:latest` 等 4 个模型 |
| 直接 tool-calling | 通过 | `get_weather({"city":"Paris"})`，5.6 s，finish_reason=tool_calls |
| Web UI local 模型列表 | 通过 | 页面 `Test / list models` 返回 4 个本地模型 |
| 真实 Bot 循环 | 通过 | provider=local、model=Q3.5-9B；模型调用 `say` 正确报告玩家名/坐标/表面/背包；tool_result ok |
| reasoning 捕获 | 通过 | assistant 事件含 `reasoning`；UI 决策页显示“推理（模型服务商返回）” |
| 一轮干净运行 | 通过 | `run_bot(max_cycles=1)` 启动/停止服务端与客户端，真实玩家在线，无异常 |
| 空正文处理 | 通过（已修） | 模型只返回 reasoning、不返回 content 时不再误报 max turns；显示“(model ended with reasoning only)”，UI 中文显示“（模型本轮只返回了推理，没有正文）” |

注意：Q3.5-9B 在 `tool_choice=auto` 下可能只返回 reasoning 和 tool_calls、不返回正文；工具链路不受影响。停止慢模型时若正在请求，Web UI 最多等 30 秒后回收进程，可能记录非零退出码。

## 7. MCP 外部 Agent 接口（v0.3.0）验证

环境：真实服务端 + 真实客户端 LLM-Bot，RCON 27017，绿色测试存档；MCP 客户端通过 stdio 启动 `python -m bridge.mcp_server`。详细输出见 [evidence/mcp-coverage.txt](evidence/mcp-coverage.txt)。

> 本节是早期 44 工具版本的记录。当前 0.3.1 为 53 个 MCP 工具，完整实测见 [MCP-FULLFLOW-TEST-2026-10-25.md](runs/MCP-FULLFLOW-TEST-2026-10-25.md)。

| 测试 | 结果 | 证据 |
|---|---|---|
| `initialize` / `tools/list` | 通过 | serverInfo `factorio-agentbridge 0.3.0`，44 个工具 |
| 自动读取 RCON 配置 | 通过 | 未设环境变量时从 `state/webui.json` 读取 127.0.0.1:27017 |
| 感知工具 | 通过 | get_state / decision_context / observe / scan / find_water / recipe_info / technologies / get_inbox / get_events / get_blueprints / get_platforms |
| 动作工具 dispatch | 通过 | say/walk/mine/craft/place/insert/take/research/wait/build_blueprint/space 均有调用路径；非法参数返回结构化失败 |
| 任务控制 | 通过 | submit_job + wait_job、wait_idle、cancel_job、cancel_all |
| 生命周期 | 通过 | pause/resume、set_speed、save、set_bot_name、set_bare(false) |
| 安全开关 | 通过 | set_eval(false)；lua_eval 默认被拒，返回 ok:false 而非断连 |
| UTF-8 | 通过 | stdout 强制 UTF-8，中文 inbox/事件不乱码 |
| 连接失败处理 | 通过 | tools/call 返回 isError:true 并提示检查 RCON；MCP 会话不退出 |
| smoke test | 通过 | `python tests/mcp_smoke.py --live` → ALL PASS |

覆盖结论：27 个 scenario remote 方法中，25 个玩家/运维命令均有 MCP 工具；仅 `warmup`、`ensure` 为连接/角色生命周期内部方法，不暴露。Bridge 的 `observe_text`、`recipe`、`techs`、`speed`、`wait_idle` 等别名均映射；`connect/close/perform/execute_tool` 为内部实现。

