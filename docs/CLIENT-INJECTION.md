# 客户端侧操作 Bot（输入 + 只读内存/Lua，不依赖服务端 scenario/RCON）

目标：服务器没有安装 AgentBridge scenario、没有开放 RCON 时，仍能操作一个真实 Factorio 客户端里的 Bot。典型场景是 `192.168.31.204` 这种原版 freeplay Host。

本项目新增 **客户端输入注入 + 只读客户端内存/Lua 读取** 通道。0.3.5 进一步加入**后台 SDL 动作通道**：键盘和虚拟鼠标不需要窗口前台/焦点；0.3.3 的 Win32 前台输入继续保留作为视觉闭环/长按世界动作的备用方案。

- 不修改服务端；
- 不加载客户端 mod；
- 不写游戏内存、不伪造游戏状态；
- 后台键盘动作通过 SDL keyboard state 注入（已验证行走同步）；后台虚拟鼠标通过 SDL 事件重写定位/选中/GUI 点击；
- 旧 `client_*` 前台工具仍通过 Windows 键盘/鼠标事件操作窗口；
- 后台状态通过 Frida 只读 Lua 桥读取（位置、背包、附近资源/实体），不需要截图或前台；
- 提供独立的 MCP stdio server：`bridge.client_mcp_server`。

> 这不等同于 DLL/Lua 注入。Factorio 是服务端权威的确定性模拟；在客户端直接改角色/背包/位置会造成 desync 或被服务器纠正。客户端 mod 在多人游戏中要求服务端同 mod，无法对原版服务器生效。因此可维护的“客户端侧”方案是 **正常输入注入 + 截图反馈**，而不是改内存或注入 Lua。

---

## 1. 组件

| 组件 | 作用 |
|---|---|
| `bridge/client_control.py` | 查找/聚焦 Factorio 窗口，发送 WASD、鼠标点击/长按、滚轮、文本，截图 |
| `bridge/client_mcp_server.py` | 独立 MCP stdio server，暴露 47 个 `client_*` 工具（含高层动作、合成/物资流转、无人值守循环、后台输入与内存读取） |
| `bridge/client_actions.py` | 0.3.6-0.3.8 高层后台动作：瓦片寻路行走/挖矿/伐木/合成/取放物资/放置/打开 GUI |
| `bridge/client_autopilot.py` | 0.3.8 无人值守燃烧时代循环：收矿/装炉/取板/分煤/工单合成/回锚点 |
| `bridge/client_input.py` | 0.3.5 后台 SDL 动作通道：键盘/文本/虚拟鼠标，不要求前台 |
| `bridge/client_memory.py` | Frida 只读 Lua 桥：抓取 lua_State、在游戏线程读取玩家/背包/附近环境 |
| `docs/client-mcp-config.example.json` | MCP 客户端配置示例 |

窗口要求（**旧 `client_*` 前台工具**；后台 `client_input_*` 不要求前台）：

- Windows；
- Factorio 以窗口/无边框窗口运行（独占全屏也可以，但切窗困难）；
- 输入时窗口必须在前台；`client_focus` 会用 `AttachThreadInput` 强制恢复焦点；
- 如果窗口失去焦点，按住键/鼠标的调用会中止，避免把输入发到别的程序。

---

## 1.5 后台 SDL 动作通道（0.3.5，`client_input_*`）

`client_input_attach` 后保持同一个 MCP 会话（内部保持一个 Frida 连接）。它不要求窗口前台：

- `client_input_key`：后台按键/长按（SDL scancode）；
- `client_input_walk`：W/A/S/D 或斜向持续 N 秒；已实测服务器看到正常 `walking` 并同步位置；
- `client_input_text`：向聊天/控制台输入文本；
- `client_input_move`：把**虚拟鼠标**移动到 SDL 客户端坐标（如 3440×1440），可悬停选中实体；
- `client_input_click` / `client_input_world_click`：在屏幕坐标/世界偏移处点击；GUI 点击已实测（人物界面可打开）；
- `client_input_mouse_off`：关闭虚拟鼠标，恢复真实鼠标事件。

