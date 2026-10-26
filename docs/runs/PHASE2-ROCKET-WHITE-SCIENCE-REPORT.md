# 阶段二报告：火箭 / 太空平台 / 白瓶攻关

日期：2026-10-25  
存档：`server/green-autonomy.zip`（已保存，当前速度 1；真实玩家 LLM-Bot 在线）  
运行环境：Factorio 2.1.23 + Space Age，无虫害（peaceful），headless 服务端 + 第二真实客户端作为角色。

## 0. 结论摘要（先看这里）

本阶段把“能玩、能给 LLM 用、能持续扩建”的地基做完了，但**尚未完成火箭发射与白瓶生产**。本存档的原油在**与出生大陆隔水相望的独立陆块**上；本阶段末已用 **169 个 landfill（约 8450 石头）**建成 L 形 1 格宽桥并徒步抵达油区，pumpjack 已开始抽油，`oil-processing` 已解锁。剩余工作转为油区 refinery/化工、蓝瓶、火箭与平台。

当前已经完成的关键里程碑：

- MCP 工具从 44 个扩展到 **53 个**；LLM 工具从 25 个扩展到 **34 个**。新增实体明细、批量配方、完整科技树、产量统计、异常告警、资源簇、批量建造、配方设置、自动接线等接口。
- 已研究：`automation`、`automation-2`、`automation-science-pack`、`electric-mining-drill`、`electronics`、`engine`、`fluid-handling`、`landfill`、`logistic-science-pack`、`oil-gathering`、`oil-processing`、`steam-power`、`steel-processing`。
- 已建成：4 组独立蒸汽发电（3.6 MW）、铁/铜/煤/石多套采矿点、20 座石炉冶炼银行、电缆+绿电路自动生产线、红/绿科研包手工批量生产、20 格矿场带式收集、煤炭自动采集点。
- 实际产量（累计统计）：铁板 2364、铜板 1207、绿电路 243、红瓶 250、绿瓶 101、煤 1824、石头 908、运输带 156、机械臂 107。
- 已完成 landfill 科技；实测 MCP 53 工具 `initialize`/`tools/list` 与全部新增读接口 `--live` 通过。

## 1. 本阶段实际完成内容

### 1.1 信息与控制接口

新增（或修复后可用）的面向 LLM 的接口：

| 工具 | 用途 |
|---|---|
| `entity_detail` | 按 unit_number 或区域查询：朝向、状态名、血量、可采、配方、全部库存、流体、电网、drop/mining 位置、机械臂过滤、传送带内容 |
| `recipes_query` | 批量配方库；默认**包含未解锁配方**，避免“火箭配方查不到”的假空结果 |
| `tech_tree` | 完整科技树：已研究/可用、前置与未满足前置、成本/次数、科研包、trigger |
| `production_stats` | 强制物品累计生产/消耗，用来判断流水线是否真的在产出 |
| `alerts` | 停电、缺燃料、缺料、产物满、流体短缺、无资源、断开连接等异常汇总 |
| `resource_patches` | 大范围资源簇（总量、tile 数、中心、包围盒），用于选址与输油路线 |
| `build_entities` | 批量建设：精确坐标、自动设配方、自动接线，**从真实玩家背包扣除物品** |
| `set_recipe` / `wire_poles` | 改已有机器配方 / 修复蓝图 revive 后没有自动连接的铜线 |
| `find_water` | 修复为校验 offshore-pump 2x2 水面与 `can_place_entity`，不再返回陆地假泵位 |

MCP 服务端仍为 stdio JSON-RPC，工具总数 **53**（34 个 LLM 工具 + 19 个运维/任务扩展）。`tests/mcp_smoke.py --live` 已覆盖新增接口并通过。

### 1.2 电力与基础工业

