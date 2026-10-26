# REA 分析记录

## 1. 目标

分析 `<FACTORIO_DIR>\bin\x64\factorio.exe`（Factorio 2.1.23）的多人游戏协议、RCON、Lua 控制面，为 LLM Agent 连接器选型。

## 2. REA 实际调用

### 2.1 `open_binary`

```json
{"path": "J:\\AI-Working\\Factorio\\bin\\x64\\factorio.exe"}
```

结果：

```json
{"path":"...factorio.exe","format":"pe","kind":"executable",
 "sha256":"fe4a1da30f322a0d0b8aeb3df7276332222baaa143e2352569b723e84b2b9060",
 "architecture":"x86_64"}
```

### 2.2 `binary_overview`（Ghidra provider）

返回 `provider_timeout`：

```
Ghidra did not finish importing and analyzing the target within its
1800000 ms startup deadline (REA_GHIDRA_STARTUP_TIMEOUT_MS).
```

原因很明确：exe 49 MB，同目录还有 **461 MB 的 factorio.pdb**，Ghidra 导入 + 符号/分析耗时超过 30 分钟。REA 给的建议是提高 `REA_GHIDRA_STARTUP_TIMEOUT_MS`，或用 `REA_GHIDRA_DISABLED_ANALYZERS` 跳过昂贵分析器；这两个都是启动 REA MCP 进程时的环境变量，当前会话无法修改。

### 2.3 `execute_rizin_command`

关闭 Ghidra 会话后尝试 Rizin：

```
{"provider_id":"rizin","operation":"execute_rizin_command",
 "reason":"Unable to run configured command (ERR_REA_WINDOWS_NATIVE)"}
```

REA 的 Windows 原生路径不支持该目标；`inspect_binary_layout` 也是 ELF/Linux 取向，不适用于这个 PE。因此没有拿到 Ghidra/Rizin 的反编译结果。

### 2.4 补偿手段

1. **PDB 符号**：`factorio.pdb` 是完整调试符号。用原始字节扫描提取可打印的符号名（不是完整 DBI/TPI 解析，拿不到地址/字段偏移，但能拿到类/方法/参数名）。
2. **exe 字符串**：提取 ASCII 字符串，过滤 RCON/网络/desync/认证等关键词，用于交叉验证。
3. **官方文档**：`doc-html/runtime-api.json`、`classes.html`、`events.html`、`concepts.html`，以及 `data/server-settings.example.json`、`data/map-gen-settings.example.json`。
4. **动态实测**：启动真实 headless 服务端，用自写 RCON 客户端和 Lua mod 验证帧格式、命令、UDP、角色能力、存档。
5. **本机既有客户端日志**：会话开始时读取 `%APPDATA%\Factorio\factorio-current.log`，看到一次真实联机的完整状态机（ConnectionAccepted → mapReadyForDownload → 33.8 MB / 67,232 blocks → ConnectedLoadingMap → TryingToCatchUp → InGame）。该文件随后被实验室运行覆盖；引文保留在 `PROTOCOL.md` 与 `TEST-REPORT.md`。

## 3. 证据文件

| 文件 | 内容 |
|---|---|
| `docs/evidence/pdb_symbols_net.txt` | 从 PDB 提取的 26,752 条与网络/RCON/多人相关的原始字符串 |
| `docs/evidence/pdb_key_symbols.txt` | 去噪后的 1,202 条关键类/方法/消息名 |
| `docs/evidence/exe_strings_net.txt` | exe 中与 RCON/网络/desync/认证相关的 1,929 条字符串 |
| `docs/PROTOCOL.md` | 基于上述证据 + 实测的协议结论 |
| `docs/TEST-REPORT.md` | 动态验证结果 |

## 4. 关键符号与含义

### 4.1 多人管理器/同步器

- `ClientMultiplayerManager`：`joinGame`、`startDownload`、`tryFinishDownloadingMap`、`tryFinishLoadingMap`、`receiveMapReadyForDownload`、`receiveShouldStartSendingTickClosures`、`receiveSkippedTickClosure`、`receivePlayerDesynced`、`checkDesync`、`tryToSendInputAction`、`updateMultiplayerInputInternal`。
- `ServerMultiplayerManager`：`receiveClientStateChanged`、`Peer` 列表。
- `ClientSynchronizer` / `ServerSynchronizer`：心跳、延迟、`processTickClosuresToJump`。
- `NetworkInputHandler::sendInputActions`、`NetworkInputListener::LatencyTickClosure`、`TickClosure`。

