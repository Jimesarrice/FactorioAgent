# LLM 决策速查：Factorio Space Age 本存档

这份速查给下一个接手的大模型用。先读这里，再读 `PHASE2-ROCKET-WHITE-SCIENCE-REPORT.md` 的详细经过。

## 0. 先确认三件事

1. 真实玩家是否在线：`get_state` 看 `player.connected`；不在线先启动 `LLM-Bot` 客户端。
2. 当前目标/控制台指令：`get_inbox` + `decision_context`。
3. 电力是否活着：`alerts` 看 `no_power`；`no_fuel` 优先修，因为会连锁停矿/停炉。

### 0.1 原油：先探索未知地图，不要只看已生成区域

`resource_patches` / `find_entities_filtered` 只能看到**已经生成/已探明**的 chunk。不要因为一次调查只在远海陆块看到油，就直接上 140 格 landfill 桥。正确顺序：

1. 让真实角色实际走向未知区域（`walk_to` 到地图边缘/未探明方向），触发新 chunk 生成；
2. 每到一段就重新 `resource_patches` 或 `entity_detail` 查 `crude-oil`；
3. 优先找**同一大陆上的更近油田**，或找到绕过湖泊的陆路；
4. 只有确实没有更近油源/陆路时，才把 landfill 长桥作为 fallback。

这条是硬规则：**先探索，再填海。**

2026-10-25 实测（本存档）：

- 已 chart 到 ±1600 范围；共 39 个原油 tile，最近仍是东侧海上陆块（约 349–439, 435–506），水缺口约 **140 格**。
- 西北方向新发现油田（约 -404…-426, -864…-883），但其水缺口约 **371 格**，比东侧更差。
- 因此探索结论：**目前没有更近的油源；东侧 140 格桥仍是最优路线**。以后 chart 到更大范围若有更近油岛，再改路线。
- 2026-10-25 后续实际执行：已用 169 个 landfill 建成 **L 形 1 格宽桥**（水区约 `y=265, x=243..275` + `x=275, y=265..401`），角色已徒步过桥到达油区。
- **oil-processing 是 `mine-entity` trigger 科技**：不能靠红绿瓶研究。实测：
  - 手挖 `crude-oil` tile 无效（流体资源，不是普通可挖矿）；
  - 只放 pumpjack、不供电也不触发；
  - **给 pumpjack 接电、让它真正开始抽取后，oil-processing 自动解锁**。
  - 因此触发条件可以理解为“让原油第一次被真实开采”，不是“放下建筑”。当前油区已有 1 台 pumpjack（#426，等待接管道/储罐）和局部蒸汽电（1 pump + boiler + engine，enet31）。
- 下一步：在油区接 pipe/storage tank → refinery → 化工（塑料/硫磺/硫酸），再补蓝瓶；或把原油/中间体运回主基地。
- 2026-10-25 进一步实测：pumpjack 已通过 2 根 pipe 接到 storage tank（tank 在 `354,430`，pumpjack 输出在 `354.5,433.5`）；tank 已有约 **4.8k crude-oil**，pumpjack 状态 working。
- 流体查询键名是 **`crude-oil`（带连字符）**，不是 `crude_oil`；用错键会误报 0。
- refinery 配方：15 钢 +10 齿轮 +10 电路 +10 管 +10 石砖；chemical-plant：5 钢 +5 齿轮 +5 电路 +5 管。油区已有 4 台石炉可现炼钢/砖，局部电 900 kW。
- 油区已放 `oil-refinery#447 @300.5,413.5` 和 `chemical-plant#449 @304.5,423.5`（尚未接电/接管道）。
- ** refinery 流体口：boxes1-2 是 input（南侧，pipe 需放在 `299.5/301.5,416.5`），boxes3-5 是 output（北侧，pipe 放在 `299.5/301.5/303.5,410.5`）。**
- **chemical-plant 流体口：boxes1-2 是 input（北侧，pipe 放在 `303.5/305.5,421.5`），boxes3-4 是 output（南侧，pipe 放在 `303.5/305.5,425.5`）。**
- 储罐连接：tank 在 `354,430`，其北侧连接需要 pipe 在 `353.5,428.5`；现有 pumpjack→tank 管道在 `354.5/355.5,432.5`。粗油到 refinery 可从 tank 北侧接出，沿 y≈424–431 找空管道路由（直线 y431 有 7 个阻塞 tile，需要绕行）。
- 下一步优先级：接电 refinery/chem → 粗油管 → 石油气管到 chem north inputs → 做 plastic；再补水管做 sulfur/acid。
- **5x5 的 oil-refinery 不能靠 small-electric-pole 供电**（小杆供电半径 2.5，refinery 中心到外侧最近杆距约 3.0–3.6）；必须用 medium-electric-pole（钢 2 + 铁棒 4 + 铜线 2）或 substation。chem plant 3x3 可以靠小杆。

