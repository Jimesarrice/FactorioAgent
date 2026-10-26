# 绿瓶科技：LLM 操作日志

环境：Factorio 2.1.23；peaceful 新存档；真实客户端 `LLM-Bot`；RCON 27017；模型 `Q3.5-9B:latest`（Ollama）。
目标：完成科技 `logistic-science-pack`（物流科技包/绿瓶）的研究。
结果：**`researched=true`**。最终电力：泵 #35、锅炉 #36、蒸汽机 #37、管道 #38/#39、lab #41、电线杆 #42；旧错接电力设备已拆除。

## 里程碑

| 阶段 | 结果 |
|---|---|
| 新存档（无敌对） | 通过：`enemy-base` 尺寸/频率 0，和平模式，进化/扩张关闭 |
| 采集与熔炼 | 通过：铁矿/铜矿/煤/石头，石炉炼铁板/铜板 |
| 红瓶生产 | 通过：手工合成 75 个 automation-science-pack |
| 实验室 | 通过：lab#41 在电源旁，供电正常 |
| 电力 | 通过：offshore-pump → boiler → steam-engine → 电网；电杆 #42 同时覆盖发动机和 lab |
| 绿瓶科技 | **通过**：`logistic-science-pack.researched=true` |

## 关键事件与修复

- **Q3.5 自主阶段**：模型完成了探矿、采矿、熔炼、造 lab、造泵/锅炉/蒸汽机；但在配方查询、trigger 科技、长距离寻路和电力拓扑上多次循环。
- **`recipe_info` 修复**：`LuaRecipe` 没有 `category` 字段（2.0 使用 `categories`），原先每次查询都抛 Lua 错误，模型只能反复猜配方名；修复后返回正确配方。
- **trigger 科技**：`research` 现在拒绝 trigger 科技并提示“需要 craft 触发物”，避免模型反复排队 `automation-science-pack`。
- **寻路**：长距离 `request_path` 失败时，walk 任务自动切换为直走 + 卡住绕行。
- **上下文**：动作结果从完整 state 压缩为 observation，避免 9B 模型在巨大 JSON 上打转。
- **旋转/拆除**：新增 `rotate_entity` / `dismantle_entity`；实测锅炉 0→8、管道拆除返物。旧错接的泵/锅炉/引擎/管道/电杆已全部拆除。
- **lab 迁移**：拆除 lab#18（回收 48 红瓶），在电源旁放置 lab#41（47.5,24.5），避免长距离拉电。

## 操作员接管后的实际动作（节选）

| tick | 动作 | 结果 |
|---:|---|---|
| 616049 | 从 furnace#14/#15 取铁板/铜板 | 50 铁板、30 铜板 |
| 626107–631234 | 走到石矿、采 10 石头 | `mined 10` |
| 633868–634360 | craft stone-furnace / boiler / steam-engine | 各 1 |
| 654538–654550 | 早期电力尝试 | 泵位失败；锅炉#19/引擎#20/电杆#21 放置 |
| 700925–701389 | 北侧清洁电力站 | 泵#35、锅炉#36、引擎#37、管道#38/#39 |
| 795650 | 给锅炉#36 加煤 | 蒸汽 200，引擎有蒸汽 |
| 838631 | rotate boiler#19 | direction 0→8 |
| 873470–904951 | 拆除旧电力、迁移 lab、布置电杆/lab | lab#41 获得电力 |
| 901797–904951 | 插入 75 红瓶并排队研究 | `research queued` |
| ~961000 | 检查科技 | **`researched=true`** |

## 完整 job 事件时间线（scenario journal，tick 634083–922787）

