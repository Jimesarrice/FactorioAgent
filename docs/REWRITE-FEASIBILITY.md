# 完全模拟协议客户端：反编译尝试与可行性结论

> 结论：**“重写 Factorio 引擎 + 完全模拟协议客户端”不是一个可以在本会话内完成的功能，也不是一个协议适配器工程，而是重写一款商业游戏引擎。** 我完成了可行范围内的反编译与结构提取，确认了这一点，并给出可执行的分阶段路线。下面区分“已验证的事实”和“工程判断”。

## 1. 我实际做了什么

1. **REA/Ghidra**
   - REA `open_binary`：`factorio.exe`，PE x86-64，49 MB，SHA-256 `fe4a1da3…9060`。
   - REA `binary_overview`：Ghidra 导入 49 MB exe + 461 MB PDB 超过 30 分钟启动上限，返回 `provider_timeout`。
   - 关闭 REA 会话后，直接使用本机 Ghidra 12.1.4（`D:\programs\ghidra_12.1.4_PUBLIC`）+ JDK 21 做 headless：
     - 先 `-noanalysis` 导入，再只启用 PDB 分析器（`OnlyPdb.java`），其余分析器全部关闭。
     - Ghidra 的 PDB 应用在 `DataTypeComponentDB.isEquivalent` 的递归类型比较里卡住（jstack 已确认），这是 200 万级类型/循环类型图的已知难点；不是几行参数能绕过的。
2. **PDB 原生工具**
   - Ghidra 自带 `pdb.exe` 依赖 Microsoft DIA SDK；本机有 `msdia140.dll`，但未注册，直接运行返回 `Unable to locate the DIA SDK`。注册需要管理员权限，且会改注册表，我没有擅自做。
3. **PDB 直读**
   - 安装 `pdbparse 1.5`，并针对 Factorio 的新版 PDB/`construct` 兼容性修了 4 处解析问题（未解析枚举名、未知 leaf、缺失字段、DBI 文件名偏移）。
   - 成功解析：**2,069,542 个 TPI 条目、1,971,084 个类型记录、53,918 个命名结构、1,074 个模块、67.5 MB 符号流**。
   - 这些数字本身就是“引擎重写”的成本证据。
4. **官方运行时面量化**
   - `doc-html/runtime-api.json`（2.1.23）：**157 个类、1,041 个方法、2,773 个属性、229 个事件、496 个概念**。这还只是暴露给 Lua/mod 的部分，不含 C++ 内部实体、物流、电路、渲染、音频、平台层。
5. **协议面已有结论**（上一轮 + 本轮）
   - 16 类 `NetworkMessage`：LAN 发现、GameInformation、Ping、ConnectionRequest/Reply/Confirm/AcceptOrDeny、TransferBlock/Request、三种 Heartbeat、Empty 等。
   - 加入流程是：发现 → 建连/鉴权 → 下载完整地图（真实日志 33.8 MB / 67,232 块）→ 加载 `level.dat`/`script.dat`/mods → `TryingToCatchUp` → `InGame` → 心跳 + InputAction + TickClosure + CRC。
   - 所有端都跑**完整确定性模拟**；CRC 不一致会 desync/断开。

## 2. 为什么“完全模拟的协议客户端”等于重写引擎

一个能加入并留在服务器里的客户端必须同时具备：

1. **网络层**：UDP 可靠层、消息头/序列化、连接状态机、地图分块、NAT/发现、重连。
2. **资源层**：解析 `.zip` 存档、`level.dat`、`script.dat`、原型数据、mod 数据、蓝图、地图块。
3. **模拟层**：所有实体更新顺序、传送带/机械臂/管道/电力/电路/火车/机器人/虫群/污染/太空平台等。
4. **Lua/mod 层**：完整 Factorio Lua API、事件顺序、随机数、`storage`、mod 加载/迁移；mod 是任意代码。
5. **确定性层**：浮点/迭代顺序/tick 对齐必须与 Wube 的构建逐位一致，否则 CRC 失败。
6. **协议层**：InputAction、TickClosure、CRC tick、desync 报告/地图重下。

这不是“把 RCON 换成 UDP”能解决的；这是 Factorio 引擎的 clean-room 重实现。按模块估算：

