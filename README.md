# FactorioAgent 0.3.5（分发版）

让大模型在真实 Factorio 服务器里扮演一名**真实玩家**。不需要重写游戏，不需要给客户端装 mod；服务端用 scenario + RCON，第二个真实客户端作为 Bot 的身体。

## 先读这个

完整安装、配置、启动、验证和排障请看：

- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**（部署主文档）

## 5 分钟起步

1. 解压到一个可写目录，例如 `C:\FactorioAgent`。
2. 确认已安装 Python 3.10+、Factorio 2.1.x + Space Age、以及一个 standalone Factorio 客户端。
3. 在包根目录运行：

```powershell
python deploy\configure.py `
  --server-exe "C:\Factorio\bin\x64\factorio.exe" `
  --client-exe "C:\Factorio\bin\x64\factorio.exe" `
  --rcon-password "换成你自己的强密码"
```

4. 打开 Web 控制台：

```powershell
python -m bridge.webui
```

浏览器访问 `http://127.0.0.1:8090`，在 Settings 选择本地/云端模型，然后 Start Bot。
默认会使用 `server/agentbot.zip`、`server/scenario-mods` 和 `server/agentbot-server-settings.json`。

5. 验证：

```powershell
python tests\mcp_smoke.py
python -m bridge.cli observe --rcon-port 27017 --rcon-password "你的密码"
```

## 0.3.5 更新

- 新增客户端只读内存/Lua 桥（Frida）：后台读取位置、血量、背包、附近资源/实体/研究，不需要窗口焦点；MCP 提供 `client_memory_*`。
- 客户端 MCP 扩展为 **28 个 `client_*` 工具**：新增 0.3.5 **后台 SDL 动作通道**（`client_input_*`）。后台键盘（行走/按键/文本）和虚拟鼠标（定位、悬停/选择、GUI 点击）不需要窗口前台/焦点，也不依赖服务端 scenario/RCON；已验证后台行走会同步到真实服务器。
- 已知限制：世界目标的长按鼠标动作（手挖、放置建筑）尚未被客户端动作层接受；自有服务器请用 scenario 工具，或临时前台使用旧 `client_*` 工具。详见 `docs/CLIENT-INJECTION.md`。

## 0.3.3 更新

- 新增无服务端 scenario/RCON 的**客户端输入通道**：`python -m bridge.client_mcp_server`，13 个 `client_*` 工具，使用正常键鼠输入与截图，不修改内存/游戏状态。详见 `docs/CLIENT-INJECTION.md`。

## 0.3.2 更新

- 修正分发包示例存档内嵌的旧 scenario（含 9 个缺失接口），并提供同步备份。
- `production_stats` 默认不再误传流体；`set_recipe` 明确仅装配机；取消任务写入事件。
- 路径/启动示例改为绝对路径，`find_water` 默认半径 120。
- 新增 Steam 同机共存方案：standalone 第二客户端、独立端口 34198、mod 镜像、Steam 构建检测；详见 `docs/COEXISTENCE.md`。

## 重要安全提示

- `state/webui.json` 明文保存 RCON 密码和 API key，不要提交/分享。
- RCON 和 WebUI 只绑定 `127.0.0.1`；不要暴露到公网。
- 默认 `lua_eval` 关闭；开启等于给模型管理员/作弊权限。
- 本包不包含 Factorio 游戏文件；请自行合法获取。

## 已验证范围

真实玩家可见、标准 Space Age 开局、走路/挖矿/手搓/真实建造、双客户端同步、蓝图即时建造、太空平台创建/进入/落地、Web 控制台、MCP 53 工具、Ollama tool-calling 均已实测。完整 Space Age 长时自主通关仍需继续验证，详见 `docs/TEST-REPORT.md` 和 `docs/REAL-PLAYER-BOT.md`。