| tick | job | 结果 | detail | unit / 备注 |
|---:|---|---|---|---|
| 634114 | craft | ok | crafted 1 | boiler x1 |
| 634360 | craft | ok | crafted 1 | steam-engine x1 |
| 653948 | walk | ok | arrived |  |
| 654517 | craft | ok | crafted 15 | pipe x15 |
| 654538 | place | fail | player cannot build offshore-pump at 50.5,29.5 |  |
| 654542 | place | ok | player built boiler | boiler; pos={'x': 50, 'y': 30} |
| 654546 | place | ok | player built steam-engine | steam-engine; pos={'x': 48, 'y': 36} |
| 654550 | place | ok | player built small-electric-pole | small-electric-pole; pos={'y': 36.5, 'x': 50.5} |
| 700925 | craft | ok | crafted 1 | stone-furnace x1 |
| 701170 | craft | ok | crafted 1 | boiler x1 |
| 701385 | place | ok | player built offshore-pump | offshore-pump; pos={'x': 52.5, 'y': 36.5} |
| 701389 | place | ok | player built boiler | boiler; pos={'x': 51, 'y': 38} |
| 716241 | place | ok | player built pipe | pipe; pos={'x': 51.5, 'y': 36.5} |
| 716245 | place | ok | player built pipe | pipe; pos={'y': 39.5, 'x': 50.5} |
| 716249 | place | ok | player built pipe | pipe; pos={'y': 39.5, 'x': 51.5} |
| 716253 | place | ok | player built pipe | pipe; pos={'y': 39.5, 'x': 49.5} |
| 716257 | place | ok | player built pipe | pipe; pos={'y': 39.5, 'x': 48.5} |
| 716261 | place | ok | player built pipe | pipe; pos={'y': 39.5, 'x': 47.5} |
| 716265 | place | ok | player built pipe | pipe; pos={'y': 35.5, 'x': 46.5} |
| 716269 | place | ok | player built pipe | pipe; pos={'y': 36.5, 'x': 46.5} |
| 716273 | place | ok | player built pipe | pipe; pos={'y': 40.5, 'x': 49.5} |
| 716277 | place | ok | player built pipe | pipe; pos={'y': 40.5, 'x': 48.5} |
| 716281 | place | ok | player built pipe | pipe; pos={'y': 38.5, 'x': 46.5} |
| 758086 | insert | ok | inserted 5 | unit=23; coal x5 |
| 758090 | insert | ok | inserted 5 | unit=19; coal x5 |
| 758214 | wait | ok | waited |  |
| 792305 | walk | ok | arrived |  |
| 792731 | craft | ok | crafted 7 | pipe x7 |
| 792790 | craft | ok | crafted 1 | steam-engine x1 |
| 793005 | craft | fail | missing wood (0/1) |  |
| 793009 | place | ok | player built offshore-pump | offshore-pump; pos={'x': 55.5, 'y': 26.5} |
| 793013 | place | ok | player built boiler | boiler; pos={'x': 51.5, 'y': 26} |
| 793017 | place | ok | player built steam-engine | steam-engine; pos={'x': 51.5, 'y': 22} |
| 793021 | place | ok | player built pipe | pipe; pos={'x': 54.5, 'y': 26.5} |
| 793025 | place | ok | player built pipe | pipe; pos={'x': 53.5, 'y': 26.5} |
| 793029 | place | ok | player built small-electric-pole | small-electric-pole; pos={'y': 28.5, 'x': 51.5} |
| 795650 | insert | ok | inserted 10 | unit=36; coal x10 |
| 795774 | wait | ok | waited |  |
| 838631 | rotate | ok | rotated boiler | unit=19 |
| 838636 | dismantle | ok | dismantled pipe | unit=30; pos={'x': 46.5, 'y': 35.5} |
| 873470 | walk | fail | direct walk timeout |  |
| 876859 | dismantle | ok | dismantled small-electric-pole | unit=21; pos={'x': 50.5, 'y': 36.5} |
| 876863 | dismantle | ok | dismantled small-electric-pole | unit=40; pos={'x': 51.5, 'y': 28.5} |
| 876867 | dismantle | ok | dismantled boiler | unit=19; pos={'x': 50.5, 'y': 30} |
| 876871 | dismantle | ok | dismantled boiler | unit=23; pos={'x': 51.5, 'y': 38} |
| 876875 | dismantle | ok | dismantled offshore-pump | unit=22; pos={'x': 52.5, 'y': 36.5} |
| 876880 | dismantle | ok | dismantled steam-engine | unit=20; pos={'x': 48.5, 'y': 36.5} |
| 876884 | dismantle | ok | dismantled pipe | unit=24; pos={'x': 51.5, 'y': 36.5} |
| 876888 | dismantle | ok | dismantled pipe | unit=25; pos={'x': 50.5, 'y': 39.5} |
| 876892 | dismantle | ok | dismantled pipe | unit=26; pos={'x': 51.5, 'y': 39.5} |
| 876896 | dismantle | ok | dismantled pipe | unit=27; pos={'x': 49.5, 'y': 39.5} |
| 876900 | dismantle | ok | dismantled pipe | unit=28; pos={'x': 48.5, 'y': 39.5} |
| 876904 | dismantle | ok | dismantled pipe | unit=29; pos={'x': 47.5, 'y': 39.5} |
| 876908 | dismantle | ok | dismantled pipe | unit=31; pos={'x': 46.5, 'y': 36.5} |
| 876912 | dismantle | ok | dismantled pipe | unit=32; pos={'x': 49.5, 'y': 40.5} |
| 876916 | dismantle | ok | dismantled pipe | unit=33; pos={'x': 48.5, 'y': 40.5} |
| 876920 | dismantle | ok | dismantled pipe | unit=34; pos={'x': 46.5, 'y': 38.5} |
| 895654 | dismantle | ok | dismantled lab | unit=18; pos={'x': 51.5, 'y': 34.5} |
| 898391 | walk | ok | arrived |  |
| 898597 | place | ok | player built lab | lab; pos={'x': 47.5, 'y': 24} |
| 898601 | place | ok | player built small-electric-pole | small-electric-pole; pos={'x': 49.5, 'y': 24} |
| 901797 | insert | ok | inserted 65 | unit=41; automation-science-pack x65 |
| 904812 | craft | ok | crafted 10 | automation-science-pack x10 |
| 904947 | insert | ok | inserted 10 | unit=41; automation-science-pack x10 |
| 904951 | research | ok | research queued |  |
| 912033 | craft | ok | crafted 1 | automation-science-pack x1 |
| 912218 | insert | ok | inserted 1 | unit=41; automation-science-pack x1 |
| 912222 | insert | ok | inserted 10 | unit=36; coal x10 |
| 916309 | walk | ok | arrived |  |
| 916447 | mine | fail | no coal within 10 tiles |  |
| 922640 | walk | ok | arrived |  |
| 922783 | take | ok | took 50 | unit=17; coal x50 |
| 922787 | insert | ok | inserted 38 | unit=36; coal x38 |