实现：hook `SDL_PollEvent`，在游戏线程上通过 `SDL_SendKeyboardKeyInternal` 注入按键，通过 `SDL_SendMouseMotion`/`SDL_PrivateSendMouseButton` 注入鼠标，并重写/屏蔽真实鼠标事件。**不修改角色/背包/位置，不发送伪造网络包**；服务端收到的是正常 InputAction。

> 0.3.6 更正：世界长按动作**已经打通**。之前的失败是因为客户端处于 remote view（controller=7）、使用了左键/中键或没有把光标移出矿脉；正确路径是：先在角色控制器（controller=1），用**右键**按住矿产资源，停止时把光标移到空白地（后台右键 up 不会清除客户端输入状态）。矿钻要在开始长按采矿之前放置。详见 1.6 节。

## 1.6 高层后台动作（0.3.6，`client_action_*`）

`client_action_attach` 创建一个 `ClientActions`，内部同时保持 SDL 输入和只读 Lua 状态；它会自动退出 remote view（controller != 1 时按 M）。工具：

- `client_action_state`：controller、位置、选中实体、mining、cursor、背包、opened_self、虚拟鼠标；
- `client_action_mine`：后台挖最近的资源（默认 iron-ore），右键长按，移动到空白地停止，校验背包增量；
- `client_action_pick`：在人物背包 GUI 中点击物品到 cursor；
- `client_action_build`：取物并在世界坐标放置（可指定 on_ore/direction）；
- `client_action_open`：左键打开实体 GUI（先清空 cursor）；
- `client_action_walk_to`、`client_action_stop`、`client_action_close_ui`、`client_action_status`、`client_action_detach`。

已实测（F: 本地服务端 + 真实客户端，无窗口焦点）：右键长按铁矿产矿并同步服务器背包；GUI 取石炉；左键放置石炉；打开石炉 GUI；自动退出 remote view。所有动作都是正常客户端输入，不写 Lua/实体/网络包。

限制与操作顺序：

- 后台右键 up 不会让客户端生成 StopMining；用 `aim_blank`（光标移到无实体地块）停止，服务器 mining 会变 false。停止后客户端仍可能保持“右键按住”状态；此时**不要**把光标移到矿/建筑上做放置，先做地面放置或直接开始下一次采矿。
- 矿钻必须**先**放到矿上（右键未按住时），再开始长按采矿；`client_action_build(on_ore=true)` 在检测到 mining 时会拒绝。
- `opened` 实体 GUI 的验证不在安全 Lua 状态里（部分客户端会抛硬错误）；用截图或后续工具确认。
- 背包槽位几何默认 `(1223,523)`、50px、10 列（3440×1440，UI 1.25）；实体窗口内的角色面板首格坐标不同（石炉 508、矿钻 518），见 `ClientActions.ENTITY_GUI`。
- 仍建议在自己的服务器上优先用 scenario 的 `mine_entity`/建造/蓝图工具；客户端高层动作用于没有 scenario/RCON 的原版 Host。

## 1.7 合成、物资流转与寻路（0.3.7）

**后台点击的根因修复。** SDL 的 `SDL_PrivateSendMouseButton` 在“按下”和“松开”之间需要一个仍然存在的按键状态；真实鼠标事件（用户在其他显示器移动/点击）会把状态清掉，于是合成器里的“松开”直接被丢弃，GUI 按钮永远不触发。现在 `ClientInput.click()` 在**同一个游戏线程作业**里原子地发送 down+up（`clickPair`），并在事件过滤里把合成按键钉到虚拟光标坐标；真实鼠标的按键事件仍然丢弃。`click_pair(button)` 也用于清理“按住不放”的状态。

新增高层动作：

