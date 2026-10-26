# Factorio 2.1.23 客户端/服务器协议与可接入面

> 结论先行：Factorio 的多人游戏面（UDP）不是 RPC，而是「下载完整地图 + 加载同样 mod + 确定性锁步模拟 + 输入流 + CRC 校验」。想让一个轻量程序冒充客户端，等价于重写 Factorio 引擎。可维护的接入口在**服务端 Lua 控制面**：RCON + mod 远程接口 + 游戏内真实 character 实体。本项目的连接器就是按这个结论实现的。

本文的分析对象是本机 `<FACTORIO_DIR>` 的 Factorio **2.1.23**（`bin/x64/factorio.exe`，PE x86-64，SHA-256 `fe4a1da30f322a0d0b8aeb3df7276332222baaa143e2352569b723e84b2b9060`）。分析手段与证据见 `docs/REA-NOTES.md` 和 `docs/evidence/`。

## 1. 三层通信面

| 面 | 传输 | 默认端口 | 用途 | 我们是否使用 |
|---|---|---|---|---|
| 游戏面 | 自定义二进制 UDP | 34197 | 发现、加入、地图传输、心跳、输入、锁步、CRC | 否（仅由真实服务端内部使用） |
| 控制面 | RCON over TCP（Source RCON 风格） | 27015/27016 | 执行服务端控制台命令、`/c` Lua、`/save`、`/quit` | **是** |
| 认证/列表 | HTTPS | 443 | `auth.factorio.com` 登录、服务器 padlock、公共服务器列表 | 服务端自动；本地可关闭 public |
| Lua 辅助面 | 本机 UDP / 文件 / 日志 | `--enable-lua-udp <port>` | mod 与外部进程交换数据、写 `script-output` | 当前未启用（已实测，保留扩展）；RCON 为回复主通道 |

Factorio 服务端的默认单人/联机端口是 **UDP 34197**；RCON 默认端口在官方示例中是 **27015**，但它与 Apple Mobile Device Service 等常见服务冲突，本项目实验使用 **27016**。

## 2. UDP 游戏面

### 2.1 发现与探测

从 PDB 的 `NetworkMessage` 派生类可以直接读出这一层的消息族：

| 消息类 | 作用 |
|---|---|
| `LANBroadcastMessage` | 局域网广播发现 |
| `GameInformationRequestMessage` / `GameInformationRequestReplyMessage` | 查询服务器名、版本、mod、人数等 |
| `GetOwnAddressMessage` / `GetOwnAddressReplyMessage` | NAT/地址探测 |
| `NatPunchMessage` / `NatPunchRequestMessage` | NAT 打洞 |
| `PingMessage` / `PingReplyMessage` | 延迟探测 |
| `EmptyMessage` | 占位/保活 |

### 2.2 建连与鉴权

```
Client                                   Server
  |  ConnectionRequestMessage              |
  |  (username, version, mods, password)   |
  |--------------------------------------->|
  |  ConnectionRequestReplyMessage         |
  |<---------------------------------------|
  |  ConnectionRequestReplyConfirmMessage  |
  |--------------------------------------->|
  |  ConnectionAcceptOrDenyMessage         |
  |<---------------------------------------|
```

PDB 中的 `ServerRouter::handleConnectionRequest`、`handleConnectionReplyConfirm`、`getPeerForThisConnectionReplyConfirm`、`addPeer` 与 `ClientRouter::processMessageInSocketThread` 对应这条链路。服务器会校验**游戏版本**、**mod 集合**、**账号验证/白名单/密码**；失败会走 `MultiplayerConnectionRefused*` 分支（exe 字符串里有 `Received MultiplayerConnectionRefusedServerHasWrongApplicationVersion while connecting is not in progress.`）。

### 2.3 地图传输

建连成功后，服务器发 `mapReadyForDownload`，客户端把地图保存为临时 `mp-download.zip`，按块请求：

- `TransferBlockRequestMessage`：客户端请求第 N 块；
- `TransferBlockMessage`：服务器返回块数据；
- 客户端状态机：`ConnectedWaitingForMap` → `ConnectedDownloadingMap` → `ConnectedLoadingMap`。

本机会话开始时已有的客户端日志（Factorio 2.0.77，真实联机）给出了一组具体数字：