## 1. 必查数据

- 配方：`recipes_query`（默认包含未解锁配方；不要用旧版 `enabled_only=true`）。
- 科技：`tech_tree`；确认前置、成本、科研包数量。
- 实体现状：`entity_detail`（状态名/库存/配方/落点/电网）。
- 产量：`production_stats`；只看“机器在动”不够，要看累计产出是否增长。
- 大范围资源：`resource_patches`；油区在独立陆块，最近缺口约 140 格水。

## 2. 已验证的关键事实

- 已研究：automation、automation-2、electric-mining-drill、electronics、engine、fluid-handling、landfill、logistic-science-pack、oil-gathering、oil-processing、steam-power、steel-processing。
- 电网：4 组蒸汽集群，3.6 MW；小杆供电半径 2.5，线长 7.5；蓝图后必须 `wire_poles`。
- 煤：4 锅炉满载约 0.9 煤/秒；高倍速会烧穿。煤炭点已建 3 钻+带+箱。
- 石头：landfill 50 石/格；**169 格 L 形桥已建成**（约 8450 石），角色已过桥；landfill 已用完。
- **speed 50 会让真实客户端掉线**（网络跟不上）；掉线后库存保留、重连可恢复。本存档稳定上限按 speed 20；掉线后先 `save`，重连后 `get_state` 核对背包。
- 火箭井不需要紫瓶/黄瓶；需要蓝瓶科技：concrete、rocket-fuel、processing-unit、logistic-robotics、LDS、advanced-material-processing-2。
- 白瓶配方：冰 1 + 铁板 2 + 碳 1 → 5 白瓶；在太空平台制造。
- 石油链研究包：约 925 红 + 925 绿（另加之前的 landfill 50）；必须自动绿瓶，不要再全手工。

## 3. 动作执行规则

1. 一次只提交一个阻塞 job；不要并行 `walk/mine/craft`。
2. 批量建造用 `build_entities`，坐标按实际实体 footprint 算；建完 `entity_detail` 抽查。
3. 机械臂方向 = **拾取方向**；`pickup_position`/`drop_position` 验证，不要凭直觉。
4. 任何 AM 都要有出口箱/下游；`full_output` 会反压整线。
5. 采矿钻落点必须是运输带/箱/炉；地面输出只出一件。运输带可铺矿上，箱/炉不可放未清矿格。
6. 电线杆：先放后 `wire_poles`；每台机器中心离杆 ≤2.5。
7. 修改配方用 `set_recipe`；不要拆了重放。
8. 长距离/跨水：先查 `land_gap` 思路；本存档无陆路，必须 landfill。

## 3.5 已跑通的自动化单元（2026-10-25）