| 阶段 | 内容 | 现实工期（有经验的小团队） |
|---|---|---|
| M0 | 发现/Ping/抓包/消息头 | 数天 |
| M1 | 连接/鉴权/握手 | 数周 |
| M2 | 地图分块下载、存档/prototype 解析 | 数周–数月 |
| M3 | 输入/心跳/CRC，能“连上不立刻掉” | 数月，且需要 M4 |
| M4 | 最小 vanilla 世界模拟（实体子集、Lua 子集） | 数月 |
| M5 | 完整 vanilla + 常见 mod + 版本跟进 | 多年 / 持续维护 |

这不是我给出的“否定”，而是由上面 200 万类型、1041 个 Lua API 方法、完整确定性要求共同决定的量级。


## 2.1 已从 PDB 复算出的网络头（本轮新增）

PDB 中 `NetworkMessageHeader`（type index 167902，class size 32）的字段：

| 偏移 | 字段 | 类型 | 说明 |
|---|---|---|---|
| 0 | `type` | `NetworkMessageType`（u8） | 0–18，见下表 |
| 1 | `fragmented` | bool/u8 | 分片标志 |
| 2 | `lastFragment` | bool/u8 | 最后一片 |
| 3 | — | padding | 对齐 |
| 4 | `messageID` | u16 | 消息 ID |
| 6 | `fragmentNumber` | u16 | 分片序号 |
| 8 | `confirm` | `std::vector<unsigned int>` | 类内字段；是否出现在线格式待抓包确认 |

`NetworkMessageType::Enum` 的 PDB 值（已确认）：

```
0 Ping
1 PingReply
2 ConnectionRequest
3 ConnectionRequestReply
4 ConnectionRequestReplyConfirm
5 ConnectionAcceptOrDeny
6 ClientToServerHeartbeat
7 ServerToClientHeartbeat
8 GetOwnAddress
9 GetOwnAddressReply
10 NatPunchRequest
11 NatPunch
12 TransferBlockRequest
13 TransferBlock
14 RequestForHeartbeatWhenDisconnecting
15 LANBroadcast
16 GameInformationRequest
17 GameInformationRequestReply
18 Empty
```

这意味着**消息头的类型字节和枚举已可编码/解码**；`messageID`/`fragmentNumber` 的字节序、`confirm` 是否上线、分片规则仍需要真实抓包验证。`TransferBlockRequestMessage`（size 16）、`ClientToServerHeartbeatMessage`（size 104）、`ServerToClientHeartbeatMessage`（size 96）等类的成员解析受 pdbparse 对前向引用/基类的限制，尚未完整导出。

## 3. 三条可行路线

### 路线 A：真实引擎 + 无头/虚拟显示（最快达到“客户端”）

- 用官方客户端连接服务器，但运行在隐藏的 Windows 会话、虚拟机或 Linux + Xvfb + 软件/GPU 渲染中；用 mod/输入注入或 Lua 控制。
- 优点：协议、模拟、mod 全部由官方引擎完成，天然不 desync；几天到几周可搭。
- 缺点：仍有 GUI/GPU/Steam 依赖；不是“重写引擎”；自动化 UI 脆弱。
- 本机的 Steam 版客户端直接启动会报 `Steam requires game restart`，需要通过 Steam 启动或使用独立版；这属于客户端启动问题，不是协议问题。

### 路线 B：协议观察者/握手客户端（研究价值最高）

- 只实现 M0–M2：局域网发现、建连、地图下载、读取服务器状态；**不进入模拟**。
- 用途：抓包、验证消息布局、做服务器浏览器/监控、研究 desync。
- 工作量：数周（前提是有真实客户端配合抓包 + 反编译消息编解码）。
- 它会在地图加载/追帧阶段失败或被断开；这是预期的，不是 bug。

### 路线 C：服务端具身 Agent（已交付，生产可用）

- 也就是上一轮的 `FactorioAgent`：真实 headless 服务端 + mod 角色 + RCON。
- 优点：真实模拟、可存档、无 GUI、LLM 可控；缺点：不是网络协议客户端，不能加入别人的服务器。
- 对“让 LLM 玩游戏”这个目标，这是目前最优解。

### 路线 D：Clean-room 引擎重写（长期）