```
24.227 Info ClientRouter.cpp:228: ConnectionAccepted
24.858 Info ClientMultiplayerManager.cpp:747: Received mapReadyForDownload
24.858 Downloading file ...\temp\mp-download.zip (33816799 B, auxiliary 123 B, 67232 blocks)
24.872 ... changing state from(ConnectedWaitingForMap) to(ConnectedDownloadingMap)
27.959 Finished download (3 s, 33.8 MB, 10.9 MB/s)
28.007 ... map download finished creating scenario
28.018 ... changing state from(ConnectedDownloadingMap) to(ConnectedLoadingMap)
28.113 Loading level.dat: 108806425 bytes.
30.129 ... changing state from(ConnectedLoadingMap) to(TryingToCatchUp)
30.161 ... changing state from(TryingToCatchUp) to(WaitingForCommandToStartSendingTickClosures)
30.191 ... changing state from(WaitingForCommandToStartSendingTickClosures) to(InGame)
39.324 Info ClientSynchronizer.cpp:319: Latency changed to (20)
```

这说明地图是**完整存档传输**（约 33.8 MB、67,232 个块），不是按需流式加载。

### 2.4 加载与追帧

客户端加载 `level.dat`、`script.dat`、所有 mod，并计算脚本校验和。随后进入 `TryingToCatchUp`，服务器让它追赶世界状态，再发 `ShouldStartSendingTickClosures`，客户端才开始发送输入。PDB 中的对应方法：

- `ClientMultiplayerManager::tryFinishDownloadingMap`
- `ClientMultiplayerManager::tryFinishLoadingMap`
- `ClientMultiplayerManager::receiveMapReadyForDownload`
- `ClientMultiplayerManager::receiveShouldStartSendingTickClosures`
- `ClientMultiplayerManager::receiveSkippedTickClosure`
- `ClientMultiplayerManager::tryFinishCatchingUpForDesyncReport`
- `ServerSynchronizer::processTickClosuresToJump`

### 2.5 游戏中的同步模型

这是**确定性锁步**，不是服务器权威状态广播：

- 客户端把本地输入编码成 `InputAction`，由 `NetworkInputHandler::sendInputActions` 发出；
- 客户端用 `NetworkInputListener::LatencyTickClosure` / `TickClosure` 处理延迟和跳帧；
- 服务器 `ServerSynchronizer` 汇总心跳、输入、tick closure；
- 双方按相同 tick 运行**完整模拟**（实体、物流、电路、Lua）；
- 周期性做 CRC 校验：exe 字符串 `Multiplayer desynchronisation: crc test (%s) failed for crcTick(%s) serverCRC(%u) localCRC(%u)`。

心跳/延迟相关消息：

| 消息类 | 作用 |
|---|---|
| `ClientToServerHeartbeatMessage` | 客户端心跳 + 输入/闭包 |
| `ServerToClientHeartbeatMessage` | 服务器心跳 + 同步信息 |
| `RequestForHeartbeatWhenDisconnectingMessage` | 断开前请求最后一次心跳 |

### 2.6 断线与 desync

- `ClientMultiplayerManager::receivePlayerDesynced`、`checkDesync`、`tryFinishCreatingDesyncReport`；
- `ParallelDesyncReportCreator`（PDB/exe 字符串）；
- 失败时客户端会下载服务器地图/对齐存档，或生成 `desync-report-*`；
- 日志字符串：`Map desynchronisation: tick %s`、`multiplayer.desynced`、`DesyncedWaitingForMap`、`DesyncedCatchingUpWithMapReadyForDownload`。

### 2.7 为什么不能做一个轻量“假客户端”

要冒充 Factorio 客户端，至少需要：

1. 完成上述发现/鉴权/地图分块下载；
2. 解包并加载 `level.dat`/`script.dat` 和全部 mod（Lua 数据、原型、地图）；
3. 在本地以**完全相同**的确定性规则运行全部实体、物流、电路、虫群和 Lua；
4. 编码正确的 `InputAction`，维持心跳与 tick closure，和服务器 CRC 对齐；
5. 处理版本/mod/地图不一致、desync、重连。

第 3 步就是重写 Factorio 引擎；协议本身也没有公开的字节级规范。**因此“模拟客户端”不应从 UDP 协议层做**。官方的可扩展点是服务端 Lua/RCON。