- **自动传送带线**：`gear AM#450 @-28.5,60.5` → `belt AM#463 @-24.5,60.5`，铁板箱 `#452`、齿轮/铁板输入箱 `#453`、输出箱 `#465`；实测已自动产出 **46 transport-belt**。注意：两台 AM 必须 4 格中心距；输出 inserter 要贴到 AM 边缘（#464 @-22.5,60.5），否则会 waiting_for_source_items。
- **自动采矿/冶炼单元**：`electric-mining-drill#471 @-37.5,49.5` → `stone-furnace#99 @-37,52` → 输出箱 `#468`（已有 107 iron-plate）；煤箱 `#466 @-40.5,52.5` + inserter#467 自动加煤。矿石不是经传送带进炉，但采矿/熔炼/出料/加煤已经自动。
- **铁板闭环进展**：`#468` → inserter#493 → 长 belt（x=-34.5 向下到 y=65.5，再向东）→ inserter#495 → `#453`；`#453` 已有 232 iron-plate，传送带 AM 自动吃板；输出箱 `#465` 已有 **82 transport-belt**。`#452`（齿轮箱）暂时仍需人工补板，原因是分支侧带 `#526` 没有被主线侧载成功；下一步加 splitter 或把齿轮 AM 的输入箱移到主线可 inserter 的位置。EED1 已完成，medium pole 已解锁。
- 下一步优先：splitter/分支补齿轮箱 → 电路/机械臂/AM 输入接入总线 → refinery 供电/接管道 → 蓝瓶 → 火箭。
- **2026-10-25 Logistics 已研究，splitter#529 已装在 x=-34,y=60.5（方向南），两路输入（#468 左带、#537 右带）都已建。** 目前左路继续到 #453 正常；右支带 #530-#533 仍空，#452 未自动收到铁板，只能人工从 #453 补 200 plates。下一步检查 splitter 右侧输出/支带方向，或把 #452 的输入箱直接挪到主线旁边用 inserter 取料。传送带输出已到 314。
- 现有铁/煤/石 outpost 本身已有传送带+箱子；可直接把箱子作为自动供料点。
- EED1 研究已到 ~89%，完成后可造 medium pole，解决 refinery 供电。

## 3.6 2026-10-25 铁矿扩产与煤电（实测修正）

- **新矿冶线已跑通**：西矿铁箱 `#204 @-69.5,58.5` → 88 格主带 `y=60.5`（绕过 drill#148 后改地面直铺）→ 10 台石炉 `y=63, x=-64..-40` → 输出带 `y=65.5` → 铁板箱 `#633 @-36.5,65.5` → inserter#635 → 原铁板环线 `#453`。实测 `#453` 已积到 **1200+ 铁板**，`#633` 另有数百。
- **矿石缓冲箱会“假富”**：`#545/#546` 满 800 后电钻显示 `waiting_for_space_in_destination`。解决：用侧带把箱里的矿卸回主带（`#546` 东侧 inserter + 1 格南向带；`#545` 西侧 13 格立带）。箱子满 ≠ 有矿进炉。
- **脚本创建的 underground-belt 不会自动配对**：`build_entities` 连续放两端，两端 `belt_neighbours` 都为空，矿会吞进入口、出口不出料。要么用玩家放置/蓝图，要么别用地下带。本档已拆掉坏地下带，改为把挡路电钻迁到 `-61.5,57.5` 后地面直铺。
- **机械臂只抓近侧车道**：带上有料、机械臂 `status=working` 却不搬，常见原因是料在远侧车道。`#533/#455` 的齿轮供料就卡在这里。优先“箱→臂→机器”同侧直供，或先过 splitter 让两车道都有料；不要在远侧硬等。
- **齿轮 AM 供料不足**：一台基础机械臂约 1.2 板/秒，齿轮 AM 需要 2 板/秒，`#452` 会长期见底。短期先人工补板/保持传送带 AM 直接吃 `#453`；根治要研究 fast-inserter（或用两条供料臂）。传送带 AM 已能持续产出，`#465` 已 **1100+** 条。
- **煤电仍是第一瓶颈**：4 锅炉只有 `#128` 由 `#252` 的 88 格煤带自动供给；`#125/#36/#131` 仍需补煤（可远程 `insert radius=200`）。煤钻已迁到活矿格：`-31,43`、`-31,45`、`-27,43`，三台合计约 0.75 煤/秒。**speed 20 挂机会在几分钟内烧穿所有煤**；挂机/建造期固定 speed 1~5，移动再临时提速。
- **拆掉的死带**：y=57.5/58.5 的 20 格、x=-22.5 y=59.5..65.5 的 7 格、`-35.5,60.5` 的 1 格；保留 y=65.5 铁板环线与分拣器支路。
- **当前余量**：背包约 470 铁板、`#453` 约 1271 板、`#633` 约 341 板；新冶炼 10 炉因缺煤已停，补煤后即可恢复 ~3 板/秒。电钻 4 台（#151/#675/#677/#678）+ 3 台煤钻；`#471` 仍停在枯矿上。
- **下一步顺序**：先让煤箱 >200 再给 10 炉补煤（每炉 40）→ 研究 fast-inserter 修齿轮供料 → 炼油厂供电/接管 → 蓝瓶 → 火箭。

## 3.7 2026-10-25 石油/塑料打通（血泪教训）

