# Factorio LLM Agent Connector

> 分发版部署请先阅读 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。当前分发版 **0.3.5** 已修复 2026-10-25 MCP 全流程实测发现的问题，并加入同机 Steam 共存、客户端输入与后台内存读取；本文档中的 `J:\...` 路径是作者开发环境的示例，分发版请用 `deploy/configure.py` 生成本机配置。

让大模型在**真实运行的 Factorio 服务器**里扮演一名角色：会走路、会挖矿、会手搓、会造建筑、会装炉冶炼，能被虫群攻击，也会存档/读档。没有 GUI、没有截图识别、没有伪造游戏状态。

- 游戏：Factorio **2.1.x**（本机 2.1.23）
- 连接方式：服务端 mod + **RCON** + 真实 `character` 实体
- Python 3.10+，**零第三方依赖**（标准库 socket/subprocess/urllib）
- LLM：任意 OpenAI-compatible `/chat/completions`（OpenAI / DeepSeek / Qwen / **Ollama/LM Studio/llama.cpp 本地模型**）
- 也提供 **MCP stdio server** 和**本地 Web 控制台**（思维链/决策日志、配置、启动/停止、控制台指令）

> 设计结论：Factorio 的 UDP 游戏面是「完整地图下载 + 同 mod + 确定性锁步 + CRC」，不是可轻量冒充的 RPC。可维护的接入口是服务端 Lua/RCON。详见 [docs/PROTOCOL.md](docs/PROTOCOL.md)。

## 快速开始

### 1. 准备 Factorio 与 mod

把 `mods/agentbridge/` 放到服务端的 mod 目录，或用 `--mod-directory` 指向本项目 `mods/`。服务端设置至少包含：

```json
{
  "auto_pause": false,
  "allow_commands": "true",
  "visibility": {"public": false, "lan": true},
  "require_user_verification": false
}
```

`auto_pause` 必须为 **false**：没有玩家连接时，否则世界不推进，角色/任务全部冻结。

本项目的实验环境在 `standalone/`（一份 `factorio.exe` + `steam_api64.dll` 的副本，`data/` 和 `mods/` 为 junction），用于隔离实验；你也可以用原来的 `<FACTORIO_DIR>\bin\x64\factorio.exe`。

### 2. 启动服务端

```bash
cd <INSTALL_DIR>
python -m bridge.cli start
```

它会用 `server/lab.zip`、`mods/`、`server/lab-server-settings.json` 启动，RCON 在 `127.0.0.1:27016`，游戏 UDP 在 `34197`。启动命令返回后服务端继续在后台运行。

自定义：

```bash
python -m bridge.cli start \
  --exe "<FACTORIO_DIR>/bin/x64/factorio.exe" \
  --save "D:/saves/agent.zip" \
  --mods "D:/saves/mods" \
  --settings "D:/saves/server-settings.json" \
  --rcon-port 27016 --rcon-password "change-me"
```

### 3. 看世界

```bash
python -m bridge.cli observe
python -m bridge.cli scan --radius 96
python -m bridge.cli state
```

### 4. 做动作

```bash
python -m bridge.cli tool walk_to '{"x": 10, "y": 10}'
python -m bridge.cli tool mine '{"resource": "iron-ore", "count": 10}'
python -m bridge.cli tool craft '{"recipe": "stone-furnace", "count": 1}'
python -m bridge.cli tool place '{"entity": "stone-furnace", "x": 3, "y": 4}'
python -m bridge.cli tool insert_item '{"target": 2, "item": "iron-ore", "count": 5}'
```

也可以直接提交原始 job：

```bash
python -m bridge.cli submit '{"kind":"walk","x":10,"y":10}'
python -m bridge.cli wait <id>
```

### 5. 让 LLM 玩

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://api.openai.com/v1   # 可选
export OPENAI_MODEL=gpt-4o-mini                    # 可选

python -m bridge.cli llm \
  --start-server \
  --turn-based \
  --task "先观察周围，找到铁矿，挖 10 个铁矿石、5 个石头、5 个煤；做一个石炉并放下；烧 5 个铁板并取出来。每一步报告进度。"