## 3. RCON 控制面

Factorio 的 RCON 与 Source RCON 兼容，使用 TCP、**小端序**、长度前缀。实测通过。

### 3.1 帧格式

```
int32 length | int32 id | int32 type | body bytes | 0x00 0x00
```

`length` 不包含自身 4 字节，等于 `4(id) + 4(type) + len(body) + 2`。

| type | 方向 | 含义 |
|---|---|---|
| 3 | 客户端 → 服务端 | AUTH，body 为密码 |
| 2 | 客户端 → 服务端 | EXEC，body 为控制台命令 |
| 2 | 服务端 → 客户端 | AUTH_RESPONSE（成功时 id 与请求一致） |
| 0 | 服务端 → 客户端 | RESPONSE，body 为命令输出 |

实测认证帧（密码 `test`）：

```
0e000000 01000000 03000000 74657374 0000
```

服务端响应：

```
0a000000 01000000 02000000 0000
```

`/version` 返回 `2.1.23\n`；命令输出通过 `rcon.print()` 回传，`game.print()` 走聊天/日志而不一定回 RCON。

### 3.2 命令与 Lua

- 命令必须带前导 `/`；不带 `/` 会被当作聊天（实测 `c rcon.print(...)` 变成聊天）。
- `/c <lua>` 或 `/silent-command <lua>` 执行 Lua；
- `remote.call("interface", "method", ...)` 调用 mod 的远程接口；
- `/save [name]`、`/quit`、`/help`、`/version` 等由服务端控制台处理；
- RCON 命令以 `<server>` 身份运行，不需要玩家在线。

### 3.3 Factorio 特有行为（实测）

1. **首次 Lua 命令会被吞掉**：新存档第一次执行 `/c` 时只记录日志
   `Using Lua console commands will disable achievements. Please repeat the command to proceed.`，
   RCON 返回空。连接器启动时应连续发两次无害命令（见 `AgentBridge.warmup`）。
2. **`auto_pause` 默认 true**：无玩家连接时服务器不推进 tick。做无头 Agent 必须在 `server-settings.json` 设 `"auto_pause": false`；否则 `on_tick` 不跑，角色/任务全部冻结。
3. **RCON 监听端口可能被其他进程占用**：本机 `127.0.0.1:27015` 被 Apple Mobile Device Service 占用，而 Factorio 绑定在 `0.0.0.0:27015`；回环连接会被更具体的 `127.0.0.1` 监听者接走，表现为连接被重置且 Factorio 日志没有 “New RCON connection”。换端口（27016）或 `--rcon-bind 127.0.0.1:27016`。
4. **RCON 限制**：`--rcon-port` 与 `--rcon-bind` 不能同时用；单连接数据上限 100 MB；有最大连接数；错误类型/解析失败会记录到日志。
5. **输出可以很大**：实测 `rcon.print` 返回 200 KB 文本仍在一个 RCON 响应帧里；本项目为稳妥仍把状态控制在几十 KB。
6. **`storage` 不能从控制台直接读**：控制台 `/c` 里的 `storage` 是关卡脚本存储，不是某个 mod 的 `storage`（实测 `storage.char_id` 为 nil）。请通过 `remote.call` 暴露状态，或用 `game.get_entity_by_unit_number`/扫描。

### 3.4 相关 PDB 符号

```
RemoteCommandProcessor::RconInterface::parse
RemoteCommandProcessor::RconInterface::read
RemoteCommandProcessor::RconInterface::send
RemoteCommandProcessor::RconInterface::sendTo
RemoteCommandProcessor::RconInterface::update / updateClient
RemoteCommandProcessor::RconInterface::maxClients
RemoteCommandProcessor::RconInterface::Client
RemoteCommandProcessor::RconInterface::Message
RemoteCommandProcessor::RconInterface::Message::Type
LuaRCON::luaPrint / valid / staticInit
RemoteCommandProcessor::StdStreamInterface / ConsoleLogInterface
```

## 4. Lua 控制面

### 4.1 远程接口

```lua
remote.add_interface("agentbridge", {
  state = function() ... end,
  submit = function(json) ... end,
})
```

外部通过 RCON：

```lua
/c remote.call("agentbridge", "submit", '{"kind":"mine","name":"iron-ore","count":10}')
```