- **炼油厂被石炉堵死输出**：原 refinery `#447 @300.5,413.5` 的北侧输出口正好被 `#424/#425` 两台石炉压住，`full_output` 不是没接管，而是管口被建筑占位。先把挡口建筑清掉，再用普通 pipe 逐格试探真正的 output 格（本档真输出是 `x=300.5/301.5, y≈420.5`，不是想当然的 299.5/303.5）。
- **脚本/蓝图创建的 pipe-to-ground 不可靠**：`place`/`blueprint_build` 都能放下两端，但不一定建立地下连接；`get_fluid_contents()` 一端有液、另一端全空就是没连上。不要再在这上面赌；**优先地面管**，必须跨管时先清空隧道上方的所有普通 pipe（地下管不能从普通 pipe 下面穿过）。
- **最稳解法：把 refinery 搬到 chem 旁边**。实际做法：拆 `#447`，在 `(298.5,423.5)` 重放；南侧接原油（从旧原油主管 `313.5,423.5` 向南绕到 `y=426.5` 再向西进炉），北侧出石油（`x=297.5..302.5,y=420.5` 再下到 `y=421.5` 进 chem 北输入）。移动后注意重新 `set_recipe` 和接线。
- **旧管会串液**：多次试接留下的 pipe 把 crude 灌进了 chem 输入管，表现为“石油管里有原油”。正确顺序是：先列出区域内所有 pipe，**全部拆掉**，再按“原油一条、石油一条”重建，最后用 fluid_contents 逐点验收。
- **塑料已打通**：研究 `plastics`（200 red + 200 green）后，chem 设 `plastic-bar`；每 2 塑料耗 1 煤 +20 石油气。煤要作为**物品**输入，不能只靠石油。输出 inserter 必须放在 `(306.5,424.5)` 向**西**取料（3x3 chem 东缘是 x305.5，306.5 才是贴边的一格），箱子放 `(307.5,424.5)`；放 307.5 取料会 `waiting_for_source_items`。
- **当前状态**：refinery/chem 都在 net31 上运行，chem 已产出 60+ 塑料（背包/箱/机器内合计约 100）；base 的 4 台锅炉在长时间 speed20 后再次缺煤，lab 已停止。`plastics` 已研究完成，`advanced-circuit / sulfur-processing / chemical-science-pack` 尚未研究，且红绿瓶已耗尽。
- **下一步**：先补 base 煤（煤钻仍在产，箱 `#252` 会回涨；远程 `take` + `insert radius=2000` 可补锅炉）→ 造红绿瓶研究 advanced-circuit 与 sulfur-processing → chem 产 sulfur/硫酸 → 化学瓶 → 蓝瓶 → 火箭。

## 4. 推荐优先级（下一轮）

1. 保煤：三台煤钻 → `#251` → `#252`；`#768` → 88 格带 → `#128`。煤箱低于 150 时先别开冶炼炉，优先给 `#125/#36/#131` 补煤。
2. 修齿轮：研究 fast-inserter，或加第二条供料臂/把齿轮 AM 输入改成同侧箱→臂→AM 直供。
3. 油区：给 refinery/chem 接 medium pole、原油管、水管；先出塑料/硫磺/硫酸。
4. 蓝瓶 + 多 lab；再火箭井/100 火箭部件；发射 starter pack；平台产白瓶。

## 5. 不要浪费时间的事

- 不要用 `can_place_entity` 单独判断箱子/熔炉在资源格上；以 `create_entity` 结果为准。
- 不要假设蓝图建筑会自己接电；必须 `wire_poles`。
- 不要在无煤自动补给时把速度拉到 20+ 长时间挂机。
- 不要忽略 `waiting_for_space_in_destination`：它通常是下游满/落点被占，不是缺电。
- 不要先做紫/黄瓶再火箭：本存档火箭井只需要蓝瓶链。

## 6. 常用调用顺序示例

```
decision_context(radius=12)
entity_detail(unit_number=...)
alerts(limit=50)
build_entities([...])  # 消耗背包物品
wire_poles()
entity_detail(radius=10, limit=20)  # 抽查
production_stats(items=["iron-plate","electronic-circuit"])
save()
```

详细 BUG 记录、产量、地图数据和后续路线见 `PHASE2-ROCKET-WHITE-SCIENCE-REPORT.md`。
