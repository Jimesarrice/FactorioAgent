# 部署与运维手册（分发版）

版本：0.3.9（客户端电力/科研/装配机 + 无人值守循环 + 寻路/挖矿/合成/物资流转 + SDL 输入 + 内存读取）  
适用：Windows 10/11（真实玩家模式）；Linux 可运行 headless 服务端，但第二真实客户端未做完整验证。  
游戏：Factorio **2.1.x**，需要 **Space Age** DLC（真实玩家/太空平台功能依赖它）。

---

## 0. 0.3.9 更新摘要

- 客户端侧**建成电力**：手造泵/锅炉/蒸汽机/杆/实验室，水边用正常建造输入接通水→管→锅炉→蒸汽机；实测锅炉 water/steam、蒸汽机 steam=200、实验室通电。
- **科研走科技树 UI**：Ctrl+F 搜索 automation → 选中 → Start research；实验室 GUI 放 10 红瓶；约 90 秒 `automation` researched=true。
- **装配机配方 GUI**：`client_action_set_recipe` / `client_action_recipe`（客户端 `get_recipe()` 可读）；实测设定 iron gear wheel 后产出 15 齿轮。
- 走路改为轻量两格探针 + 八向脱困，替代 2400 瓦片的网格查询；长时间会话未再崩溃。
- 客户端 MCP **49 个** `client_*` 工具。

## 0. 0.3.8 更新摘要

- 新增 `bridge/client_autopilot.py`：无人值守燃烧时代循环（收矿→装炉→取板→分煤→工单合成→回锚点），可独立 CLI 或 MCP 后台线程运行。
- `entity_insert(half=True)` 右键取半叠，用于给矿钻/熔炉分煤。
- `open_entity(name=...)` 改为小范围悬停搜索后再点击，修复 1×1 容器（落点木箱）偶发选中下方矿的问题；实测一次取回 67 铁矿。
- 实测 8 分钟无人值守：20 tick / 0 错误，收矿 116、取板 115、耗煤 39，齿轮补到 12。
- 客户端 MCP 47 个 `client_*` 工具。
- 已知限制：实体库存无法从客户端 Lua 读取，循环用时间片+背包增量；煤分配为启发式。

## 0. 0.3.7 更新摘要

0.3.7 把客户端侧动作补到**可闭环的后台全自动**（无需窗口焦点/服务端 scenario/RCON）：

- 修复后台 GUI 点击不触发的根因：合成器的按下/松开改为同一游戏线程作业内原子发送（`clickPair`），并把合成按键钉在虚拟光标坐标；真实鼠标事件仍屏蔽。
- 新增 `client_action_craft`（Ctrl+F 搜索 + 点击配方）、`client_action_mine_entity`（伐木/挖石）、`client_action_insert`/`client_action_take`（含 Ctrl+左键快速转移）、`client_action_pick_ground`（F 拾取地面物品）。
- `walk_to` 改为读取客户端瓦片碰撞网格做 BFS，边走边重规划；实测绕过树林与残骸。
- 实测闭环：挖树取木→合成木箱→石炉进矿/进木→8 铁板→铁齿轮→燃烧矿钻放矿上→落点木箱收集→Ctrl+点击取回背包。
- 注意：2.1 燃烧矿钻没有输出槽，产物掉在 `drop_position`；落点被角色占住会状态 38。放箱子或按 F 拾取。
- 客户端 MCP 现为 **44 个** `client_*` 工具。
- 0.3.6 的高层动作、0.3.5 的后台输入/内存、0.3.3 的前台输入、0.3.2 的共存均保留。

## 0. 0.3.6 更新摘要

- `bridge/client_actions.py`：自动退出 remote view；右键长按挖矿，光标移空白地停止；GUI 取背包物品；左键放置建筑；左键打开实体 GUI。
- `client_mcp_server` 新增 11 个 `client_action_*` 工具（当时共 39 个）。
- 0.3.5 的后台只读内存、0.3.3 的前台输入、0.3.2 的共存均保留。

## 0. 0.3.5 更新摘要

0.3.5 新增客户端**后台动作通道**（不依赖服务端 scenario/RCON，不需要窗口前台）：

- `bridge/client_input.py`：Frida SDL 注入。键盘按键/长按/文本通过 SDL keyboard state 发送；虚拟鼠标通过重写 SDL 事件和 SDL mouse state 保持位置，屏蔽真实鼠标干扰。
- `client_mcp_server` 新增 10 个 `client_input_*` 工具，共 **28 个** `client_*` 工具（0.3.6 进一步到 39 个）。
- 已实测：后台 **W/A/S/D 行走**同步到真实服务器；后台虚拟鼠标可定位、悬停/选中实体、点击 GUI（如打开人物界面）；客户端可保持后台/最小化。
- 仍是正常玩家输入，不写角色/背包/位置，不伪造网络包。
- 已知限制：世界目标的长按鼠标动作（手挖、放置建筑）当前客户端动作层未接受；自有服务器请用 scenario 工具，或临时把窗口切前台用旧 `client_*` 工具。
- 0.3.4 的只读内存/Lua 桥、0.3.3 的 Win32 前台输入、0.3.2 的 Steam/standalone 共存均保留。