- 4 组独立蒸汽集群，每组 1 台 offshore-pump + 2 根管道 + 1 台 boiler + 1 台 steam-engine；总容量 **3.6 MW**。
- 所有电线杆已接入同一电网（`enet=20`）；`wire_poles` 修复了蓝图建造后线杆彼此不连通的问题（47 杆 / 69 条连接）。
- 20 座石炉冶炼银行：可批量装矿石/煤，手动/脚本收集铁板、铜板；实测 300 矿石约产出 250 铁板。
- 铁/铜采矿：
  - 铁：早期电动钻 + 后续 5 台燃烧采矿钻，配运输带 + 末端箱子；
  - 铜：2 台电动钻 + 2 台燃烧钻，配运输带 + 箱子；
  - 煤：3 台燃烧钻 + 运输带 + 箱子（已实测累积 168+ 煤）；
  - 石：3 台燃烧钻 + 运输带/箱子（部分因放下时资源未清导致收集不稳，见 BUG 清单）。
- 电路生产线：铜线 AM → 绿电路 AM → 输出箱；插入机械臂方向和输出缓冲修复后，实测累计 243 绿电路。

### 1.3 科研与配方链

- 已通过手动批量生产红/绿瓶完成 `automation-2` 与 `landfill`。
- 关键结论：**火箭井本身不要求紫瓶/黄瓶**。`rocket-silo` 的前置是 concrete、rocket-fuel、processing-unit、logistic-robotics、low-density-structure、advanced-material-processing-2；这些都可以在蓝瓶阶段完成。真正的门槛是：
  - 蓝瓶需要石油（塑料、硫磺、硫酸）；
  - 石油在本存档位于独立陆块；
  - 因此必须 landfill 桥 + 输油管/电力线。
- 石油链研究包需求（红+绿各）：landfill 50（已完成）、engine 100、fluid-handling 50、oil-gathering 100、plastics 200、sulfur-processing 150、advanced-circuit 200、chemical-science-pack 75，合计约 **925 红 + 925 绿**。这是下一阶段最大工程量，要求绿瓶自动化而不是继续手工。

### 1.4 地图与石油结论

用资源簇 + 连通分量 + 最近点搜索得到：

- 出生大陆与油区陆块之间没有陆路；
- 最近缺口：出生侧 `(220,280)`，油区侧 `(276,408)`，约 **140 格水**；
- 油区油井集中在 `(344,448)`、`(348,434)`、`(353,435)`、`(364,450)`、`(422,487)` 等 14 个点；
- landfill 配方为 **50 石头 → 1 landfill**；实际 4 连通 L 形桥为 **169 格 = 8450 石头**（已建成，角色已过桥）。
- 已实测的精确水区：`y=265, x=243..275` 与 `x=275, y=265..401`；桥两端分别接出生大陆与油区陆块。

## 2. 发现并解决的问题（BUG / 陷阱）

1. **`research` 参数名不一致**  
   scenario 读 `job.params.tech`，bridge 传 `technology`，导致“bad argument #3”。已让 scenario 同时接受 `tech`/`technology`。

2. **批量配方查询把未解锁配方藏掉了**  
   `rocket-part`、`rocket-silo`、`space-science-pack` 等在未研究时 `enabled=false`；原来的 `enabled_only` 默认 true，导致“查不到火箭配方”。现在 `recipes_query` 默认包含未解锁配方，并显式返回 `enabled`。

3. **蓝图 revive 不自动接电线**  
   用 `build_entities`/`blueprint_build` 一次放多根电线杆后，每根杆各自一个电网，机器全部停电。已加入 `wire_poles_near`：蓝图 revive 后按杆型线长自动两两 `connect_to`，并提供 `wire_poles` 工具。实测 47 杆 69 连接，电网恢复统一。

4. **`find_water` 的假泵位**  
   `can_place_entity` 对 offshore-pump 会接受陆地中心；之前返回的 50.5,29.5 实际建不了。现在额外检查泵 2x2 足迹中至少 2 格水，并保留 shore 搜索。