```

`--turn-based` 会在模型思考时暂停游戏、执行动作时恢复，避免模型思考期间世界继续跑（例如被虫群攻击）。不加则是实时模式。

### 6. MCP

把 `docs/mcp-config.example.json` 合并到你的 MCP 配置中，先启动服务端和 LLM-Bot 客户端，然后客户端会看到 **53 个 MCP 工具**：

- 感知：`decision_context`、`observe`、`get_state`、`scan`、`nearby_entities`、`find_water`、`recipe_info`、`recipes_query`、`technologies`、`tech_tree`、`entity_detail`、`production_stats`、`alerts`、`resource_patches`、`get_inbox`、`get_events`、`get_blueprints`、`get_platforms`
- 动作：`walk_to`、`mine`（含伐木）、`craft`、`place`、`insert_item`、`take_item`、`rotate_entity`、`dismantle_entity`、`research`、`set_recipe`、`build_entities`、`wire_poles`、`wait`、`say`
- 蓝图/太空：`blueprint_create`、`blueprint_build`、`build_blueprint`、`space`
- 控制：`submit_job`、`wait_job`、`wait_idle`、`cancel_job`、`cancel_all`、`instruct`、`clear_inbox`、`pause`、`resume`、`set_speed`、`save`、`respawn`
- 运维：`ping`、`set_bot_name`、`set_bare`、`set_eval`、`lua_eval`

### 本阶段报告与 LLM 交接

- [阶段二报告：火箭/白瓶攻关、BUG 与决策](docs/runs/PHASE2-ROCKET-WHITE-SCIENCE-REPORT.md)
- [LLM 决策速查（接手指南）](docs/runs/LLM-DECISION-NOTES.md)
- [MCP 全流程实测报告（2026-10-25）](docs/runs/MCP-FULLFLOW-TEST-2026-10-25.md)

MCP server 使用 stdio、换行分隔 JSON-RPC；日志写 stderr，不污染协议输出。自动读取 `state/webui.json` 的 RCON 参数。完整工具说明、覆盖审计和客户端配置见 [MCP.md](docs/MCP.md)。

### 7. Web 控制台 + 本地/云端 LLM

```bash
python -m bridge.webui --port 8090
# 浏览器打开 http://127.0.0.1:8090
```

- 界面默认中文，右上角可切换 English（选择保存在浏览器本地，刷新后保持）。
- **Dashboard**：RCON/玩家/背包/任务/研究/附近资源与实体/Bot 进程日志，可启动/停止 Bot、暂停/恢复、存档、发送控制台指令。
- **Decisions & Reasoning**：显示 provider 返回的 `reasoning_content`（不伪造隐藏思维链）和每次工具调用/结果。
- **Settings**：provider=`auto|local|cloud`、本地与云端 base URL/model/API key、local 失败回退云端、temperature、目标、玩家名、tick 间隔、turn-based、是否自动起服/起客户端，以及所有路径和 RCON 参数。
- 默认只绑定 `127.0.0.1`；API key 在 UI/API 中显示为 `***`，留空保存不会覆盖已存密钥；明文只保存在本机 `state/webui.json`。
- 本地模型只需提供 OpenAI-compatible 端点：Ollama `http://127.0.0.1:11434/v1`、LM Studio `:1234/v1`、llama.cpp `:8080/v1`、vLLM `:8000/v1`。当前默认/已实测：Ollama `Q3.5-9B:latest`。云端仍用 `OPENAI_API_KEY/OPENAI_BASE_URL/OPENAI_MODEL` 或 UI 配置。
- Bot 事件写入 `state/bot-events.jsonl`，进程输出写入 `state/webui-bot.out`（UTF-8）；停止后状态显示 `STOPPED`，异常退出显示 `EXITED <code>`。
- 完整页面/API/生命周期说明：[WEBUI.md](docs/WEBUI.md)。


## 关于“完全模拟协议客户端”

`docs/REWRITE-FEASIBILITY.md` 记录了反编译与可行性验证的结论：**直接重写 Factorio 引擎、实现完全模拟的 UDP 协议客户端，等价于 clean-room 重写整款游戏，不是本项目的短期目标。** 本项目交付的是服务端具身 Agent（真实引擎 + mod + RCON），能在自己的服务器上让 LLM 真正玩；它不冒充官方客户端，也不能加入别人的服务器。反编译资产、卡点和三条可行路线都在该文档中。

## 真实玩家模式（推荐用于“其他玩家能看到”）

裸 character 模式不会出现在玩家列表，也不能用蓝图/太空平台。要满足“真实玩家 + 全部玩家功能”，必须有一个真实客户端作为身体；控制逻辑放在**存档自带的 scenario**里，普通客户端不需要装 mod。