## 0. 0.3.4 更新摘要

0.3.4 新增客户端**后台只读内存/Lua 桥**：

- `bridge/client_memory.py`：Frida 抓取 Lua state，在游戏线程读取位置/血量/背包/附近资源/实体/研究，不需要窗口焦点。
- `client_mcp_server` 新增 `client_memory_attach/status/observe/inventory/detach`，共 18 个 `client_*` 工具。
- 只读，不写角色/背包/位置；地址按 Factorio 2.1.23 win64，更新版本需换 RVA。
- Frida 为可选依赖（`pip install frida`）。
- `client_input_*` 工具同样依赖 Frida；一次 attach 后保持整个 bot 会话，不要每个动作重连。

0.3.3 的客户端输入通道仍然包含：


- `bridge/client_control.py`：Win32 窗口/键鼠/截图控制。
- `bridge/client_mcp_server.py`：独立 MCP server，49 个 `client_*` 工具（0.3.9 含配方设置），截图可内联返回图片。
- `bridge/client_actions.py`：0.3.9 高层后台动作（寻路/挖矿/伐木/合成/取放物资/放置/打开/设配方）。
- `bridge/client_autopilot.py`：0.3.8 无人值守循环。
- `bridge/client_input.py`：0.3.5 后台 SDL 动作通道（键盘/虚拟鼠标），不要求窗口前台。
- 适用于原版 freeplay Host（例如 204）；输入类工具需要前台，`client_memory_*` 通过 Frida 只读 Lua 桥在后台读取位置/背包/附近资源。
- 文档：[CLIENT-INJECTION.md](CLIENT-INJECTION.md)。

0.3.2 的 Steam 同机共存支持仍然包含：


- 第二客户端必须是 **standalone**；`BotClient` 检测 `steam_api64.dll` 并默认拒绝 Steam 构建，`--allow-steam` 仅作逃生口。
- Bot 客户端默认使用独立本地 UDP 端口 **34198**（服务器 34197），并支持 `--client-port`/`--bind`。
- 新增 `--mod-source`：从 Steam profile 镜像已启用 mod，避免 `ModsMismatch`。
- Bot client 的 `--config`/data/mod 路径统一解析为绝对路径，避免 Factorio 从 `bin\x64` 启动时找不到配置。
- WebUI 设置页新增 client_port/client_data_dir/client_mod_dir/client_mod_source。
- 新增 [COEXISTENCE.md](COEXISTENCE.md)，记录 Steam Host 的 `UserVerificationMissing`、Steam 第二实例 `Steam requires game restart` 等实测失败模式。

0.3.1 的测试修复仍然包含：


- `server/agentbot.zip` 内嵌 `control.lua` 已同步为当前源码（并附带同步的 `agentbot.backup.zip`），不再缺 9 个接口。
- `production_stats` 默认物品表移除流体 `sulfuric-acid`；现在传流体名会返回单项错误，不会让整次查询失败。
- `set_recipe` 明确只适用于 assembling machine（含炼油厂/化工厂）；石炉返回可读的固定配方错误。
- `cancel_job` / `cancel_all` 现在写入 `job_canceled` 事件（含 `reason`），审计日志完整。
- `dismantle_entity` / `rotate_entity` 的远目标错误改为明确提示“256 格内未找到，先走近到 10 格内”；目标扫描半径提升到 256。
- 服务端路径和服务端启动参数会先按调用者 cwd 解析为绝对路径；文档示例也统一使用绝对路径。
- `find_water` 默认半径改为 120；仍找不到时可继续加大。
- 分发包附带本次全流程实测报告 `docs/runs/MCP-FULLFLOW-TEST-2026-10-25.md`。

## 1. 这个包是什么

FactorioAgent 让大模型在**真实运行的 Factorio 服务器**里扮演一名真实玩家：

- 玩家列表里能看到 `LLM-Bot`；
- 通过服务端 scenario + RCON 控制角色，不需要给客户端装 mod；
- 支持走路、挖矿、手搓、建造、拆除、旋转、熔炼、研究、蓝图、太空平台；
- 支持 OpenAI-compatible 云端模型和本地 Ollama/LM Studio；
- 附带 Web 控制台和 MCP stdio server。

它不是 Factorio 引擎重写，也不是 UDP 协议伪造客户端。详见 `docs/PROTOCOL.md`、`docs/REWRITE-FEASIBILITY.md`。

### 两种运行模式

| 模式 | 身体 | 玩家列表可见 | 能力 | 适用 |
|---|---|---|---|---|
| **真实玩家模式（推荐）** | 第二个真实 Factorio 客户端 | 是 | 正常玩家全部能力（蓝图/太空平台/GUI） | 让其他人看到 Bot、完整游玩 |
| **裸角色实验模式（Lab）** | 服务端 mod 创建的 `character` | 否 | 基础移动/挖矿/建造/任务 | 单机实验、低成本调试 |

