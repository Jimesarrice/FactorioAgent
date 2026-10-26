# 与 Steam 客户端同机共存方案

目标：同一台 Windows 机器上同时运行**人类玩家的 Steam Factorio 客户端**和**LLM Bot 的真实客户端**，且两者都能连接同一个服务器。

结论：**不要让 Steam 客户端启动第二个 Steam 实例**。人类用 Steam 客户端，Bot 用 **standalone（非 Steam）Factorio**，并且做到四件事：

1. 独立 `--config`（write-data）和独立 `player-data.json`；
2. 独立 `--mod-directory`，且 mod 集与服务器完全一致；
3. 独立本地 UDP 端口（Bot 用 `34198`，服务器用 `34197`）；
4. 低画质、窗口化、关闭音频、启动后最小化。

本项目已把这些做成 `BotClient` 的默认/可选参数，并新增 mod 同步与 Steam 构建检测。

---

## 1. 先说失败模式

| 现象 | 根因 | 处理 |
|---|---|---|
| 启动第二个 Steam 客户端失败 / 提示 Steam 相关错误 | Steam 同一 app 单实例、同账号限制、`steam_api64.dll` 依赖 | 第二客户端改用 **standalone** 构建；不要把 Steam 安装目录复制一份当 standalone。**人类客户端从 Steam 启动，不要直接用 Steam 目录的 factorio.exe 传 `--mp-connect` 作为第二实例**（实测 `Steam requires game restart`） |
| `Host address is already in use` / 第二个客户端无法绑定端口 | 两个进程抢 `34197/udp` | Bot 客户端加 `--port 34198`（本项目已默认） |
| 第二个客户端连上后配置/玩家名异常，或启动时文件被锁 | 两个客户端共用 `%APPDATA%\Factorio` | Bot 使用独立 `--config`（`bot-data/config.ini`），玩家数据独立 |
| `ModsMismatch` | 人类 Steam profile 启用了一套 mod，Bot 只加载 base/DLC | `--mod-source` 从 Steam profile 镜像**已启用**的 mod 到 Bot 的 mod 目录 |
| `UserVerificationMissing` | 服务器/Steam Host 开了 `require_user_verification`，Bot 无 Factorio.com 验证 token | 本地 LAN 在服务器/Host 关闭验证，或给 Bot 使用已验证账号 |
| 两个全屏客户端抢焦点/鼠标，Bot 影响人类操作 | 同桌面两个全屏窗口 | Bot 低画质、窗口化、最小化；必要时用第二 Windows 用户会话/RDP 或第二台机器 |
| 帧率低/显存不足/卡顿 | 两个完整客户端吃同一 GPU | `--graphics-quality low --force-graphics-preset very-low --max-texture-size 2048 --disable-audio`；必要时第二机器 |

> 重点区分：**“进程同时存在”**和**“能加入 Steam Host 的游戏”**是两件事。standalone 进程可以和 Steam 客户端同时运行；连不上往往是验证/模组/端口问题，不是 Steam 单实例本身。

---

## 2. 推荐拓扑

```
人类 Steam 客户端 ─┐
                    ├── 专用服务器（headless standalone，34197/udp）
LLM Bot standalone ─┘        │
（独立 config/mod/端口）      └── RCON 127.0.0.1:27017
                                      │
                                MCP / WebUI / LLM loop
```

- 服务器用本项目 headless 方案，**不经过 Steam**；它没有 Steam 单实例问题。
- 人类客户端用 Steam 正常启动、正常加入 `192.168.31.56:34197`。
- Bot 客户端用 standalone，加入同一地址。
- 两者都连接服务器，互相可见；Bot 由 scenario 控制。

如果暂时不想开 headless 服务器，也可以由 Steam 客户端 **Host Game**，Bot 用 standalone 连接。此时必须：

- Host 设置关闭 **Require user verification**（或 Bot 使用已验证账号）；
- Host 与 Bot 的启用 mod 完全一致；
- Bot 用独立的本地端口。