## 最终研究确认

研究任务在 lab#41 通电并放入 75 个红瓶后开始；`research_progress` 从 0 递增，最终查询：

```text
logistic-science-pack.researched = true
force.research_progress = 0 (queue empty)
```

操作员在完成后把游戏速度恢复为 1，并执行 `save()`；当前存档保留 lab#41、泵#35、锅炉#36、引擎#37、管道#38/#39、电杆#42。

## 实体清单接口（辅助判断）

`nearby_entities`（MCP / LLM 工具）按距离输出附近实体，支持半径、名称、类型、是否包含自然资源、limit。示例：

```json
{"radius":30,"include_nature":false,"limit":20}
```

当前返回 8 个建筑：`stone-furnace#17`、`boiler#36`、`lab#41`、`small-electric-pole#42`、`pipe#39`、`pipe#38`、`offshore-pump#35`、`steam-engine#37`。
需要方向/可拆除性时，`rotate_entity`/`dismantle_entity` 的返回会带 direction/unit_number；实体表用于定位目标。

## 证据

- 原始事件：`state/bot-events.jsonl`、`state/_green_events_final.json`
- MCP 覆盖：`docs/evidence/mcp-coverage.txt`
- 思维链：[GREEN-SCIENCE-REASONING-LOG.md](GREEN-SCIENCE-REASONING-LOG.md)