分发版默认按真实玩家模式配置。Lab 模式需要 `mods/agentbridge` 和 `server/lab.zip`。

---

## 2. 分发包内容

```
FactorioAgent-0.3.9/
├─ README.md                    项目说明
├─ VERSION                     版本号
├─ LICENSE                     MIT
├─ requirements.txt            说明：无第三方 Python 依赖
├─ bridge/                     Python 连接器（stdlib，无 pip 依赖）
├─ webui/                      Web 控制台静态资源
├─ deploy/
│  ├─ configure.py             生成本机 state/webui.json
│  └─ Start-WebUI.bat          Windows 一键打开控制台
├─ mods/agentbridge/           Lab 模式 mod（真实玩家模式不用）
├─ scenarios/agentbot/         真实玩家 scenario 源码
├─ server/
│  ├─ agentbot.zip             干净的真实玩家示例存档（含 scenario）
│  ├─ agentbot.backup.zip      与 agentbot.zip 同步的干净回滚副本
│  ├─ lab.zip                  Lab 示例存档
│  ├─ agentbot-server-settings.json
│  ├─ lab-server-settings.json
│  └─ scenario-mods/           只含 base/DLC 的服务端 mod 列表
├─ docs/                       协议、架构、MCP、WebUI、部署、测试报告、实战笔记
├─ ops/                        诊断/蓝图辅助脚本（可选）
├─ tests/                      RCON/MCP/冒烟测试（可选）
├─ state/                      运行时生成（空目录/模板）
└─ server-data/                可选的服务端 write-data（空目录）
```

分发包**不包含** Factorio 游戏文件、Steam 客户端、用户存档、API key、日志、`bot-data/`、`server-data/` 的运行数据。`server/agentbot.zip` 是项目自带的干净 starting map，可直接用作示例；正式使用请先备份并复制到可写目录。

---

## 3. 前置条件

### 3.1 必需

- Factorio **2.1.x**，带 Space Age DLC。
- 一个可运行的 **standalone** Factorio 客户端（真实玩家模式需要第二个客户端作为身体）。
  - 不建议用 Steam 版启动第二个实例：Steam 通常限制同账号多实例，且可能报 `Steam requires game restart`。
  - 你的正常客户端可以用 Steam；Bot 身体用 standalone。
- Python **3.10+**（Windows 建议 3.11/3.12）。
- 可写目录（不要放在 `Program Files` 下，除非已处理权限）。
- 空闲端口：`34197/udp`（游戏）、`27017/tcp`（真实玩家 RCON）、`8090/tcp`（Web 控制台，仅本机）。

### 3.2 检查 Python

```powershell
python --version
python -c "import sys; print(sys.executable)"
```

本包核心**没有第三方 pip 依赖**；不需要 `pip install -r requirements.txt`。`requirements.txt` 仅用于说明。

可选：需要**后台客户端内存/Lua 读取**时安装 Frida：

```powershell
python -m pip install frida
```

不安装时输入类 `client_*` 工具仍可用；`client_memory_*` 会报缺少 frida。

### 3.3 检查 Factorio

```powershell
& "C:\Factorio\bin\x64\factorio.exe" --version
```

记下这个路径，后面配置用。服务端和 Bot 客户端可以指向**同一个** standalone 安装的不同进程；Bot 客户端会用独立的 `bot-data/` 作为 write-data，不会污染你的正常存档。

---

## 4. 安装

### 4.1 解压

解压到例如：

```
C:\FactorioAgent
```

确认目录下能看到 `bridge\`、`webui\`、`server\agentbot.zip`、`deploy\configure.py`。

### 4.2 生成配置

在包根目录打开 PowerShell：

```powershell
cd C:\FactorioAgent
python deploy\configure.py `
  --server-exe "C:\Factorio\bin\x64\factorio.exe" `
  --client-exe "C:\Factorio\bin\x64\factorio.exe" `
  --rcon-password "请换成你自己的强密码"
```

它会：

- 写入 `state/webui.json`；
- 创建 `state/`、`state/blueprints/`、`bot-data/`、`server-data/saves/`、`server-data/temp/`；
- 校验可执行文件、存档、mod 目录和服务端设置；
- 打印 RCON 密码和 Web 控制台地址。

如果不传 `--rcon-password`，脚本会生成随机密码并打印。**这个密码必须与启动服务端时的 `--rcon-password` 一致**；之后改配置要重启服务端。

检查：

```powershell
python deploy\configure.py --check
```

### 4.3 备份示例存档

首次启动会把示例存档当作可写存档使用（自动存档会写在旁边）。分发版已附带同步的 `agentbot.backup.zip`，也可再复制一份：

```powershell
Copy-Item server\agentbot.zip server\agentbot.backup.zip
```

以后想回到干净起点，用备份替换即可。

---

## 5. 配置文件参考

### 5.1 `state/webui.json`

由 `deploy/configure.py` 生成，WebUI 和内置 bot 循环共用。关键字段：