| 工具 | 行为 |
|---|---|
| `client_action_craft` | E 打开角色界面 → Ctrl+F 搜索 → Ctrl+A 清空旧查询 → 输入配方文本 → 点第一个结果（每点一次合成一次） |
| `client_action_mine_entity` | 按类型/名字（如 `type=tree, item=wood`）走到并挖掉最近的树/石头 |
| `client_action_insert` | 打开实体 → 从角色面板取一叠 → 点实体槽位（input/fuel/slot1） |
| `client_action_take` | 打开实体 → **Ctrl+左键**对应槽位，把内容快速转移进背包 |
| `client_action_pick_ground` | 光标指向地面物品后按 F 拾取 |
| `client_action_close_ui` | 幂等地关闭实体 GUI 与角色界面（E 探测，必要时再按一次 E） |

寻路：`walk_to` 不再只靠贪心与侧移，而是用客户端 Lua 读取 `tile.collides_with('player')` 生成半径 24 的碰撞网格，Python 端 BFS 出路径，按路点前进并在卡住时重规划；实测穿过树林与残骸走 45 格。

**燃烧矿钻（2.1）没有输出槽**：产物掉在 `drop_position` 前方的地面。落点被角色占住时状态为 38（waiting_for_space_in_destination）。处理：把木箱放在落点（钻会自动装入），或 `client_action_pick_ground` 用 F 拾取。实测闭环：矿钻→落点木箱→Ctrl+点击箱子把矿石转进背包。

实测流程（3440×1440，UI 1.25）：挖树取木 → 合成木箱 → 石炉进矿/进木 → 出 8 铁板 → 合成铁齿轮 → 燃烧矿钻放在矿上 → 木箱收集 → 取矿回背包。

## 1.8 无人值守循环（0.3.8，`client_autopilot`）

`BurnerAutopilot` 按固定间隔执行一个安全 tick：

1. 从落点木箱 Ctrl+点击收矿；
2. 把背包里的矿整叠装进石炉；
3. 从熔炉输出 Ctrl+点击取板；
4. 交替给矿钻/熔炉分煤（右键取半叠，`entity_insert(half=True)`）；
5. 按工单把某配方补到目标数量（每 tick 最多合成一次）；
6. 离锚点过远时走回去。

独立运行：

```bash
python -m bridge.client_autopilot --pid 55128 --name LLM-Bot   --drill=-56,-2 --chest=-56.5,-3.5 --furnace=-49,6 --anchor=-52.7,1.3   --order "iron gear wheel=10" --interval 20 --minutes 6   --state state/autopilot_state.json
```

MCP：`client_auto_start`（参数 drill/chest/furnace/anchor/orders/interval/minutes）、`client_auto_status`、`client_auto_stop`。循环运行时其它 `client_action_*`（除 state/status）会被拒绝，避免两个动作流抢同一个虚拟鼠标。

**小实体定位修复（0.3.8）**：1×1 容器在默认缩放下可点击区只有约 9 px，且渲染位置与 `position` 会有几个像素偏差；单点瞄准会偶发选中下面的矿。现在 `open_entity(name=...)` 先做**小范围悬停搜索**（±22 px，步长 6 px）确认 `selected == name` 再点击，背包/熔炉/木箱的打开因此稳定。实测对落点木箱一次取回 67 铁矿。

**0.3.8 的三个稳定性修复（都是实测踩出来的）**：

1. **单会话锁**：同一游戏进程里两个 Frida 输入脚本同时 hook SDL，任一卸载都可能让客户端崩溃（本轮实测崩过一次）。`ClientInput` 现在持有 `state/client_input.lock`，第二个会话直接报错；循环运行期间只允许 RCON/只读内存观察。
2. **输入焦点**：客户端重启后 SDL 键盘焦点为 0，注入的文字全部丢失（合成搜索为空）。`ClientActions` 初始化时自动 `enable(1720,720)`，同时建立虚拟鼠标与键盘焦点。
3. **精确背包槽**：客户端 Lua 的 `inv[i].name`（1..40）是可读的（`get_slot` 仍会硬错误），所以取物前先解析物品所在槽，不再“逐格试拿再放回”；避免误拿木箱时回放失败卡住循环。合成还加了 `expect` 校验：搜索结果被吞时（点到了默认列表首格）会重开界面重试一次。