---

## 3. 本项目已加的支持

### 3.1 BotClient 独立端口与 Steam 构建检测

`bridge/bot_client.py`：

- 新参数 `client_port`，默认 **34198**，启动参数里加 `--port 34198`；
- 可选 `--bind`；
- 如果 exe 同目录存在 `steam_api64.dll`，默认拒绝启动并提示改用 standalone；
- 仍保留 `--allow-steam` 逃生口（不推荐）；
- `--mod-source` 可在启动前镜像 mod；
- `--data-dir` / `--mod-dir` 保持独立。

命令行示例：

```powershell
python -m bridge.bot_client `
  --exe "<FACTORIO_DIR>\bin\x64\factorio.exe" `
  --server 192.168.31.56:34197 `
  --name LLM-Bot `
  --client-port 34198 `
  --data-dir "<INSTALL_DIR>\bot-data" `
  --mod-dir "<INSTALL_DIR>\bot-mods" `
  --window-size 800x600 `
  --wait
```

### 3.2 Mod 镜像

如果服务器/Host 启用了额外 mod（实测 Steam Host 曾启用 `Teleporters_2.1.0`，导致 `ModsMismatch`），用：

```powershell
python -m bridge.bot_client `
  --exe "<FACTORIO_DIR>\bin\x64\factorio.exe" `
  --server 192.168.31.56:34197 `
  --name LLM-Bot `
  --data-dir "...\bot-data" `
  --mod-dir "...\bot-mods" `
  --mod-source "$env:APPDATA\Factorio\mods" `
  --wait
```

`sync_mods()` 会：

- 读取源 `mod-list.json`；
- 只复制 **enabled** 的非内置 mod（zip 或目录）；
- 写出目标 `mod-list.json`，保留 base/DLC；
- 缺失的 enabled mod 会明确报错，不会静默带着错误 mod 集连接。

也可以由 WebUI 配置：`client_mod_source` 指向 Steam profile 的 `mods` 目录，启动 Bot 时自动同步。

### 3.3 配置项

`state/webui.json` 的 `bot` 段新增：

```json
{
  "client_exe": "<FACTORIO_DIR>/bin/x64/factorio.exe",
  "client_port": 34198,
  "client_data_dir": "<INSTALL_DIR>/bot-data",
  "client_mod_dir": "<INSTALL_DIR>/bot-mods",
  "client_mod_source": "C:/Users/<you>/AppData/Roaming/Factorio/mods"
}
```

`deploy/configure.py` 也支持：

```powershell
python deploy\configure.py `
  --server-exe "<FACTORIO_DIR>\bin\x64\factorio.exe" `
  --client-exe "<FACTORIO_DIR>\bin\x64\factorio.exe" `
  --client-port 34198 `
  --client-mods "<INSTALL_DIR>\bot-mods" `
  --client-mod-source "$env:APPDATA\Factorio\mods" `
  --rcon-password "***"
```

`--client-mod-source` 可留空（服务器只有 base/DLC 时）。

---

## 4. 两种落地方式

### 4.1 推荐：headless 服务器 + Steam 人类客户端 + standalone Bot

1. 启动项目 headless 服务器：

```powershell
python -m bridge.cli start `
  --exe "<FACTORIO_DIR>\bin\x64\factorio.exe" `
  --save "<INSTALL_DIR>\server\agentbot.zip" `
  --mods "<INSTALL_DIR>\server\scenario-mods" `
  --settings "<INSTALL_DIR>\server\agentbot-server-settings.json" `
  --port 34197 `
  --rcon-bind 127.0.0.1:27017 `
  --rcon-password "test"
```

2. 人类 Steam 客户端加入 `192.168.31.56:34197`。
3. Bot 用 standalone 加入同一地址：