```json
{
  "llm": {
    "provider": "auto",
    "local_base_url": "http://127.0.0.1:11434/v1",
    "local_model": "Q3.5-9B:latest",
    "local_api_key": "",
    "cloud_base_url": "https://api.openai.com/v1",
    "cloud_model": "gpt-4o-mini",
    "cloud_api_key": "",
    "fallback_cloud": true,
    "temperature": 0.2
  },
  "bot": {
    "server_exe": "C:/Factorio/bin/x64/factorio.exe",
    "client_exe": "C:/Factorio/bin/x64/factorio.exe",
    "server_save": "C:/FactorioAgent/server/agentbot.zip",
    "server_mods": "C:/FactorioAgent/server/scenario-mods",
    "server_settings": "C:/FactorioAgent/server/agentbot-server-settings.json",
    "server_config": "",
    "rcon_port": 27017,
    "rcon_password": "YOUR_PASSWORD",
    "host": "127.0.0.1",
    "player_name": "LLM-Bot",
    "start_server": true,
    "start_client": true,
    "turn_based": true,
    "interval": 8.0,
    "turns": 8,
    "goal": "从零开始完成 Space Age，最终抵达 Shattered Planet"
  },
  "webui": {"host": "127.0.0.1", "port": 8090}
}
```

安全说明：

- `state/webui.json` 以**明文**保存本地/云端 API key 和 RCON 密码；
- 不要提交到 Git、不要发给别人；
- Web 控制台默认只绑定 `127.0.0.1`；
- 如果必须多人共用，使用反向代理 + 认证，并限制来源 IP。

### 5.2 环境变量

配置优先级：命令行/JSON 显式值 > 环境变量 > 代码默认值。

| 变量 | 作用 |
|---|---|
| `FACTORIO_EXE` | 服务端 Factorio 可执行文件 |
| `FACTORIO_CLIENT_EXE` | Bot 客户端可执行文件（不设则用 `FACTORIO_EXE`） |
| `FACTORIO_SAVE` | 服务端存档路径 |
| `FACTORIO_MODS` | 服务端 mod 目录 |
| `FACTORIO_SETTINGS` | 服务端 `server-settings.json` |
| `FACTORIO_CONFIG` | 可选的 Factorio `--config`（独立 write-data） |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` | 云端 LLM 回退 |
| `LOCAL_LLM_BASE_URL` / `LOCAL_LLM_MODEL` | 本地 LLM 回退 |
| `LLM_PROVIDER` | `auto` / `local` / `cloud` |

### 5.3 服务端设置

`server/agentbot-server-settings.json` 已包含关键项：

```json
{
  "auto_pause": false,
  "auto_pause_when_players_connect": false,
  "allow_commands": "true",
  "visibility": {"public": false, "lan": true},
  "require_user_verification": false,
  "max_players": 16,
  "autosave_interval": 15,
  "autosave_slots": 3
}
```

- `auto_pause` **必须为 false**：没有玩家时世界仍要 tick，否则 Bot 的 job 会冻结。
- `allow_commands` 为 `"true"` 时局域网玩家可用控制台命令；私有 LAN 可接受，公开服务器建议改 `"admins-only"` 并只给信任玩家 admin。
- 公开服务器请额外设置 `game_password`、`public: true`、`require_user_verification: true`，并做端口转发/防火墙；本项目默认只面向本机/局域网。

### 5.4 端口

| 端口 | 协议 | 用途 | 暴露建议 |
|---|---|---|---|
| `34197` | UDP | Factorio 游戏 | 仅 LAN 或受控端口转发 |
| `27017` | TCP | 真实玩家 RCON | **只绑 127.0.0.1** |
| `27016` | TCP | Lab 模式 RCON | 只绑 127.0.0.1 |
| `8090` | TCP | Web 控制台 | 只绑 127.0.0.1 |

启动服务端时建议加：

```text
--rcon-bind 127.0.0.1:27017
```

不要向公网开放 RCON；RCON 一旦泄露，等同于服务器管理员权限。

---

## 6. 真实玩家模式：完整启动顺序

以下命令均在包根目录 `C:\FactorioAgent` 执行。

### 6.1 方式 A：WebUI 一键管理（推荐新用户）

1. 打开控制台：

```powershell
python -m bridge.webui
```

或双击 `deploy\Start-WebUI.bat`。

2. 浏览器打开 `http://127.0.0.1:8090`。
3. 在 **Settings** 确认：
   - `server_exe` / `client_exe`；
   - `server_save` = `<安装目录>/server/agentbot.zip`；
   - `server_mods` = `<安装目录>/server/scenario-mods`；
   - `server_settings` = `<安装目录>/server/agentbot-server-settings.json`；
   - `rcon_port` = `27017`，密码与配置一致；
   - `start_server`、`start_client` 勾选。
4. 选择 provider（本地 Ollama / 云端），填模型名和 API key（本地模型通常不需要 key）。
5. 点击 **Start Bot**。它会依次启动服务端、Bot 客户端、LLM 循环。
6. 在 Dashboard 观察 `player connected`、背包、job、研究进度。
7. 停止时点击 **Stop Bot**；它会先停 LLM 循环，再停客户端/服务端并保存。