5. **蓝图建造的“位置”是包围盒中心，不是左上角**  
   第一版电力线按左上角计算，整条线被放到错误位置。修复方式：`actual = build + bp_pos - bp_center`；后来用 `wire_poles` 和实际 detail 二次校验。以后批量蓝图必须用实际 detail 验证落点。

6. **机械臂方向语义**  
   `direction` 指向**拾取侧**的朝向，产物落在背后；多数人直觉相反。方向错时表现为 `waiting_for_source_items` / `waiting_for_space_in_destination`。已用 `pickup_position` / `drop_position` 逐根确认；`entity_detail` 现在也返回这两个点。

7. **生产机器输出缓冲会堵死整条线**  
   绿电路 AM 输出到 3 个电路后 status=full_output，前级电缆 AM 也满，插入臂全部 waiting。加输出机械臂 + 箱子后恢复。任何自动线都必须设计**出口缓冲/取出**。

8. **燃烧采矿钻的地面输出只出一件就停**  
   钻头把物品掉到地面后，地面物品实体占据输出点，钻头状态变成 `waiting_for_space_in_destination`，不是继续生产。必须让落点下面是**运输带/箱子/熔炉**。运输带可以铺在矿脉上；箱子和熔炉不能放在未清理的矿脉格上。

9. **相邻钻头的落点会互相占位**  
   一排 2 格间距的燃烧钻，每个钻的落点正好落在下一个钻头上，全部卡住。应保证输出方向有 1 格空带/箱，或统一朝外。

10. **实体尺寸/落点与 `can_place_entity` 不一致**  
    电动钻 3x3、石炉 2x2、箱子 1x1，按中心/整数格计算很容易差 1 格；`can_place_entity` 对“资源上的箱子/熔炉”偶尔仍返回 true，但 `create_entity` 会失败。当前 `build_entities` 先检查再建，失败会退款并返回 failures；对箱子类“资源格”可用直接 `create_entity` 实测（本次石场箱子即如此建成）。后续应把“资源格不可放建筑”写进构建器。

11. **产量统计 API 位置**  
    `force.item_production_statistics` 不存在；正确调用是 `force.get_item_production_statistics(surface)`。默认统计物品列表中若含未知物品会让整个调用失败，bridge 现在总是显式传一份安全清单。

12. **煤炭是真正的瓶颈，不是电力容量**  
    4 台锅炉满载约 0.9 煤/秒；加速到 20x 时 200 煤只够几秒。没有煤带/煤箱时，高倍速会把基地烧停。已建 3 钻煤炭点 + 箱子，后续应把煤送到锅炉旁并加“箱子+机械臂”自动加煤。

13. **实体状态必须解码**  
    `working`/`no_fuel`/`waiting_for_space_in_destination`/`full_output`/`no_ingredients` 对应完全不同的修复动作；只看 `ok=true` 会误判。`entity_detail` 与 `alerts` 已返回状态名。

14. **真实客户端断线后角色消失**  
    服务端仍在跑但 `player.connected=false`，所有 LuaPlayer 动作不可用。需要重新启动第二客户端并 `wait_connected`；存档前先 save。

## 3. 给后续 LLM 的决策经验

### 3.1 开工顺序

1. 先 `tech_tree` + `recipes_query` 确认目标配方和前置，不要凭记忆。
2. 先电力后产线：1 泵可带 20 锅炉/20 引擎；初期 2–4 引擎即可，但**煤一定要有来源**。
3. 先矿后炉：电动钻 90 kW，燃烧钻不需要电但 2x2 落点必须朝空带/箱；运输带可铺矿上。
4. 先电路后机器：绿电路是机械臂、电动钻、箱子、科研包的通用货币；一条“电缆 AM + 绿电路 AM + 输出箱”在早期收益极高。
5. 再科研：红/绿瓶先满足 `automation-2` 与 `landfill`；靠手工批量生产可以推进，但石油链的 925×2 包必须上自动绿瓶。