- 详细架构、启动、指令、能力面和验证状态：[REAL-PLAYER-BOT.md](docs/REAL-PLAYER-BOT.md)
- **与 Steam 客户端同机共存（standalone 第二客户端、独立端口/配置/模组）：[COEXISTENCE.md](docs/COEXISTENCE.md)**
- **没有服务端 scenario/RCON 时的客户端通道：[CLIENT-INJECTION.md](docs/CLIENT-INJECTION.md)**（输入注入 + Frida 只读内存/Lua；`python -m bridge.client_mcp_server`）
- 场景存档：`server/agentbot.zip`；服务端 mod 目录：`server/scenario-mods`（只有 base/DLC）
- 第二个客户端：`python -m bridge.bot_client --exe <standalone factorio> --name LLM-Bot`（需要 standalone 客户端；Steam 版不建议双实例）。**已在 `<FACTORIO_DIR>` 2.1.23 standalone 上验证：真实玩家可见、freeplay 标准开局（坠毁飞船/起始物资）、走路/挖矿/手搓/真实建造、双真实客户端在线无 desync、蓝图即时建造、太空平台创建/进入/落地，以及 RCON 同步**；本地 Ollama Q3.5-9B 的真实 tool-calling/`say` 已通过，完整 LLM 长时通关仍未验证，见 [TEST-REPORT.md](docs/TEST-REPORT.md) 第 5、6 节。
- 本地/云端 LLM 与图形控制台：`python -m bridge.webui --port 8090`（见上文第 7 节）。
- 一体化长时循环：`python -m bridge.cli bot --start-server --start-client --client-exe <standalone> --player-name LLM-Bot --goal "..."`
- 控制台指令：`/bot <text>`、`@bot <text>`、或 `python -m bridge.cli raw '/c remote.call("agentbridge","instruct","...")'`
- `server/agentbot.zip` 已并入 freeplay 标准开局：第一个玩家加入时创建坠毁飞船/起始物资；存档保持无玩家的干净起点。

## 文件结构

```
FactorioAgent/
├─ bridge/
│  ├─ rcon.py          Source-RCON 客户端（认证/命令/大输出）
│  ├─ server.py        启动/保存/退出 headless 服务端
│  ├─ agent.py         AgentBridge + 34 个 LLM 工具 + 观测格式化
│  ├─ llm_agent.py     OpenAI-compatible tool-calling 循环（local/cloud/fallback）
│  ├─ bot_client.py    第二个真实客户端的启动/配置/最小化
│  ├─ bot_loop.py      长时目标循环（goal + memory + inbox）
│  ├─ settings.py      Web/Bot 配置、API key 掩码与默认值
│  ├─ webui.py         零依赖本地 Web 控制台后端
│  ├─ mcp_server.py    stdio MCP server（53 个 MCP 工具）
│  └─ cli.py           命令行入口
├─ webui/              index.html / style.css / app.js
├─ mods/agentbridge/
│  ├─ info.json
│  └─ control.lua      裸角色实验模式的角色/任务状态机
├─ scenarios/agentbot/ 真实玩家 scenario 源码（改完要同步到 server-data/scenarios）
├─ server/
│  ├─ lab.zip              裸角色实验存档
│  ├─ agentbot.zip         真实玩家 scenario 存档（干净起点，客户端自动下载，无需 mod）
│  ├─ scenario-mods/       只有 base/DLC 的服务端 mod 目录
│  ├─ agentbot-server-settings.json
│  ├─ lab-server-settings.json
│  └─ map-gen-settings.json
├─ state/              webui.json / bot-events.jsonl / blueprints / 日志
├─ docs/
│  ├─ PROTOCOL.md      协议与可接入面分析
│  ├─ ARCHITECTURE.md  连接器设计与扩展
│  ├─ AIRI-REUSE.md    airi-factorio 复用分析
│  ├─ REA-NOTES.md     REA/Ghidra/Rizin/PDB 记录
│  ├─ WEBUI.md         Web 控制台/API/本地 LLM 说明
│  ├─ TEST-REPORT.md   实测结果
│  └─ evidence/        测试输出与 PDB/字符串证据
├─ tests/              RCON/角色/完整循环的验证脚本
└─ standalone/         隔离的实验用 Factorio 副本（不随项目分发游戏文件）
```

## 工具/动作

`AgentBridge`（`bridge/agent.py`）是核心 API：

| 方法 | 作用 |
|---|---|
| `state(radius=18)` | 完整 JSON：tick、角色、背包、job、队列、附近资源/实体、科技 |
| `observe_text()` | 给 LLM 的紧凑文本 |
| `submit(action)` | 提交 job，返回 id |
| `wait_job(id)` / `wait_idle()` | 等待完成 |
| `scan(radius)` | 更大范围扫描（资源按类型聚合） |
| `recipe(name)` / `techs()` | 配方/科技查询 |
| `pause(flag)` / `speed(v)` | 暂停/调速 |
| `save()` / `respawn()` | 存档/重生 |
| `execute_tool(name,args)` | 工具名到动作的映射 |

job 类型：`walk`、`mine`、`craft`、`place`、`insert`、`take`、`research`、`wait`、`say`、`build_blueprint`、`space`。每个 job 有超时、phase、detail；失败会返回原因而不是静默。

蓝图工具：