如果服务端/客户端是你手动启动的，把 `start_server`、`start_client` 设为 `false`，只让 WebUI 运行 LLM 循环，避免重复启动。

### 6.2 方式 B：手动分步（便于排查）

#### 第 1 步：启动服务端

```powershell
python -m bridge.cli start `
  --exe "C:\Factorio\bin\x64\factorio.exe" `
  --save "C:\FactorioAgent\server\agentbot.zip" `
  --mods "C:\FactorioAgent\server\scenario-mods" `
  --settings "C:\FactorioAgent\server\agentbot-server-settings.json" `
  --rcon-bind "127.0.0.1:27017" `
  --rcon-password "你的RCON密码"
```

看到：

```text
server ready: RCON 127.0.0.1:27017, game UDP :34197
```

说明服务端已启动。日志在 `server/server-stdout.log` 和 `server/console.log`。

> 如果使用独立 write-data，追加 `--config "C:\FactorioAgent\server-data\config.ini"`。不传则使用 Factorio 默认配置。

#### 第 2 步：启动 Bot 身体（第二个真实客户端）

```powershell
python -m bridge.bot_client `
  --exe "C:\Factorio\bin\x64\factorio.exe" `
  --server 127.0.0.1:34197 `
  --name LLM-Bot `
  --wait
```

- 客户端会以 `800x600`、very-low 图形、独立 `bot-data/` 启动；
- `--wait` 会等 scenario 报告 `LLM-Bot` 已连接；
- 日志在 `server/bot-client.log`；
- 不想自动最小化加 `--no-minimize`。

也可以不手动启动，交给 `bridge.cli bot --start-client`（见第 4 步）。

#### 第 3 步：检查玩家和状态

```powershell
python -m bridge.cli observe --rcon-port 27017 --rcon-password "你的RCON密码"
python -m bridge.cli state --rcon-port 27017 --rcon-password "你的RCON密码"
```

应看到 `player.connected=true`、`player.name="LLM-Bot"`。如果只是裸角色 Lab 模式，不会出现在玩家列表，这是正常的。

#### 第 4 步：启动 LLM 循环

```powershell
$env:OPENAI_API_KEY="sk-..."          # 云端；本地 Ollama 可留空
$env:OPENAI_MODEL="gpt-4o-mini"

python -m bridge.cli bot `
  --start-server --start-client `
  --client-exe "C:\Factorio\bin\x64\factorio.exe" `
  --rcon-port 27017 `
  --rcon-password "你的RCON密码" `
  --player-name LLM-Bot `
  --goal "从零开始完成 Space Age，最终抵达 Shattered Planet" `
  --interval 8 --turns 8 --turn-based