### 4.2 消息族

- 发现：`LANBroadcastMessage`、`GameInformationRequest/Reply`、`GetOwnAddress/Reply`、`NatPunch/Request`、`Ping/Reply`。
- 会话：`ConnectionRequest`、`ConnectionRequestReply`、`ConnectionRequestReplyConfirm`、`ConnectionAcceptOrDeny`、`EmptyMessage`。
- 地图：`TransferBlockMessage`、`TransferBlockRequestMessage`。
- 同步：`ClientToServerHeartbeatMessage`、`ServerToClientHeartbeatMessage`、`RequestForHeartbeatWhenDisconnectingMessage`。
- 基础设施：`NetworkMessage`、`NetworkMessageHeader`、`UnparsedNetworkMessage`、`NetworkMessageType::{Enum,reliable,str}`、`Deserialiser`。

### 4.3 RCON

- `RemoteCommandProcessor::RconInterface::{parse,read,send,sendTo,update,updateClient,maxClients}`；
- `RconInterface::Message`、`Message::Type`、`Client`；
- `LuaRCON::{luaPrint,valid,staticInit}`；
- `StdStreamInterface`、`ConsoleLogInterface`。

### 4.4 反 desync

- `ParallelDesyncReportCreator`；
- `ClientDesyncedWaitingForMap`、`ClientDesyncedDownloadingMap`、`ClientDesyncedCatchingUpWithMapReadyForDownload`、`ClientDesyncedSavingLocalVariantOfMap`、`ClientDesyncedCreatingReport`；
- 字符串：`Multiplayer desynchronisation: crc test (%s) failed for crcTick(%s) serverCRC(%u) localCRC(%u)`、`Map desynchronisation: tick %s`。

## 5. 没有拿到的内容

- 消息结构体字段偏移、枚举值、消息 opcode、压缩/加密方式；
- `RconInterface::parse` 的具体反编译；
- 地图块大小/压缩算法；
- 输入动作的二进制布局。

这些不是本项目的阻塞项：连接器走 RCON/Lua，不做 UDP 字节级兼容。若确实需要，建议：

1. 复制一份 `factorio.exe` 到实验目录，**不带 PDB**（或临时改名 PDB），用 Ghidra 单独打开；49 MB 的 PE 通常能在 30 分钟内完成默认分析。
2. 或在启动 REA 的环境里设置 `REA_GHIDRA_STARTUP_TIMEOUT_MS=7200000`，并用 `REA_GHIDRA_DISABLED_ANALYZERS` 跳过 Decompiler/PDB 等昂贵分析器。
3. 在 Ghidra 中从字符串 `Starting RCON interface at %s`、`RCON received an invalid message type %u`、`Multiplayer desynchronisation` 找 xref，定位 `RconInterface::parse` / `ClientMultiplayerManager::checkDesync`。
4. 用 Wireshark/tshark 抓本机 34197 UDP，和 PDB 消息类交叉验证；注意协议是自定义二进制，Wireshark 没有 dissector。

## 6. 复现步骤

```powershell
# 1. 打开
#    mcp__rea__open_binary(path="<FACTORIO_DIR>\bin\x64\factorio.exe")

# 2. 提取 PDB 字符串（本项目脚本思路）
python - <<'PY'
import re
data = open(r'<FACTORIO_DIR>\bin\x64\factorio.pdb','rb').read()
runs = re.findall(rb'[ -~]{6,300}', data)
# 过滤 Multiplayer/NetworkMessage/Rcon/Desync/CRC/...，见 docs/evidence
PY

# 3. 提取 exe 字符串
python - <<'PY'
import re
data = open(r'<FACTORIO_DIR>\bin\x64\factorio.exe','rb').read()
runs = re.findall(rb'[\x20-\x7e]{5,400}', data)
PY

# 4. 动态验证
cd <INSTALL_DIR>
python -m bridge.cli start
python -m bridge.cli observe
```

## 7. 结论

REA 成功完成了 PE 识别与静态资料采集；Ghidra 因 PDB/体积超时，Rizin 在 Windows 原生目标不可用。协议结论主要来自 **PDB 符号 + exe 字符串 + 官方文档 + 真实服务端实测**，足以支撑架构选型；没有进行 UDP 字节级复刻。