- 只有在你接受“多年、持续跟进版本、法律/维护风险”时才考虑。
- 需要从 M0 开始，且必须用真实客户端抓包 + 差分测试 + 每个版本回归；不能靠一次反编译完成。
- 不建议在当前阶段启动。

## 4. 法律与边界

- 本研究只针对你本机拥有/安装的 Factorio，做互操作性分析；**不绕过 DRM、不绕过账号验证、不复制/分发游戏资源或反编译代码**。
- Factorio 的 EULA/当地法律对反向工程和衍生作品可能有额外限制；发布任何客户端前请自行确认。不要把 `factorio.exe`、PDB、解包数据或反编译结果打进仓库。
- 若只是自建服务器 + 自用 Agent，路线 C 没有这个问题。

## 5. 如果继续：我建议的下一步

1. **先定目标**：你要的是“加入任意服务器并玩”（A/B/D），还是“在自己的服务器上让 LLM 玩”（C）？
2. 若选 B：
   - 需要你授权我用 Steam 启动一个真实客户端，抓一次本机回环 UDP 包（或你提供 pcap）。
   - 我用 pdbparse 的类型布局 + 抓包做消息头/握手/地图块的字段对照，先实现发现 + 握手 + 下载。
   - 交付物是“协议观察者”，明确不进入模拟。
3. 若选 A：
   - 我先在虚拟机/隐藏桌面里把官方客户端跑起来，验证无头可行性，再做输入控制；这比反编译引擎快一个数量级。
4. 若选 D：
   - 需要立项、预算、版本策略和法务评估；我可以先产出 M0–M2 的详细设计，但不会承诺短周期内“完全模拟”。

## 6. 当前可复现的反编译资产

| 路径 | 内容 |
|---|---|
| `re/ghidra_scripts/OnlyPdb.java` | 只启用 PDB 分析器的 Ghidra preScript |
| `re/ghidra_scripts/DumpInfo.java` | 导出符号/函数/类型 |
| `re/ghidra_scripts/ApplyPdb.java` | 尝试直接应用 PDB（受分析会话限制，保留作记录） |
| `re/pdb_layouts.txt` | `NetworkMessageHeader` 布局 + `NetworkMessageType` 枚举值 |
| `re/pdb_classes.txt` | 1,175 条匹配类型记录（含 type index、size、类名） |
| `re/tpi_scan.txt` | TPI/流结构统计与探查样本 |
| `re/pdbonly_jstack.txt` | Ghidra 卡在 `DataTypeComponentDB.isEquivalent` 的线程栈 |
| `re/pdbonly2_stdout.log` | 只启用 PDB 分析器的完整 headless 日志 |
| `re/pdbexe.log` | `pdb.exe` 缺 DIA SDK 的错误 |
| `re/pdb_dump.txt` | 无分析会话时 PDB 应用失败的证据 |
| `re/pdbonly2_stdout.log` | Ghidra PDB-only 分析日志（含卡点） |
| `docs/evidence/` | 上一轮的 PDB 符号/字符串证据 |

复现关键命令：

```bat
D:\programs\ghidra_12.1.4_PUBLIC\support\analyzeHeadless.bat ^
  <INSTALL_DIR>\re\ghidra_project FactorioRE ^
  -import <INSTALL_DIR>\standalone\bin\x64\factorio.exe ^
  -preScript OnlyPdb -postScript DumpInfo <INSTALL_DIR>\re\pdb_info.txt ^
  -analysisTimeoutPerFile 1200 -scriptPath <INSTALL_DIR>\re\ghidra_scripts
```

PDB 直读（需先修 `pdbparse` 的 4 个兼容点）：

```python
import pdbparse
pdb = pdbparse.parse(r"<FACTORIO_DIR>/bin/x64/factorio.pdb")
tpi = pdb.streams[2]
print(len(tpi.types), len(tpi.structures))
```

## 7. 诚实的状态

- 已完成：协议分层、消息类清单、加入/地图/锁步/CRC 流程、PDB 规模量化、反编译管线与卡点证据。
- 未完成：消息结构字段的完整导出（pdbparse/Ghidra 在 200 万类型上仍有性能/兼容问题）、真实 UDP 抓包、握手客户端、任何模拟。
- 因此**没有**“重写好的引擎”或“能加入服务器的自研客户端”可以交付；我不会把 RCON 具身 Agent 包装成那个东西。