### 3.2 建造与排错

- 批量建造后**立刻 `entity_detail` 抽查**落点、朝向、配方；不要假设 `placed=N` 就万事大吉。
- 机械臂方向用 `pickup_position` / `drop_position` 验证；不要凭箭头直觉。
- 任何 AM 都要有出口：插入臂 + 箱子，或下游机器；否则 `full_output` 会反压整条线。
- 采矿钻落点必须有带/箱/炉；地面输出只出一件。
- 电线杆间距：小杆**供电半径 2.5**、线长 7.5；机器中心到杆必须 ≤2.5。蓝图后必须 `wire_poles`。
- 2x2 石炉、3x3 钻的中心网格要按实际实体位置算；`can_place_entity` 对资源格可能说谎，最终以 `create_entity` 结果为准。

### 3.3 石油与白瓶的关键数字

- **先探索再结论**：本报告的油区调查只覆盖**已生成 chunk**。不要直接认定油只在海上陆块；必须让真实角色走向未知地图，重新查 `crude-oil`，优先寻找同一大陆更近油田或绕湖陆路。landfill 长桥只是没有更近油源时的 fallback。
- 已生成区域内石油区在独立陆块，最近水缺口约 140 格；landfill 50 石/格，约 7000 石。
- 2026-10-25 实际 chart 到 ±1600 后复核：39 个原油 tile；最近仍是东侧海上陆块（约 349–439,435–506），水缺口约 140 格；西北新油田（约 -404…-426,-864…-883）水缺口约 371 格，更差。结论：暂时没有更近油源，东侧桥仍最优。
- **oil-processing 是 `mine-entity` trigger 科技**，不能靠科研包研究；必须到达油区并实际挖掉一个 `crude-oil` tile。pumpjack 配方已随 oil-gathering 解锁，refinery/化工仍要触发 oil-processing。
- 蓝瓶链：石油 → 塑料/硫磺/硫酸 → 红电路/处理单元 → 蓝瓶；火箭井只需要蓝瓶科技，不需要紫/黄瓶。
- 火箭井：1000 钢 + 200 处理单元 + 200 电动引擎 + 100 管 + 1000 混凝土；火箭部件 100 个（每件 1 处理单元 + 1 LDS + 1 火箭燃料）。
- 白瓶：太空平台用 冰 + 铁板 + 碳 合成（5 个/次）；需要先发射带 `space-platform-starter-pack` 的火箭并建平台。
- 平台物品：foundation、asteroid-collector、crusher、cargo-bay、solar panel/accumulator 等，均消耗钢/处理单元/电动引擎/LDS。

### 3.4 时间与倍速

- 倍速会同时放大煤耗；在没有煤带/大煤箱前，建议 speed 1–5，完成煤自动补给后再用 20+。
- 手工合成速度 1，AM1 速度 0.5；小批量手工更快，大批量/无人值守才上 AM。
- 研究是多实验室并行消耗科研包；先保证包供应，再加 lab。1 lab 只适合早期。

## 4. 下一步可执行路线（建议按顺序）

1. **landfill 桥（已完成）**：169 格 L 形桥已建，角色已过桥；landfill 已耗尽。
2. **油区接管道/储罐（已完成）**：pumpjack #426 已接 storage tank，tank 约 4.8k crude-oil，pumpjack working；油区局部蒸汽电 enet31。
3. **石油与蓝瓶（进行中）**：refinery/chem 已放下但未接电/管道；先接电，再把 tank 粗油接入 refinery south inputs，refinery north output 接 chem north input；先做 plastic（只需 petroleum + coal），再补水管做 sulfur/acid。之后做红电路、处理单元、蓝瓶；补足 925 红/绿包（自动绿瓶，8–12 台 AM2 + 多 lab）。
4. **火箭**：钢/混凝土/电动引擎/处理单元产线；火箭井 + 100 火箭部件；发射 `space-platform-starter-pack`。
5. **平台/白瓶**：平台 foundation、asteroid collector、crusher、assembling machine、cargo bay、太阳能；用冰+铁板+碳产白瓶，货舱/着陆台回传。
6. **全程验证**：`production_stats` 看白瓶累计、`alerts` 清异常、`detail` 抽查平台与火箭井。