返回数据用 `rcon.print(helpers.table_to_json(...))`。接口函数在**地图主线程**执行；返回大表会被序列化成 JSON 字符串。

### 4.2 事件与 helpers

- `script.on_event(defines.events.on_tick, ...)`：任务状态机；
- `on_script_path_request_finished`：异步寻路结果；
- `helpers.send_udp` / `helpers.recv_udp` / `on_udp_packet_received`：2.1 的本机 UDP 辅助通道，需要 `--enable-lua-udp <port>`；
- `helpers.write_file` / `remove_path`：写 `script-output`；
- `game.tick_paused`、`game.speed`：暂停/调速；
- `game.server_save()`：多人模式下保存当前存档。

UDP 实测（实验版 mod）：

- 入站：外部发到 `127.0.0.1:<lua-udp-port>`，`on_udp_packet_received` 正常触发，事件里带 `payload`、`player_index=0`、`source_port`。
- 出站：在没有玩家连接的专用服务器上，`helpers.send_udp(data, 0, port)` 返回成功但**外部收不到包**。因此本项目把 RCON 作为请求/响应主通道；当前 mod 未启用 UDP（RCON 已足够），该能力保留为扩展。需要出站推送时可用 `helpers.write_file` + 文件 tail，或接入一个真实客户端实例（`for_player` 指向玩家）。
- 官方文档说明：UDP 事件是通过 input action 引入游戏状态的；暂停/保存期间不处理；多人时数据还要经过服务器分发，因此应保持流量很小。

### 4.3 无 GUI 的“真实角色”

这是本项目最关键的可玩性发现：

- `LuaPlayer.character` 在玩家断开时返回 **nil**；
- `LuaPlayer.create_character()` 要求玩家 **online**；
- 但是 `surface.create_entity{name="character", position=..., force=game.forces.player}` 创建的**裸 character 实体**可以直接使用：
  - `character.walking_state = {walking=true, direction=...}`：真实走路，引擎处理碰撞；
  - `character.mining_state = {mining=true, position=...}`：真实挖矿，按资源/工具/ mining speed 结算，产物进角色背包；
  - `character.begin_crafting{recipe=..., count=...}`：真实手搓，消耗原料、按 crafting speed 产出；
  - `character.get_inventory(defines.inventory.character_main)` / `insert` / `remove`：真实背包；
  - 放到熔炉里会真实冶炼；角色也会被虫群攻击、会死亡。
- 因此无需 GUI 客户端，也无需 `game.connected_players` 非空。`auto_pause=false` 保证无玩家时 tick 继续。

实测（详见 `docs/TEST-REPORT.md`）：角色从 `(0,0)` 走到 `(9.17,9.17)`，挖到铜/铁/石/煤，手搓铁齿轮，放置石炉，装入煤和铁矿，等待后取出铁板。

## 5. PDB 中的协议/控制面清单

### 5.1 管理器与同步器

```
ClientMultiplayerManager::joinGame
ClientMultiplayerManager::startDownload / tryFinishDownloadingMap / tryFinishLoadingMap
ClientMultiplayerManager::receiveMapReadyForDownload / receiveNewPeerInfo / receivePeerDisconnect
ClientMultiplayerManager::receivePlayerDesynced / checkDesync / tryFinishCatchingUpForDesyncReport
ClientMultiplayerManager::tryToSendInputAction / updateMultiplayerInputInternal
ClientMultiplayerManager::receiveShouldStartSendingTickClosures / receiveSkippedTickClosure
ClientMultiplayerManager::receiveBeginPause / receiveEndPause / receiveGameEnd
ServerMultiplayerManager::receiveClientStateChanged
ServerSynchronizer::processTickClosuresToJump
NetworkInputHandler::sendInputActions
NetworkInputListener::LatencyTickClosure
```

### 5.2 路由器与消息

```
ServerRouter::addPeer / handleConnectionRequest / handleConnectionReplyConfirm
ServerRouter::getPeerForThisConnectionReplyConfirm / getPeerAddress / sendMessageToAddress
ClientRouter::processMessageInSocketThread
NetworkMessage / NetworkMessageHeader / UnparsedNetworkMessage
NetworkMessageType::Enum / reliable / str
```

### 5.3 消息类全表

