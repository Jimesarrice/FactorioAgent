# 本地 Web 控制台

零第三方依赖的单机控制台，用来启动/停止 Bot、观察游戏、查看模型决策与配置本地/云端 LLM。

## 启动

```bash
cd <INSTALL_DIR>
python -m bridge.webui --port 8090
# 浏览器打开 http://127.0.0.1:8090
```

默认只绑定 `127.0.0.1`。`webui.host/port` 修改后需要重启控制台。

界面默认中文，右上角“语言 / Language”可切换中文或 English；选择保存在浏览器 `localStorage`（键名 `factorio-webui-lang`），刷新后保持。切换语言会即时重绘状态卡片、决策日志和配置表单，不需要重启控制台。

## 页面

- **Dashboard**
  - RCON 在线状态、Bot 进程状态（`RUNNING` / `STOPPED` / `EXITED <code>`）。
  - 玩家名/位置/表面/血量/控制器、当前 job/队列、tick/speed。
  - 背包、研究、附近资源与实体、Bot 进程日志。
  - 按钮：Start/Stop、Pause/Resume、Save、发送控制台指令。
- **Decisions & Reasoning**
  - `assistant`：provider 返回的 `reasoning_content`（标注 “provider-supplied”）和正文。
  - `tool_call` / `tool_result`：每次工具调用及结果，可折叠。
  - `cycle_start` / `cycle_end` / `error` / `provider_fallback`。
  - 不生成或补写模型的隐藏思维链；模型不返回 reasoning 时这里就没有。
- **Settings**
  - LLM：`provider=auto|local|cloud`、本地/云端 base URL、model、API key、local 失败回退云端、temperature。
  - Bot：goal、玩家名、间隔、每轮工具数、turn-based、是否自动起服/起客户端，以及 exe/存档/mods/settings/config/RCON。
  - Web：host/port。

## 本地模型

任何 OpenAI-compatible 端点都行：

| 运行时 | base URL | 备注 |
|---|---|---|
| Ollama | `http://127.0.0.1:11434/v1` | `ollama serve`，模型名如 `Q3.5-9B:latest` |
| LM Studio | `http://127.0.0.1:1234/v1` | 打开本地 server |
| llama.cpp | `http://127.0.0.1:8080/v1` | `llama-server` |
| vLLM | `http://127.0.0.1:8000/v1` | OpenAI-compatible |

云端仍支持 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`，也可以在 Settings 里填。`provider=auto` 先试本地，失败且开启 `fallback_cloud` 时再试云端。

## 配置与密钥

- 配置文件：`state/webui.json`（本机明文；不要把控制台暴露到公网）。
- API 返回的 key 是 `***`；UI 留空保存会保留原值，不会把掩码写回。
- 要清除 key，可在停止 Bot 后直接编辑 `state/webui.json` 把对应字段设为 `""`。
- 事件日志：`state/bot-events.jsonl`（每行一条 JSON，UTF-8）。
- Bot 进程输出：`state/webui-bot.out`（UTF-8）。
- 停止通过 `state/bot-stop.flag` 通知子进程；超时后回收进程树。

## HTTP API

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/state` | 游戏状态 + 进程状态 + 当前 LLM 摘要 |
| GET | `/api/logs?limit=400` | 事件日志 |
| GET | `/api/status` | 仅进程状态 |
| GET/POST | `/api/config` | 读取/保存配置（key 掩码） |
| GET | `/api/models?provider=local\|cloud` | 模型列表（OpenAI `/models`） |
| POST | `/api/models` | 用未保存的 base/key 临时列出模型 |
| POST | `/api/control` | `start`/`stop`/`pause`/`resume`/`save`/`instruct`/`set_eval` |

## 进程生命周期

- `start`：写空事件日志，启动 `python -m bridge.bot_loop --config state/webui.json`；子进程环境强制 `PYTHONIOENCODING=utf-8`、`PYTHONUTF8=1`。
- 子进程自行退出：`phase=exited`，记录退出码。
- 显式 `stop`：写 stop flag，等待最多 30 秒；未退出则回收进程树；最终 `phase=stopped`、`pid=null`。
- `bot_loop` 若配置了 `start_server/start_client`，会负责启动并在退出时保存/关闭它们；否则连接已在运行的服务器和玩家。

## 已验证

- fake-local OpenAI 端点：模型列表、连续 cycles、reasoning/决策事件、start/stop、中文 UTF-8、key 掩码。
- 真实本地 Ollama `Q3.5-9B:latest`：`/v1/models`、直接 tool-calling、Web UI 启动真实服务端/客户端、`say` 工具调用与 reasoning 捕获均通过；详见 [TEST-REPORT.md](TEST-REPORT.md) 6.5。
- 真实云端 API 和所有的长时自主通关尚未验证（需要云端 key 与长跑）。

## 安全边界

- 控制台没有账号体系，默认 localhost；不要 `--host 0.0.0.0` 开到公网。
- `lua_eval` 默认关闭；它绕过正常玩家约束。Web UI 的 `set_eval` 动作只在明确需要时使用。
- API key 明文保存在 `state/webui.json`，请自行控制文件权限与备份。