**8 分钟实测**：20 个 tick、0 错误；收矿 116、装炉 116、取板 115、耗煤 39；工单把铁齿轮补到 12；结束时背包 192 铁板 / 12 齿轮，熔炉仍在工作。

**限制**：实体库存无法通过客户端 Lua 读取（对非玩家实体调用 `get_inventory` 会硬错误），循环以时间片 + 玩家背包增量计数；煤的分配是启发式（半叠轮换），没有真实库存反馈。长时运行应在有 scenario/RCON 的服务器上并行观察，或定期人工校准。

## 2. 后台内存/Lua 读取（Frida）

`python -m bridge.client_memory --pid <pid> observe` 或 MCP 的：

```text
client_memory_attach  {"pid": 12345}
client_memory_observe {"radius": 64}
client_memory_inventory
client_memory_detach
```

原理：

- 通过 PDB 的公开符号定位 Factorio 2.1.23 的 `luaL_loadstring` / `lua_pcallk` / `lua_tolstring` / `lua_settop`；
- Frida attach 到 `factorio.exe`，hook `lua_pcallk` / `luaD_call` 抓取 Lua state；
- 在 `onLeave` 的**游戏线程**里执行只读 Lua chunk：
  - 玩家名、位置、血量、表面；
  - 主背包物品/数量；
  - 半径内资源（含 amount）和实体（名称/类型/坐标/unit_number/status）；
  - 当前研究、选中实体。
- 返回 JSON，无需游戏窗口在前台；实测客户端最小化时仍能读取。
- 服务器多人时**必须传 `name`**（例如 `LLM-MemTest`）；否则会返回 `multiple connected players; pass name`，避免误读另一名玩家的位置/背包。

限制：

- 地址按 Factorio **2.1.23 win64** 固定；游戏更新后需从 PDB 重新生成 `bridge/client_memory.py` 的 RVA 表。
- 只读；不要在客户端 Lua 里改角色/背包/位置——多人服务器会 desync 或被纠正。
- Frida 是可选依赖：`pip install frida`；没有安装时其余 `client_*` 输入工具仍可用。
- 只应在自己的客户端/服务器或获授权的环境使用；Frida attach 属于进程注入。

## 3. MCP 配置

```json
{
  "mcpServers": {
    "factorio-client": {
      "command": "python",
      "args": ["-m", "bridge.client_mcp_server"],
      "cwd": "<ABSOLUTE_PATH_TO_FactorioAgent>",
      "env": {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    }
  }
}
```

它与原来的 `factorio` server（RCON/scenario）**互相独立**：

- 有 scenario/RCON 时优先用原 server，状态/动作精确；
- 没有时用 `factorio-client`，只靠输入和截图。

不要同时让两个“大脑”操作同一个 Bot。

---

## 4. 工具

| 工具 | 作用 |
|---|---|
| `client_list_windows` | 列出 Factorio 窗口（hwnd/pid/title） |
| `client_attach` | 按 hwnd/pid/title 绑定窗口 |
| `client_info` | 窗口信息、客户区大小、是否前台 |
| `client_focus` | 强制前台 |
| `client_screenshot` | 截图；`inline=true` 同时返回 MCP image content |
| `client_key` | 单键 tap/down/up（wasd/e/m/tab/esc/enter/tilde/数字/VK） |
| `client_hold` | 按住键 N ms，失焦自动中止 |
| `client_walk` | 按住方向键 N 秒 |
| `client_click` | 客户区坐标点击；`hold_ms` 长按（挖矿/采集）；`double` 双击 |
| `client_scroll` | 滚轮 |
| `client_type` | 输入 ASCII 文本（聊天/控制台） |
| `client_map` | 开关地图（M） |
| `client_inventory` | 开关背包（E） |
| `client_input_attach/status` | 附加/查询后台 SDL 动作通道（保持会话） |
| `client_input_key/walk/text` | 后台键盘、行走、文本 |
| `client_input_move/click/world_click` | 后台虚拟鼠标定位/点击 |
| `client_input_mouse_off/detach` | 关闭虚拟鼠标/断开通道 |
| `client_memory_attach` | 附加只读 Frida Lua 桥（后台） |
| `client_memory_status` | 内存桥状态 |
| `client_memory_observe` | 位置/血量/背包/附近资源/实体/研究 |
| `client_memory_inventory` | 主背包 |
| `client_memory_detach` | 断开内存桥 |