发现/探测：`LANBroadcastMessage`、`GameInformationRequestMessage`、`GameInformationRequestReplyMessage`、`GetOwnAddressMessage`、`GetOwnAddressReplyMessage`、`NatPunchMessage`、`NatPunchRequestMessage`、`PingMessage`、`PingReplyMessage`。

会话：`ConnectionRequestMessage`、`ConnectionRequestReplyMessage`、`ConnectionRequestReplyConfirmMessage`、`ConnectionAcceptOrDenyMessage`、`EmptyMessage`。

传输：`TransferBlockMessage`、`TransferBlockRequestMessage`。

同步：`ClientToServerHeartbeatMessage`、`ServerToClientHeartbeatMessage`、`RequestForHeartbeatWhenDisconnectingMessage`。

### 5.4 反序列化

`NetworkMessageHeader` 从 `Deserialiser` 构造；`UnparsedNetworkMessage::parse<T>` 对每种消息做模板化解析。具体字段布局没有在 PDB 名称中暴露，本项目也没有做字节级复刻；这不影响基于 RCON/Lua 的连接器。


### 5.5 PDB 复算的网络消息头（2.1.23）

`NetworkMessageHeader` 的 PDB 字段布局（type index 167902）：

```
+0  type          NetworkMessageType (u8)
+1  fragmented    bool
+2  lastFragment  bool
+3  padding
+4  messageID     u16
+6  fragmentNumber u16
+8  confirm       std::vector<unsigned int>   // 类内字段，是否上线待抓包确认
```

`NetworkMessageType::Enum` 的值为：`0 Ping, 1 PingReply, 2 ConnectionRequest, 3 ConnectionRequestReply, 4 ConnectionRequestReplyConfirm, 5 ConnectionAcceptOrDeny, 6 ClientToServerHeartbeat, 7 ServerToClientHeartbeat, 8 GetOwnAddress, 9 GetOwnAddressReply, 10 NatPunchRequest, 11 NatPunch, 12 TransferBlockRequest, 13 TransferBlock, 14 RequestForHeartbeatWhenDisconnecting, 15 LANBroadcast, 16 GameInformationRequest, 17 GameInformationRequestReply, 18 Empty`。字节序/分片规则仍需真实抓包验证。

## 6. 推荐连接流程

```
1. 启动真实 headless 服务端（auto_pause=false, 固定端口, 独立存档）
2. TCP 连接 RCON → AUTH(type=3)
3. 发两次无害 /c 命令，吃掉 achievements 确认
4. remote.call("agentbridge","ensure") 确保裸 character 存在
5. remote.call("agentbridge","state", radius) 取世界/背包/附近资源
6. remote.call("agentbridge","submit", action_json) 提交任务
7. 循环 state/events 直到 job done/failed；或阻塞等待
8. 结束前 remote.call("agentbridge","save")，再 /quit 优雅退出
```

## 7. 未解/未做

- 没有做 UDP 游戏协议的字节级实现、加密/压缩/字段布局分析；结论是这条路线不经济。
- 没有复刻蓝图、GUI、个人物流、载具、火车、电路网络 UI、飞行/太空平台等系统。
- 裸 character 不是 `LuaPlayer`：少数只接受 `LuaPlayer` 的 API 不可用（如 `build_from_cursor`、`create_character`）；本项目用 `surface.create_entity` + 手动物品校验/扣除来模拟建造。
- `helpers.send_udp` 在无玩家专用服务器上的出站行为未完全定位；已用 RCON 规避。
- 用 `--create` 生成的存档没有玩家加入过，部分“起始科技”未自动授予；实验室用 `init-lab` 手动补齐，真实存档不需要。

## 参考

- 本机官方运行时文档：`<FACTORIO_DIR>\doc-html\runtime-api.json`、`classes.html`、`events.html`、`concepts.html`
- 本机官方示例：`data\server-settings.example.json`、`data\map-gen-settings.example.json`
- REA/PDB 证据：`docs/evidence/pdb_key_symbols.txt`、`docs/evidence/pdb_symbols_net.txt`、`docs/evidence/exe_strings_net.txt`
- 实测日志与结果：`docs/TEST-REPORT.md`
- airi-factorio：`<WORKSPACE>\airi-factorio`（MIT），复用分析见 `docs/AIRI-REUSE.md`