```

若服务端/客户端已手动启动，去掉 `--start-server --start-client`。

> `--turn-based` 会在模型思考时暂停游戏、执行动作时恢复。慢模型建议开启；实时模型可关闭。

#### 第 5 步：MCP（可选，替代内置 LLM 循环）

先启动服务端和 Bot 客户端，再配置 MCP 客户端。示例见 `docs/mcp-config.example.json`：

```json
{
  "mcpServers": {
    "factorio": {
      "command": "python",
      "args": ["-m", "bridge.mcp_server"],
      "cwd": "<ABSOLUTE_PATH_TO_FactorioAgent>",
      "env": {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    }
  }
}
```

把 `cwd` 替换成你的安装绝对路径。MCP server 会自动读取 `state/webui.json` 的 RCON 地址和密码；也可显式传 `--port 27017 --password ...`。

**不要同时运行内置 `bridge.cli bot` 和 MCP 客户端**：两者都会向同一个玩家提交 job，会互相抢控制。选一个作为“大脑”。

---

## 7. Lab 裸角色模式（可选）

适合没有第二客户端、只做实验的场景。

1. 服务端使用 Lab 存档和 `mods/agentbridge`：

```powershell
python -m bridge.cli start `
  --exe "C:\Factorio\bin\x64\factorio.exe" `
  --save "C:\FactorioAgent\server\lab.zip" `
  --mods "C:\FactorioAgent\mods" `
  --settings "C:\FactorioAgent\server\lab-server-settings.json" `
  --rcon-bind "127.0.0.1:27016" `
  --rcon-password "lab-password"
```

2. 用 `--rcon-port 27016` 执行 `observe/state/tool`。
3. 裸角色不在玩家列表里，不能使用蓝图/太空平台；这是引擎约束，不是 bug。

Lab 存档是新地图时，可能需要初始化起始科技：

```powershell
python -m bridge.cli init-lab --rcon-port 27016 --rcon-password "lab-password"
```

---

## 8. LLM 配置

### 8.1 云端

任意 OpenAI-compatible `/chat/completions`：

```text
provider = cloud
base_url = https://api.openai.com/v1       # 或 DeepSeek/Qwen 兼容端点
model    = gpt-4o-mini
api_key  = sk-...
```

环境变量也可：

```powershell
$env:OPENAI_API_KEY="sk-..."
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
$env:OPENAI_MODEL="gpt-4o-mini"
```

### 8.2 本地

Ollama 默认：

```text
provider = local
base_url = http://127.0.0.1:11434/v1
model    = Q3.5-9B:latest
```

LM Studio：`http://127.0.0.1:1234/v1`；llama.cpp：`http://127.0.0.1:8080/v1`；vLLM：`http://127.0.0.1:8000/v1`。

要求模型支持 **tool calling**。只回 reasoning、不回 tool_calls 的模型会导致循环空转；此时换模型或开启云端回退。

`provider=auto` 会先试本地，失败或没有工具调用时回退云端（`fallback_cloud=true`）。

---

## 9. MCP 工具面

MCP server 提供 **53 个工具**，覆盖：

- 感知：`decision_context`、`observe`、`get_state`、`scan`、`nearby_entities`、`find_water`、`recipe_info`、`recipes_query`、`technologies`、`tech_tree`、`entity_detail`、`production_stats`、`alerts`、`resource_patches`、`get_inbox`、`get_events`、`get_blueprints`、`get_platforms`；
- 动作：`walk_to`、`mine`、`craft`、`place`、`insert_item`、`take_item`、`rotate_entity`、`dismantle_entity`、`research`、`set_recipe`、`build_entities`、`wire_poles`、`wait`、`say`；
- 蓝图/太空：`blueprint_create`、`blueprint_build`、`build_blueprint`、`space`；
- 控制：`submit_job`、`wait_job`、`wait_idle`、`cancel_job`、`cancel_all`、`instruct`、`clear_inbox`、`pause`、`resume`、`set_speed`、`save`、`respawn`；
- 运维：`ping`、`set_bot_name`、`set_bare`、`set_eval`、`lua_eval`。

完整说明见 `docs/MCP.md`。`lua_eval` 默认关闭；它能绕过正常玩家约束，不要给不受信任的模型开启。

---

## 10. 验证清单

按顺序做完，任何一步失败先看日志。

1. **Python 导入**

```powershell
python -c "import bridge.agent, bridge.webui, bridge.mcp_server; print('imports ok')"
```

2. **MCP 协议/工具数**（不需要服务端）

```powershell
python tests\mcp_smoke.py
```

应输出 `PASS initialize ... tools=53` 和 `ALL PASS`。

3. **服务端 RCON**

```powershell
python -m bridge.cli observe --rcon-port 27017 --rcon-password "你的密码"
```

4. **真实玩家可见**

`state` 里 `player.connected=true` 且 `player.name=LLM-Bot`。在正常客户端玩家列表也应看到 `LLM-Bot`。

5. **只读工具自检**（服务端 + 客户端已启动）

```powershell
python tests\mcp_smoke.py --live
```

覆盖 `ping/get_state/decision_context/observe/nearby_entities/find_water/recipe_info/technologies/get_blueprints/get_platforms`。

6. **WebUI**

打开 `http://127.0.0.1:8090`，Dashboard 应显示 RCON 正常、玩家、背包、日志；Settings 保存后刷新仍生效。

7. **动作冒烟**

在游戏里让 Bot 走一小段、挖 1 个石头；或通过 MCP 调 `walk_to`。确认位置/背包变化，且另一个客户端能看到。

---

## 11. 日常运维

### 11.1 保存与停止

```powershell
python -m bridge.cli stop --rcon-port 27017 --rcon-password "你的密码"
```

它会先 `save` 再 `/quit`。不要直接杀进程；直接杀可能丢失最近进度（虽然有自动存档）。

### 11.2 备份

需要备份：

- `server/agentbot.zip`（或你实际使用的存档）；
- `state/webui.json`（含配置/密钥，注意保密）；
- `state/blueprints/`；
- 自定义的服务端设置/地图生成设置。

不需要备份 `bot-data/`、日志、`server-data/temp/`。

### 11.3 自动存档

`autosave_interval=15` 分钟、`autosave_slots=3`，在存档同目录生成 `_autosave1..3.zip`。长时运行建议另配备份脚本。

### 11.4 升级

1. 停止 Bot 和服务端；
2. 备份存档、`state/webui.json`、蓝图；
3. 解压新版本到新目录；
4. 用 `deploy/configure.py` 重新生成本机配置（或把旧 `state/webui.json` 复制到新目录）；
5. 替换存档前先确认 scenario 版本兼容；
6. 运行验证清单。

**scenario 源码与存档内嵌副本**：`scenarios/agentbot/control.lua` 是源码，`server/agentbot.zip` 内也有 `agentbot/control.lua`。只改源码不会影响已有存档；新地图/重建存档的方法见 `docs/REAL-PLAYER-BOT.md` 第 9.2 节。不要直接在运行中的存档上覆盖 scenario 文件。

### 11.5 修改 scenario 后重建干净存档

概览（完整步骤见 `docs/REAL-PLAYER-BOT.md`）：

1. 把 `scenarios/agentbot/control.lua` 复制到 `server-data/scenarios/agentbot/control.lua`；
2. 用 `--start-server-load-scenario agentbot` 启动一张新地图；
3. RCON/控制台 `game.server_save()`，再 `/quit`；
4. 用新生成的 `server-data/saves/agentbot.zip` 替换交付存档；
5. 保持存档为“无玩家”的干净起点，首次加入时再创建 crash site/起始物资。

---

## 12. 安全

- **RCON 密码**：至少 16 位随机字符；不要用示例密码；不要暴露到公网。启动时用 `--rcon-bind 127.0.0.1:27017`。
- **WebUI**：只绑 `127.0.0.1`；不要在路由器上转发 8090。它没有内置登录认证。
- **API key**：`state/webui.json` 明文保存；使用文件系统权限限制；不要把该文件提交到 Git 或发给他人。
- **`allow_commands`**：公开服务器改 `"admins-only"`；只给信任玩家 admin。
- **`lua_eval`**：默认关闭。开启后模型可创建物品/传送/改研究，等于作弊/管理员权限。只在你信任模型和操作者时开启。
- **公开服务器**：默认配置只面向本机/LAN；公开前必须设置游戏密码、用户验证、白名单/防火墙，并评估风险。
- **客户端数据**：`bot-data/player-data.json` 含 Bot 账号信息；不要分发。
- **Factorio 许可**：本包不包含 Factorio 游戏文件；使用者需自行合法获取 Factorio 和 Space Age。

---

## 13. 常见问题

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `RCON port ... did not open` | 服务端启动失败/端口占用/密码不影响端口 | 看 `server/server-stdout.log`；换端口；确认 Factorio 进程未退出 |
| `Connection refused` / `WinError 10061` | RCON 端口错、服务端没起、防火墙 | 真实玩家用 27017，Lab 用 27016；本机先测 `Test-NetConnection 127.0.0.1 -Port 27017` |
| 玩家列表看不到 Bot | 用了 Lab 模式 / 客户端没连上 | 真实玩家模式需要第二个真实客户端；看 `server/bot-client.log` |
| 玩家名为空 | 只写了 `username`，没写 `service-username` | `BotClient` 已同时写；不要手工改 `player-data.json` |
| 客户端报 mod 不匹配 | 正常客户端装了额外 mod / 服务端 mod 集不同 | 用干净 profile（只 base/DLC）；真实玩家服务端用 `server/scenario-mods` |
| 世界不推进 | `auto_pause=true` 或没有玩家且 auto_pause | 设 `auto_pause=false`；重启服务端 |
| `full_output` / 机器停 | 下游满、输出箱满、管道堵 | 看 `entity_detail`、加输出箱/下游，先清堵 |
| `production_stats` 报 Unknown item | 传入了流体名（如 `sulfuric-acid`） | 只传物品名；省略 `items` 会用安全默认物品表 |
| `set_recipe` 报不能设配方 | 目标是石炉等固定配方设备 | 该工具只支持 assembling machine（含炼油厂/化工厂）；石炉需要换装配机 |
| `dismantle_entity` 报目标太远 | 目标不在 10 格内 | 先 `walk_to` 到目标附近；现在会明确提示距离/范围 |
| 模型不回 tool_calls | 模型不支持工具调用 / 端点错 | 换模型；检查 `/v1/models`；开启云端回退 |
| WebUI 显示 `EXITED 1` | 配置路径/API key/服务端状态错 | 看 `state/webui-bot.out` 和 Dashboard 日志 |
| `lua_eval` 被拒绝 | eval 未开启 | 默认关闭；确认风险后再开 |
| `client_memory_attach` 失败 | 未安装 frida / PID 错 / 游戏未进图 | `pip install frida`；`client_list_windows` 核对 PID；进图后再试 |
| `client_input_attach` 失败 | 未安装 frida / PID 错 / 文件被破坏 | `pip install frida`；重新解压分发包，确认 `bridge/client_input.py` 不是 0 字节且无 null 字节 |
| `client_input_*` 报 `Errno 22` / `null bytes` | 源码文件被磁盘/杀软损坏 | 用分发包重新覆盖 `bridge/`；校验 zip 的 SHA256；必要时换本地盘工作 |
| 后台鼠标能选中但不能手挖/放置 | 世界长按动作尚未被客户端动作层接受 | 自有服务器用 scenario 挖矿/建造工具；或临时前台使用 `client_click` 长按 |
| 高倍速客户端掉线 | 网络/客户端跟不上 | 降低 `set_speed`（实测 50 会掉线，20 较稳） |
| 中文乱码 | Windows 控制台编码 | 设 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`，或 `chcp 65001` |
| 存档被写坏/无法启动 | 直接杀进程/磁盘满/并发写 | 用自动存档恢复；停止时用 `bridge.cli stop` |
| 端口被占用 | 另一个 Factorio/旧进程 | `Get-NetTCPConnection -LocalPort 27017`；结束旧进程或换端口 |

日志位置：

- 服务端 stdout：`server/server-stdout.log`
- 服务端控制台：`server/console.log`
- Bot 客户端：`server/bot-client.log`
- WebUI/Bot 循环：`state/webui-bot.out`
- 事件：`state/bot-events.jsonl`

---

## 14. 已知限制

- 本包不重写 Factorio 引擎，不伪造 UDP 客户端；只能连自己的服务器。
- 真实玩家模式必须有一个真实客户端作为身体；没有客户端就没有 `LuaPlayer`。
- 一个服务端建议只接一个 Bot 大脑（内置循环或 MCP 二选一）。
- `production_stats` 只接受物品名，不接受流体名；省略 `items` 时使用安全默认表。
- `set_recipe` 只适用于 assembling machine（含炼油厂/化学厂）；石炉是固定配方。
- `dismantle_entity`/`rotate_entity` 需在 10 格内；远距离会返回明确错误而不是自动寻路。
- `cancel_job`/`cancel_all` 现在会写 `job_canceled` 事件（含 `reason`），便于审计。
- 载具/火车/蜘蛛机甲、GUI-only 操作、复杂蓝图模块/燃料/线缆参数尚未封装成高层工具；可用 `lua_eval` 补，但默认关闭。
- 0.3.7 客户端后台动作已闭环（合成/伐木/物资流转/瓦片寻路）；后台右键 up 不清除客户端输入状态，用“光标移空白地 + 原子点击对”停止；2.1 燃烧矿钻无输出槽，产物掉地面。
- 完整 Space Age 通关（到 Shattered Planet）是模型规划/长时记忆/错误恢复问题，连接器提供能力面，不保证任意模型能通关。
- 本机同 GPU 同时跑正常客户端 + Bot 客户端会有性能开销；建议低画质/最小化。
- Linux 下 headless 服务端可用；第二真实客户端的窗口/最小化逻辑主要按 Windows 编写，未完整验证。

---

## 15. 分发包校验

每个发布 zip 旁会提供：

- `FactorioAgent-0.3.9.zip`
- `FactorioAgent-0.3.9.zip.sha256`
- `MANIFEST.txt`（包内）

Windows 校验：

```powershell
Get-FileHash .\FactorioAgent-0.3.9.zip -Algorithm SHA256
Get-Content .\FactorioAgent-0.3.9.zip.sha256
```

Linux/macOS：

```bash
sha256sum FactorioAgent-0.3.9.zip
```

---

## 16. 命令速查

> 服务端命令请使用**绝对路径**。`bridge/server.py` 现在会先按调用者 cwd 解析相对路径，但 Factorio 自身的工作目录是 `bin\x64`，依赖相对路径容易踩坑。

```powershell
# 配置/检查
python deploy\configure.py --server-exe "C:\Factorio\bin\x64\factorio.exe" --client-exe "C:\Factorio\bin\x64\factorio.exe" --rcon-password "***"
python deploy\configure.py --check

# 服务端（真实玩家）
python -m bridge.cli start --exe "C:\Factorio\bin\x64\factorio.exe" --save "C:\FactorioAgent\server\agentbot.zip" --mods "C:\FactorioAgent\server\scenario-mods" --settings "C:\FactorioAgent\server\agentbot-server-settings.json" --rcon-bind 127.0.0.1:27017 --rcon-password "***"

# Bot 客户端
python -m bridge.bot_client --exe "C:\Factorio\bin\x64\factorio.exe" --server 127.0.0.1:34197 --name LLM-Bot --wait

# 状态/工具
python -m bridge.cli observe --rcon-port 27017 --rcon-password "***"
python -m bridge.cli state --rcon-port 27017 --rcon-password "***"
python -m bridge.cli tool walk_to '{"x":10,"y":10}' --rcon-port 27017 --rcon-password "***"

# WebUI
python -m bridge.webui
# 或 deploy\Start-WebUI.bat

# MCP
python -m bridge.mcp_server --port 27017 --password "***"

# 自检
python tests\mcp_smoke.py
python tests\mcp_smoke.py --live

# 停止
python -m bridge.cli stop --rcon-port 27017 --rcon-password "***"
```

---

## 17. 相关文档

- [README](../README.md)
- [真实玩家模式细节](REAL-PLAYER-BOT.md)
- [与 Steam 客户端同机共存方案](COEXISTENCE.md)
- [无服务端 scenario/RCON 的客户端输入通道](CLIENT-INJECTION.md)
- [MCP 工具与客户端配置](MCP.md)
- [Web 控制台](WEBUI.md)
- [架构](ARCHITECTURE.md)
- [协议与接入面](PROTOCOL.md)
- [测试报告](TEST-REPORT.md)
- [MCP 全流程实测报告](runs/MCP-FULLFLOW-TEST-2026-10-25.md)
- [LLM 实战决策速查](runs/LLM-DECISION-NOTES.md)

如部署中遇到本手册未覆盖的问题，先保留 `server/*.log`、`state/webui-bot.out`、`state/webui.json`（脱敏后）和复现命令，再提交 issue。