```powershell
python -m bridge.bot_client `
  --exe "<FACTORIO_DIR>\bin\x64\factorio.exe" `
  --server 192.168.31.56:34197 `
  --name LLM-Bot `
  --client-port 34198 `
  --data-dir "<INSTALL_DIR>\bot-data" `
  --mod-dir "<INSTALL_DIR>\server\scenario-mods" `
  --wait
```

4. RCON 绑定 Bot 名：

```powershell
python -m bridge.cli raw '/c remote.call("agentbridge","set_bot_name","LLM-Bot")' --rcon-port 27017 --rcon-password test
```

> 若服务端是在**同一台机器**上，作为人类客户端的 Steam 客户端连接本地服务器通常没有端口问题；Bot 显式用 34198 避免与服务器/人类客户端抢端口。

### 4.2 由 Steam 客户端 Host Game

1. Steam 客户端：Host Game，选择存档。
2. 在 Host 设置中：
   - 关闭 **Require user verification**（本地 LAN 测试）；
   - 确认局域网可见/允许直连；
   - 记下启用的 mod。
3. 关闭 Host 后再启动 Bot 或使用 `--mod-source` 同步 mod；不要在 Host 运行中改 mod。
4. Bot 使用独立 `--client-port 34198`、独立 data/mod 目录连接 `192.168.31.56:34197`。

如果 Host 必须开启验证，Bot 需要一个**已验证的 Factorio.com 账号 token**（写入 Bot 的 `player-data.json` 的 `service-token`），否则会持续 `UserVerificationMissing`。

---

## 5. 输入/窗口隔离

同桌面两个客户端仍可能争夺焦点：

- 本项目 BotClient 启动后默认最小化；不要用 `--no-minimize` 做长时间运行。
- Steam 客户端建议窗口化或无边框，避免独占全屏。
- 如果最小化后 Bot 客户端被系统暂停/降帧，检查 Windows 图形设置里的“后台优化”，或使用第二 Windows 用户会话（RDP）启动 Bot。
- 若两客户端仍互相影响，最终方案是第二台机器/带 GPU 的 Windows VM；本项目协议不需要同机。

---

## 6. 实测记录与边界

- 本机已实测：standalone 客户端与 Steam 客户端进程可同时存在；standalone 客户端可连接 headless 服务端并进入 `InGame`。
- 直接启动 Steam 构建作为第二客户端时，客户端日志出现 `Steam requires game restart, restarting...` 并退出；这是 Steam 构建/单实例行为，不能靠传参绕过。**第二客户端必须是 standalone。**
- 用本项目新的 `BotClient`（standalone、`--client-port 34199`、独立 data/mod）在已有服务器 + 另一 standalone 客户端在线时启动，日志进入 `InGame`，服务端记录 `PlayerJoinGame`；证明多客户端 + 独立端口方案可用。
- 实测失败案例：
  - 连接 Steam Host 时服务器日志 `UserVerificationMissing`（验证开关问题）；
  - Steam Host 启用 `Teleporters` 时出现 `ModsMismatch`（mod 集问题）。
- 由此确认：**同机共存的关键不在绕过 Steam 单实例，而在“standalone 第二客户端 + 独立数据/端口 + 同 mod 集 + 正确验证设置”**。
- 不承诺两个完整客户端在低端 GPU 上流畅；这是硬件/会话隔离问题，不是连接器能消除的。

---

## 7. 相关文件

| 文件 | 作用 |
|---|---|
| `bridge/bot_client.py` | 第二客户端启动、独立配置、端口、最小化、mod 镜像、Steam 构建检测 |
| `bridge/bot_loop.py` | 长时循环中的 client 端口/data/mod 参数 |
| `bridge/settings.py` | `client_port/client_data_dir/client_mod_dir/client_mod_source` 默认值与 WebUI 配置 |
| `deploy/configure.py` | 生成上述本机配置 |
| `docs/REAL-PLAYER-BOT.md` | 真实玩家模式整体说明 |
| `docs/DEPLOYMENT.md` | 分发部署手册 |
