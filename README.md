# FactorioAgent 0.3.8（分发版）

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

## 0.3.8 更新

- 新增 `bridge/client_autopilot.py`：**无人值守燃烧时代循环**。按 tick 自动收矿（落点木箱）→ 装炉 → 取板 → 在矿钻/熔炉之间分配煤 → 按工单手工合成 → 偏离时走回锚点；支持独立 CLI 与客户端 MCP 的 `client_auto_start/status/stop`（后台线程）。
- `entity_insert(..., half=True)`：右键取半叠，便于把一摞煤分给两台设备。
- 实测：走到 122 格外的煤矿手挖 40 煤运回，启动 **8 分钟循环**：20 个 tick、0 错误，收矿 116、装炉 116、取板 115、耗煤 39，铁齿轮按工单补到 12 个；结束时背包 **192 铁板 / 12 齿轮**，熔炉仍在工作。日志与 `state/autopilot_state.json` 记录每 tick 计数。
- 客户端 MCP 现为 **47 个工具**。
- 稳定性修复：①同一进程只允许一个输入会话（`state/client_input.lock`；两个 SDL hook 并存会让客户端崩溃）；②初始化时自动建立键盘焦点（重启后焦点为 0，注入文字会丢失）；③用 `inv[i].name` 精确定位背包槽（`get_slot` 仍不可用），取物不再误拿/放回失败；合成加 `expect` 校验并在被吞搜索时重试。
- 说明：实体库存无法通过客户端 Lua 读取（硬错误），循环以时间片+玩家背包增量校验；有 scenario/RCON 时建议并行观察真实库存。

## 0.3.7 更新

- **修复后台 GUI 点击不生效的根因**：SDL 在合成按下与松开之间会被真实鼠标事件清掉按键状态，导致“松开”事件根本不产生（GUI 按钮要抬起才触发）。`ClientInput.click()` 改为在**同一个游戏线程作业内**原子地发送 down+up（`clickPair`），并把合成的按键事件钉在虚拟光标坐标上；实测关闭窗口、点配方、点背包格子全部可用。
- **后台手工合成**：新增 `client_action_craft` / `ClientActions.craft()`——E 打开角色界面、Ctrl+F 搜索配方、Ctrl+A 替换查询、点击第一个结果；实测合成木箱、铁齿轮。
- **实体物资流转**：新增 `client_action_insert` / `client_action_take` / `client_action_pick_ground`。插入用光标法（从角色面板取一叠→点实体槽位）；取出用 Factorio 的 **Ctrl+左键快速转移**（实测把熔炉 8 块铁板、箱子 6 块铁矿转入背包）。内置石炉/燃烧矿钻/木箱的槽位坐标（3440×1440, UI 1.25）。
- **瓦片 BFS 寻路**：`walk_to` 改为读取客户端 `tile.collides_with('player')` 碰撞网格做 BFS，边走边重规划；实测绕过树林/残骸走 45 格回熔炉。
- **新增 `client_action_mine_entity`**：按类型/名字挖最近的树或石头（含寻路与右键长按），实测采集木头。
- **背包槽位测量修正**：格距 50 px（不是 44），角色界面首格中心 (1223,523)。
- 客户端 MCP 现为 **44 个 `client_*` 工具**。实测闭环：燃烧矿钻落在矿脉→把矿石吐在落点→落点放木箱自动收集→Ctrl+点击箱内矿石转入背包。
- 发现：Factorio 2.1 的燃烧矿钻**没有输出槽**，产物直接掉在 `drop_position`（前方地面）；落点被角色占住时状态 38（waiting_for_space_in_destination）。用木箱放在落点或按 F 拾取。
- 仍未实现：射击/战斗、载具、蓝图与远程视图内的客户端侧点击（这些仍走服务端工具链更稳）、平台侧自动化。

## 0.3.6 更新

- 新增高层后台动作模块 `bridge/client_actions.py`：**行走、挖矿、从背包取物、放置建筑、打开实体 GUI**，全部无需窗口前台/焦点，不依赖服务端 scenario/RCON。
- 客户端 MCP 扩展为 **39 个 `client_*` 工具**；新增 `client_action_*`（state/mine/pick/build/open/walk_to/stop/close_ui）。
- 实测：右键长按采矿同步到真实服务器（背包 +矿）；后台 GUI 取物；左键放置石炉成功；自动退出 remote view（按 M）。
- 已知限制：后台右键 up 未清除客户端输入状态；用“光标移到空白地”停止采矿；矿钻要在开始长按采矿**之前**放到矿上；打开 GUI 的验证需要截图。背包槽位坐标默认按 3440×1440 客户端，见 `docs/CLIENT-INJECTION.md`。
- 0.3.5 的“世界长按动作未打通”已被本版取代。

## 0.3.5 更新

- 新增客户端只读内存/Lua 桥（Frida）：后台读取位置、血量、背包、附近资源/实体/研究，不需要窗口焦点；MCP 提供 `client_memory_*`。
- 客户端 MCP 扩展为 **28 个 `client_*` 工具**：新增 0.3.5 **后台 SDL 动作通道**（`client_input_*`）。后台键盘（行走/按键/文本）和虚拟鼠标（定位、悬停/选择、GUI 点击）不需要窗口前台/焦点，也不依赖服务端 scenario/RCON；已验证后台行走会同步到真实服务器。
- 0.3.5 当时的已知限制（世界长按动作）已在 0.3.6 通过右键长按 + 空白地停止 + 高层动作工具解决；详见 `docs/CLIENT-INJECTION.md`。

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