## 4.5 自动化生产线（2026-10-25 新增）

- 自动传送带线已跑通：齿轮 AM → 传送带 AM（4 格中心距），铁板箱/齿轮箱/输出箱 + 4 个 inserter；实测输出箱已有 **46 transport-belt**。
- 自动采矿/冶炼单元已跑通：电钻 #471 → 石炉 #99 → 铁板箱 #468（107 plates）；煤箱 #466 + inserter #467 自动加煤。
- 现有铁/煤/石 outpost 已是“钻→传送带→箱子”结构，可直接作为自动供料点。
- 铁板闭环已接到传送带 AM：`#468 → inserter#493 → x=-34.5 纵向 belt → y=65.5 横向 belt → inserter#495 → #453`；#453 已有 232 plates，belt AM 自动生产，输出箱 #465 已有 **82 belts**。
- Logistics 已研究，splitter#529 已装在 x=-34,y=60.5（南向，双输入：左 #468、右 #537）。左路到 #453 正常；右支带 #530-#533 仍空，#452 只能人工补板。下一步修正 splitter 右侧输出/支带方向，或把 #452 输入箱移到主线旁用 inserter 直接取料。当前传送带输出箱已有 314 belts。
- EED1 已完成，medium pole 已解锁，refinery 供电条件具备。

## 5. 当前存档与复现

- 存档：`server/green-autonomy.zip`（已 save；当前速度 1）。
- 服务端：RCON `127.0.0.1:27017`，密码 `test`；真实客户端角色 `LLM-Bot`。
- WebUI：`python -m bridge.webui`（默认 `127.0.0.1:8090`）。
- MCP：`docs/mcp-config.example.json`；`python tests/mcp_smoke.py --live` 已验证 53 工具。
- 当前状态有部分机器因缺料/满输出 idle，属正常；煤点与石点会继续产煤/石（在燃料耗尽前）。若要长期挂机，先做煤自动加料。

## 6. 诚实边界

- 本阶段**没有**发射火箭、没有建立太空平台、没有白瓶，也没有完成完整通关验证。
- 但本阶段末已实际建成 **169 格 landfill 桥**（L 形 1 格宽，水区 `y=265, x=243..275` + `x=275, y=265..401`），角色徒步过桥到达油区；在油区建了局部蒸汽电（1 pump+boiler+engine）和 pumpjack #426，**oil-processing 已解锁**（pumpjack 真正开始抽取时触发；只放置不触发，手挖原油无效）。
- pumpjack 已接 2 根 pipe 到 storage tank（tank 在 `354,430`）；tank 已有约 **8.1k crude-oil**，pumpjack 状态 working。注意流体键名是 `crude-oil`（连字符）。
- 油区已放 `oil-refinery#447 @300.5,413.5` 和 `chemical-plant#449 @304.5,423.5`；配方材料已备，尚未接电/接管道。refinery inputs 在南侧 boxes1-2（pipe `299.5/301.5,416.5`），outputs 在北侧 boxes3-5；chem inputs 在北侧 boxes1-2（pipe `303.5/305.5,421.5`）。
- 石油陆块的 140 格水路是硬约束；不填海就只能靠后续 landfill/铁路/管线，无法用现有工具跳过。
- 基地的部分矿石/煤仍靠脚本批量搬运（从箱子/地面拾取），不是全程传送带/机器人；这满足“真实物品、不凭空生成”，但离“完全无人化工厂”还有距离。
- 下一步最值得投资的是：油区接管道/储罐并建 refinery/化工、煤自动加料、绿瓶自动化；桥和 oil-processing 已不再是主要卡点。