截图默认保存到 `state/shots/client.png`，同时可生成 `_small.png`。GPU 截图优先调用 `um win shot --hwnd`（Windows Graphics Capture）；没有 `um` 时回退 PIL，可能出现黑屏。

CLI 也可直接使用：

```powershell
python -m bridge.client_control list
python -m bridge.client_control --pid 12345 focus
python -m bridge.client_control --pid 12345 shot state/shots/client.png --scale 0.5
python -m bridge.client_control --pid 12345 walk left 2.5
python -m bridge.client_control --pid 12345 click 640 360 --hold-ms 30000
```

---

## 5. 原版服务器上的挖矿流程（示例）

以 `192.168.31.204` 的 freeplay Host 为例：

1. 用 standalone 客户端连接（`BotClient` 默认 34198 本地端口），窗口保持可见；不要最小化。
2. MCP 调用：
   - `client_list_windows` → 拿 hwnd；
   - `client_attach` → `client_focus`；
   - `client_screenshot`（`inline=true`）看当前位置；
   - `client_map` → 截图，找最近铁矿（地图上铁矿石通常为蓝灰色块）；
   - 关闭地图，`client_walk` 按方向走 2~5 秒，重复地图截图修正；
   - 到矿旁后，在世界截图里选矿格坐标，`client_click(x,y,hold_ms=60000)` 长按挖矿；
   - `client_inventory` + 截图，读取铁矿石数量；
   - 未到 50 就继续对准矿格长按或换格。
3. 因为这是视觉闭环，工具会返回明确截图路径，但**不会伪造“已挖 50”**；需要看截图/物品计数确认。

一次长按通常能连续挖同一矿格；矿格耗尽后要换格。若矿脉被建筑/树挡住，先绕行或清理。

---

## 6. 与 RCON 方案的对比

| 维度 | 服务端 scenario/RCON | 客户端输入注入 |
|---|---|---|
| 服务端要求 | 必须装 scenario + 开 RCON | 无 |
| 状态精度 | 精确（背包/坐标/实体/配方） | 依赖截图/视觉 |
| 动作精度 | API 级，可寻路/队列/蓝图 | 键鼠级，受焦点/UI 影响 |
| 速度 | 快 | 慢 |
| 适用服务器 | 自己/可改服务端 | 任意可正常加入的服务器 |
| 风险 | RCON 权限 | 焦点被抢、点击误操作；不修改状态 |

结论：能改服务端时仍用 scenario；不能改时用本客户端通道，二者不要混用。

---

## 7. 限制与安全

- 只在 Windows 验证；Linux 需替换输入/截图实现。
- 需要前台焦点；用户正在操作同一桌面时会互相抢输入。长时间运行建议独立 Windows 用户会话/RDP 或第二台机器。
- 不能读取权威游戏状态；坐标/背包由截图判断，精度有限。
- 不支持蓝图、太空平台等高层 API；这些仍应走服务端 scenario。
- 输入类工具不修改内存/游戏状态；内存读取为只读 Lua 注入；不绕过反作弊、不伪造网络包。
- `client_input_*` 使用 Frida 注入 SDL 调用；这是客户端进程注入，属于正常输入注入的自动化，不等同于修改游戏状态。
- 世界目标长按鼠标动作尚未打通；不要把它描述为“可手挖/放置”。
- 内存桥需要 Frida，属于客户端进程注入；只在你拥有/获授权的客户端上使用。
- 在多人服务器使用自动化前，确认服务器规则允许；不要在别人的服务器上未经许可操作。