| 工具 | 作用 |
|---|---|
| `blueprint_create(name, x1,y1,x2,y2)` | 从当前表面抓蓝图，保存到 `state/blueprints/<name>.txt`，返回实体/地砖数 |
| `blueprint_build(name, x, y, mode)` | `ghost` 只放施工幽灵；`cost` 即时建成并从玩家背包扣物品（默认）；`force` 即时建成但不扣物品 |
| `build_blueprint(index, x, y, mode)` | 构建玩家蓝图库中的记录，模式同上（需客户端先在图库里存图；与字符串路径共用构建 API） |

- 位置 `(x,y)` 是蓝图包围盒中心；地砖（stone-path、space-platform-foundation 等）同样支持。
- `cost` 先检查材料，缺少时返回 `missing` 清单；地形/建筑阻挡时返回明确错误。`cost`/`force` 使用 Factorio `forced` 建造模式，会自动清除树木/岩石等自然障碍，但不会拆除玩家建筑。
- 模块、燃料、线缆、配方参数、参数化蓝图属于已知缺口（见限制）。

太空平台工具（`space`）：

```
create(planet, starter_pack, name)   创建平台并默认 apply starter pack（生成 hub）
apply_starter_pack(platform)         补应用 starter pack
enter/leave(platform)                进入/离开平台内部
land()                               落回平台当前行星（引擎异步落地，必要时自动回退）
pause/resume(platform)               暂停/恢复平台
schedule / go(station) / add_stop / clear_schedule / hub
```

## 存档与退出

```bash
python -m bridge.cli stop     # 先 save，再 /quit
```

服务端退出时会再保存一次。角色、背包、建筑、科技都在 `lab.zip` 里；Python 进程重启不影响游戏。

**不要直接拿主存档跑 Agent**。先复制一份，或新建存档：

```bash
# 用 Factorio 自带 --create（会得到一个无玩家、无起始科技的实验存档）
python -m bridge.cli start --save "C:/FactorioAgent/server/new.zip"
# 首次用新实验存档时，补齐起始科技（真实存档不需要）
python -m bridge.cli init-lab
```

## 已知限制

- 裸 `character` 不是 `LuaPlayer`：不能用 GUI、蓝图、个人物流、`build_from_cursor`；这些能力只在真实玩家 scenario 模式下可用。
- 真实玩家 scenario 的蓝图是“幽灵 + `revive`”实现：`cost` 扣物品、`force` 不扣；不支持模块/燃料/线缆/配方参数/参数化蓝图，复杂蓝图可能只建成部分实体并留下幽灵。
- 太空平台支持创建/进入/落地/调度，但跨行星长距离航行需要真实推进器/燃料；`land` 的引擎落地是异步的（约数秒）。
- 载具/火车/蜘蛛机甲/电路网络 UI/流体手工混合未封装；`mine` 只支持固体资源。
- 研究只负责排队；要真正推进需要实验室和科技包。
- `helpers.send_udp` 在无玩家专用服务器上只能收、不能发；本项目用 RCON 请求/响应。
- 未做 UDP 游戏协议字节级兼容（这是刻意选择）。
- 实验室的 `--create` 存档需要 `init-lab` 才有起始科技；真实游戏存档不需要。

## 故障排查

| 现象 | 原因/处理 |
|---|---|
| RCON 连接被重置，Factorio 日志没有 `New RCON connection` | 端口被别的进程占用（本机 27015 是 Apple Mobile Device Service）。`netstat -ano | findstr 27015`，换端口或 `--rcon-bind 127.0.0.1:27016` |
| tick 不涨/角色不动 | `server-settings.json` 的 `auto_pause` 还是 true |
| 第一条 `/c` 没输出 | 首次 Lua 命令被 achievements 确认吞掉；连接器已自动发两次，手工测试时再发一次 |
| `insert` 报 `target refused` | 熔炉里已有另一种矿，先炼完/取出；或目标满了 |
| `place` 报 collision | 位置被树/建筑占用；换位置，或依赖自动附近回退 |
| `research` 报 missing prerequisites | 先研究前置科技；实验存档先 `init-lab` |
| 角色消失 | 每 120 tick 自动重生；也可 `python -m bridge.cli tool respawn '{}'` |
| 启动客户端报 `Steam requires game restart` | 这是 Steam 版客户端直接启动的限制；本连接器不需要 GUI 客户端。要可视化请通过 Steam 启动客户端加入同一服务器 |

## 许可与致谢

本项目代码为新建实现。架构思想来自：

- [moeru-ai/airi-factorio](https://github.com/moeru-ai/airi-factorio)（MIT）
- 其原始灵感：[naklecha/factorio-automation](https://github.com/naklecha/factorio-automation)

Factorio 是 Wube Software 的商标/作品；本仓库不包含游戏本体或盗版文件。`standalone/` 仅是本机实验用的副本/链接，分发时请删除。