const $ = (sel) => document.querySelector(sel);
const LANG_KEY = "factorio-webui-lang";
const state = {
  config: null,
  lastEventsKey: "",
  lastData: null,
  lastEvents: null,
  savedKeys: {},
  busy: false,
};

const I18N = {
  zh: {
    "provider.auto": "自动",
    "provider.local": "本地",
    "provider.cloud": "云端",
    "page.title": "Factorio 智能体控制台",
    "brand.suffix": "/ 智能体控制台",
    "brand.sub": "真实玩家 LLM 操作台",
    "lang.label": "语言",
    "status.offline": "RCON 未连接",
    "status.online": "RCON 在线",
    "status.webuiError": "Web 控制台错误",
    "status.model": "模型 —",
    "status.botStopped": "机器人未启动",
    "status.botRunning": "机器人运行中（{pid}）",

    "tab.dashboard": "仪表盘",
    "tab.decisions": "决策与推理",
    "tab.settings": "设置",

    "dashboard.title": "实时游戏状态",
    "dashboard.start": "启动机器人",
    "dashboard.stop": "停止机器人",
    "dashboard.pause": "暂停",
    "dashboard.resume": "恢复",
    "dashboard.save": "保存游戏",

    "card.bot": "机器人进程",
    "card.player": "玩家",
    "card.position": "坐标 / 所在表面",
    "card.health": "生命值",
    "card.job": "当前任务",
    "card.tick": "游戏刻 / 速度",

    "section.inventory": "背包",
    "section.research": "研究",
    "section.resources": "附近资源",
    "section.entities": "附近实体",
    "section.console": "控制台指令",
    "section.botlog": "机器人进程日志",
    "research.current": "当前",
    "research.progress": "进度",
    "research.queue": "队列",
    "research.players": "在线玩家",
    "console.priority": "最高优先级；也支持游戏内",
    "console.or": "或",
    "console.placeholder": "例如：先做 20 个铁齿轮，然后造一个石炉并烧铁矿",
    "console.send": "发送",

    "common.empty": "空",
    "common.none": "无",
    "common.idle": "空闲",
    "inventory.count": "{count} 种物品",
    "job.queued": "排队：{list}",
    "job.noQueue": "无排队任务",

    "decisions.title": "决策与推理",
    "decisions.filterReasoning": "推理",
    "decisions.filterTools": "工具调用",
    "decisions.filterResults": "工具结果",
    "decisions.autoscroll": "自动滚动",
    "decisions.note": "这里显示模型/服务商实际返回的推理内容（reasoning，若有）以及工具决策与结果；不会伪造隐藏思维链。不同本地/云端模型的 reasoning 字段支持不同。",
    "decisions.empty": "启动机器人后这里会显示决策。",

    "settings.title": "配置",
    "settings.save": "保存配置",
    "settings.testModels": "测试 / 列出模型",
    "settings.note1": "配置保存在本机",
    "settings.note2": "。API 密钥以掩码显示，留空/保持",
    "settings.note3": "不会覆盖原值。Web 控制台默认只绑定 127.0.0.1。",
    "settings.llm": "LLM",
    "settings.bot": "机器人",
    "settings.web": "Web 控制台",
    "settings.provider": "提供方",
    "settings.providerAuto": "自动（本地优先，失败可回退云端）",
    "settings.providerLocal": "本地（OpenAI-compatible）",
    "settings.providerCloud": "云端（OpenAI-compatible）",
    "settings.temperature": "温度",
    "settings.localBase": "本地基础 URL",
    "settings.localModel": "本地模型",
    "settings.localKey": "本地 API 密钥（可选）",
    "settings.cloudBase": "云端基础 URL",
    "settings.cloudModel": "云端模型",
    "settings.cloudKey": "云端 API 密钥",
    "settings.fallback": "本地失败时回退云端",
    "settings.goal": "目标",
    "settings.playerName": "玩家名",
    "settings.interval": "间隔（秒）",
    "settings.turns": "每轮工具调用数",
    "settings.turnBased": "回合制（思考时暂停）",
    "settings.startServer": "启动服务端",
    "settings.startClient": "启动机器人客户端",
    "settings.serverExe": "服务端可执行文件",
    "settings.clientExe": "客户端可执行文件",
    "settings.clientPort": "机器人客户端 UDP 端口",
    "settings.clientDataDir": "机器人客户端数据目录",
    "settings.clientMods": "机器人客户端 Mod 目录",
    "settings.clientModSource": "Mod 来源（Steam profile）",
    "settings.serverSave": "服务端存档",
    "settings.serverMods": "服务端 Mod 目录",
    "settings.serverSettings": "服务端设置",
    "settings.serverConfig": "服务端配置（write-data）",
    "settings.rconHost": "RCON 主机",
    "settings.rconPort": "RCON 端口",
    "settings.rconPassword": "RCON 密码",
    "settings.host": "主机",
    "settings.port": "端口",
    "settings.webNote": "修改主机/端口需要重启 Web 控制台。",
    "settings.keySaved": "已保存（留空保持）",
    "settings.testing": "测试中…",
    "settings.modelsCount": "{count} 个模型",
    "settings.failed": "失败",

    "footer.left": "Factorio 智能体控制台",
    "footer.right": "仅本机访问 · 密钥不会离开这台机器",

    "bot.running": "运行中",
    "bot.stopped": "已停止",
    "bot.exited": "已退出 {code}",
    "bot.pid": "进程号 {pid}",
    "bot.exitedFoot": "进程异常结束",

    "player.waiting": "等待 {name} 连接",
    "player.foot": "#{index} · {role} · 控制器 {controller}",
    "player.admin": "管理员",
    "player.player": "玩家",
    "player.notConnected": "未连接",
    "player.guiOpened": "已打开界面",

    "job.walk": "行走",
    "job.mine": "采矿",
    "job.craft": "合成",
    "job.place": "放置",
    "job.insert": "装入",
    "job.take": "取出",
    "job.research": "研究",
    "job.wait": "等待",
    "job.say": "发言",
    "job.build_blueprint": "蓝图建造",
    "job.space": "太空操作",

    "resources.meta": "距离 {distance} · 格数 {tiles} · 总量 {total}",
    "entities.meta": "距离 {distance}",

    "feed.reasoning": "推理（模型服务商返回）",
    "feed.emptyAssistant": "（助手消息为空）",
    "feed.goalCycle": "目标 / 本轮",
    "feed.arguments": "参数",
    "feed.result": "结果",
    "feed.toolCallName": "工具调用：{name}",
    "feed.toolResultName": "工具结果：{name}",
    "feed.tool": "工具",
    "feed.toolResult": "工具结果",
    "feed.reasoningOnly": "（模型本轮只返回了推理，没有正文）",
    "feed.emptyResponse": "（模型返回空响应）",
    "feed.maxTurns": "（已达到最大工具轮数）",

    "event.assistant": "助手",
    "event.cycle_start": "周期开始",
    "event.cycle_end": "周期结束",
    "event.tool_call": "工具调用",
    "event.tool_result": "工具结果",
    "event.error": "错误",
    "event.provider_fallback": "模型回退",
    "event.event": "事件",

    "toast.configSaved": "配置已保存",
    "toast.startOk": "机器人已启动",
    "toast.stopOk": "机器人已停止",
    "toast.pauseOk": "游戏已暂停",
    "toast.resumeOk": "游戏已恢复",
    "toast.saveOk": "游戏已保存",
    "toast.instructOk": "指令已发送",
    "toast.actionOk": "{action} 完成",
    "toast.modelsFound": "找到 {count} 个模型",
    "toast.modelListFailed": "获取模型列表失败",
  },
  en: {
    "provider.auto": "auto",
    "provider.local": "local",
    "provider.cloud": "cloud",
    "page.title": "Factorio Agent Console",
    "brand.suffix": "/ AGENT CONSOLE",
    "brand.sub": "real-player LLM operator",
    "lang.label": "Language",
    "status.offline": "RCON offline",
    "status.online": "RCON online",
    "status.webuiError": "webui error",
    "status.model": "model —",
    "status.botStopped": "bot stopped",
    "status.botRunning": "bot running ({pid})",

    "tab.dashboard": "Dashboard",
    "tab.decisions": "Decisions & Reasoning",
    "tab.settings": "Settings",

    "dashboard.title": "Live game state",
    "dashboard.start": "Start bot",
    "dashboard.stop": "Stop bot",
    "dashboard.pause": "Pause",
    "dashboard.resume": "Resume",
    "dashboard.save": "Save game",

    "card.bot": "Bot process",
    "card.player": "Player",
    "card.position": "Position / surface",
    "card.health": "Health",
    "card.job": "Current job",
    "card.tick": "Tick / speed",

    "section.inventory": "Inventory",
    "section.research": "Research",
    "section.resources": "Nearby resources",
    "section.entities": "Nearby entities",
    "section.console": "Console instruction",
    "section.botlog": "Bot process log",
    "research.current": "Current",
    "research.progress": "Progress",
    "research.queue": "Queue",
    "research.players": "Players online",
    "console.priority": "Highest priority; also accepts in-game",
    "console.or": "or",
    "console.placeholder": "e.g. craft 20 iron gears, then build a stone furnace and smelt iron ore",
    "console.send": "Send",

    "common.empty": "empty",
    "common.none": "none",
    "common.idle": "idle",
    "inventory.count": "{count} item types",
    "job.queued": "queued: {list}",
    "job.noQueue": "no queued jobs",

    "decisions.title": "Decisions & reasoning",
    "decisions.filterReasoning": "reasoning",
    "decisions.filterTools": "tool calls",
    "decisions.filterResults": "tool results",
    "decisions.autoscroll": "autoscroll",
    "decisions.note": "Shows reasoning actually returned by the model/provider (if any) plus tool decisions and results; hidden chain-of-thought is never fabricated. Support for the reasoning field varies by local/cloud model.",
    "decisions.empty": "Start the bot to see decisions.",

    "settings.title": "Configuration",
    "settings.save": "Save config",
    "settings.testModels": "Test / list models",
    "settings.note1": "Config is stored locally in",
    "settings.note2": ". API keys are masked; leaving the field empty or keeping",
    "settings.note3": "will not overwrite the saved value. The console binds to 127.0.0.1 by default.",
    "settings.llm": "LLM",
    "settings.bot": "Bot",
    "settings.web": "Web console",
    "settings.provider": "Provider",
    "settings.providerAuto": "auto (local first, fall back to cloud)",
    "settings.providerLocal": "local (OpenAI-compatible)",
    "settings.providerCloud": "cloud (OpenAI-compatible)",
    "settings.temperature": "Temperature",
    "settings.localBase": "Local base URL",
    "settings.localModel": "Local model",
    "settings.localKey": "Local API key (optional)",
    "settings.cloudBase": "Cloud base URL",
    "settings.cloudModel": "Cloud model",
    "settings.cloudKey": "Cloud API key",
    "settings.fallback": "Fall back to cloud if local fails",
    "settings.goal": "Goal",
    "settings.playerName": "Player name",
    "settings.interval": "Interval (s)",
    "settings.turns": "Turns per cycle",
    "settings.turnBased": "turn-based (pause while thinking)",
    "settings.startServer": "Start server",
    "settings.startClient": "Start bot client",
    "settings.serverExe": "Server executable",
    "settings.clientExe": "Client executable",
    "settings.clientPort": "Bot client UDP port",
    "settings.clientDataDir": "Bot client data dir",
    "settings.clientMods": "Bot client mod dir",
    "settings.clientModSource": "Mod source (Steam profile)",
    "settings.serverSave": "Server save",
    "settings.serverMods": "Server mods",
    "settings.serverSettings": "Server settings",
    "settings.serverConfig": "Server config (write-data)",
    "settings.rconHost": "RCON host",
    "settings.rconPort": "RCON port",
    "settings.rconPassword": "RCON password",
    "settings.host": "Host",
    "settings.port": "Port",
    "settings.webNote": "Changing host/port requires restarting the console.",
    "settings.keySaved": "saved (leave blank to keep)",
    "settings.testing": "testing...",
    "settings.modelsCount": "{count} models",
    "settings.failed": "failed",

    "footer.left": "Factorio Agent Console",
    "footer.right": "localhost only · keys stay on this machine",

    "bot.running": "RUNNING",
    "bot.stopped": "STOPPED",
    "bot.exited": "EXITED {code}",
    "bot.pid": "pid {pid}",
    "bot.exitedFoot": "process ended unexpectedly",

    "player.waiting": "waiting for {name}",
    "player.foot": "#{index} · {role} · controller {controller}",
    "player.admin": "admin",
    "player.player": "player",
    "player.notConnected": "not connected",
    "player.guiOpened": "GUI opened",

    "job.walk": "walk",
    "job.mine": "mine",
    "job.craft": "craft",
    "job.place": "place",
    "job.insert": "insert",
    "job.take": "take",
    "job.research": "research",
    "job.wait": "wait",
    "job.say": "say",
    "job.build_blueprint": "build blueprint",
    "job.space": "space",

    "resources.meta": "d={distance} · tiles={tiles} · total={total}",
    "entities.meta": "d={distance}",

    "feed.reasoning": "REASONING (provider-supplied)",
    "feed.emptyAssistant": "(empty assistant message)",
    "feed.goalCycle": "GOAL / CYCLE",
    "feed.arguments": "arguments",
    "feed.result": "result",
    "feed.toolCallName": "tool call: {name}",
    "feed.toolResultName": "tool result: {name}",
    "feed.tool": "tool",
    "feed.toolResult": "tool result",
    "feed.reasoningOnly": "(model ended with reasoning only)",
    "feed.emptyResponse": "(empty response)",
    "feed.maxTurns": "(max turns reached)",

    "event.assistant": "assistant",
    "event.cycle_start": "cycle start",
    "event.cycle_end": "cycle end",
    "event.tool_call": "tool call",
    "event.tool_result": "tool result",
    "event.error": "error",
    "event.provider_fallback": "provider fallback",
    "event.event": "event",

    "toast.configSaved": "Config saved",
    "toast.startOk": "Bot started",
    "toast.stopOk": "Bot stopped",
    "toast.pauseOk": "Game paused",
    "toast.resumeOk": "Game resumed",
    "toast.saveOk": "Game saved",
    "toast.instructOk": "Instruction sent",
    "toast.actionOk": "{action} ok",
    "toast.modelsFound": "Found {count} models",
    "toast.modelListFailed": "model list failed",
  },
};

let lang = "zh";
try {
  if (localStorage.getItem(LANG_KEY) === "en") lang = "en";
} catch (e) {
  // localStorage can be unavailable in hardened browsers; default to Chinese.
}

function t(key, params = {}) {
  const table = I18N[lang] || I18N.zh;
  let out = table[key] ?? I18N.zh[key] ?? key;
  for (const [k, v] of Object.entries(params)) {
    out = out.split(`{${k}}`).join(String(v));
  }
  return out;
}

function errorText(message) {
  const raw = String(message || "");
  if (lang !== "zh") return raw || "operation failed";
  const map = [
    [/bot is already running/i, "机器人已在运行"],
    [/unknown action[: ]+(\S+)/i, (match) => `未知操作：${match[1]}`],
    [/invalid config/i, "配置无效"],
    [/eval is disabled/i, "Lua eval 未启用"],
    [/RCON connection closed/i, "RCON 连接已断开"],
    [/Connection refused/i, "连接被拒绝，请确认服务端和 RCON 已启动"],
  ];
  for (const [pattern, replacement] of map) {
    const match = raw.match(pattern);
    if (match) return typeof replacement === "function" ? replacement(match) : replacement;
  }
  return raw ? `错误：${raw}` : "操作失败";
}

function jobLabel(kind) {
  if (!kind) return t("common.idle");
  const key = "job." + kind;
  const translated = t(key);
  return translated === key ? kind : translated;
}

function providerLabel(provider) {
  const value = provider || "auto";
  const key = "provider." + value;
  const translated = t(key);
  return translated === key ? value : translated;
}

function eventLabel(type) {
  const key = "event." + type;
  const translated = t(key);
  return translated === key ? (type || t("event.event")) : translated;
}

function fmtTime(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString(lang === "zh" ? "zh-CN" : "en-US");
}

function applyStaticTranslations() {
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  document.title = t("page.title");
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAria));
  });
  const select = $("#lang-select");
  if (select) select.value = lang;
}

function updateKeyPlaceholders() {
  for (const [name, saved] of Object.entries(state.savedKeys || {})) {
    const el = document.querySelector(`[name="llm.${name}_api_key"]`);
    if (el) el.placeholder = saved ? t("settings.keySaved") : "***";
  }
}

function applyLanguage() {
  setToast("");
  applyStaticTranslations();
  updateKeyPlaceholders();
  if (state.lastData) {
    renderState(state.lastData);
  } else {
    setTop("", t("status.offline"));
  }
  if (state.lastEvents) {
    const feed = $("#feed");
    const scroll = feed.scrollTop;
    renderFeed(state.lastEvents);
    feed.scrollTop = scroll;
  }
}

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body.slice(0, 300)}`);
  }
  return res.json();
}

function setToast(message, kind = "") {
  const el = $("#toast");
  el.textContent = message || "";
  el.className = "toast " + kind;
  if (message) setTimeout(() => { if (el.textContent === message) { el.textContent = ""; el.className = "toast"; } }, 6000);
}

function setTop(kind, label) {
  const dot = $("#conn-dot");
  dot.className = "dot " + (kind || "");
  $("#conn-label").textContent = label;
}

function text(el, value) {
  el.textContent = value === undefined || value === null || value === "" ? "—" : String(value);
}

function tab(name) {
  document.querySelectorAll(".tab").forEach((el) => el.classList.toggle("active", el.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((el) => el.classList.toggle("active", el.id === "tab-" + name));
  if (name === "decisions") refreshLogs(true);
}

document.querySelectorAll(".tab").forEach((el) => el.addEventListener("click", () => tab(el.dataset.tab)));

$("#lang-select").addEventListener("change", (event) => {
  lang = event.target.value === "en" ? "en" : "zh";
  try { localStorage.setItem(LANG_KEY, lang); } catch (e) { /* ignore */ }
  applyLanguage();
});

// ---------------------------------------------------------------- config
function formSet(name, value) {
  const el = document.querySelector(`[name="${name}"]`);
  if (!el) return;
  if (el.type === "checkbox") el.checked = Boolean(value);
  else el.value = value === undefined || value === null ? "" : value;
}

function formGet(name) {
  const el = document.querySelector(`[name="${name}"]`);
  if (!el) return undefined;
  return el.type === "checkbox" ? el.checked : el.value;
}

function fillConfig(cfg) {
  state.config = cfg;
  const saved = { local: false, cloud: false };
  const fields = [
    "llm.provider", "llm.temperature", "llm.local_base_url", "llm.local_model",
    "llm.local_api_key", "llm.cloud_base_url", "llm.cloud_model", "llm.cloud_api_key",
    "llm.fallback_cloud", "bot.goal", "bot.player_name", "bot.interval", "bot.turns",
    "bot.turn_based", "bot.start_server", "bot.start_client", "bot.server_exe",
    "bot.client_exe", "bot.client_port", "bot.client_data_dir", "bot.client_mod_dir",
    "bot.client_mod_source", "bot.server_save", "bot.server_mods", "bot.server_settings",
    "bot.server_config", "bot.host", "bot.rcon_port", "bot.rcon_password",
    "webui.host", "webui.port",
  ];
  for (const field of fields) {
    let value = cfg;
    for (const key of field.split(".")) value = value && value[key];
    if (field.endsWith("_api_key")) {
      if (field.includes("local")) saved.local = Boolean(value);
      if (field.includes("cloud")) saved.cloud = Boolean(value);
      const el = document.querySelector(`[name="${field}"]`);
      if (el) el.value = "";
    } else {
      formSet(field, value);
    }
  }
  state.savedKeys = saved;
  updateKeyPlaceholders();
  updateTopModel(cfg);
}

function collectConfig() {
  const out = { llm: {}, bot: {}, webui: {} };
  for (const el of document.querySelectorAll("#config-form [name]")) {
    const [section, key] = el.name.split(".");
    if (!out[section] || !key) continue;
    let value = el.type === "checkbox" ? el.checked : el.value;
    if (el.type === "number") value = value === "" ? 0 : Number(value);
    out[section][key] = value;
  }
  return out;
}

function updateTopModel(cfg) {
  const llm = (cfg && cfg.llm) || {};
  const provider = llm.provider || "auto";
  const model = provider === "local" ? llm.local_model : provider === "cloud" ? llm.cloud_model : (llm.local_model || llm.cloud_model);
  $("#model-label").textContent = `${providerLabel(provider)} · ${model || "—"}`;
}

async function loadConfig() {
  const cfg = await api("/api/config");
  fillConfig(cfg);
}

async function saveConfig(showToast = true) {
  const cfg = await api("/api/config", { method: "POST", body: JSON.stringify({ config: collectConfig() }) });
  fillConfig(cfg.config);
  if (showToast) setToast(t("toast.configSaved"), "ok");
  return cfg.config;
}

$("#btn-save-config").addEventListener("click", async () => {
  try { await saveConfig(true); } catch (e) { setToast(errorText(e.message), "err"); }
});

$("#config-form").addEventListener("submit", (event) => event.preventDefault());

$("#btn-test-models").addEventListener("click", async () => {
  const status = $("#model-test-status");
  status.textContent = t("settings.testing");
  try {
    await saveConfig(false);
    const provider = formGet("llm.provider") === "cloud" ? "cloud" : "local";
    const data = await api(`/api/models?provider=${encodeURIComponent(provider)}`);
    if (data.ok) {
      const list = $("#model-list");
      list.replaceChildren();
      for (const model of data.models || []) {
        const option = document.createElement("option");
        option.value = model;
        list.appendChild(option);
      }
      const count = (data.models || []).length;
      status.textContent = t("settings.modelsCount", { count });
      setToast(t("toast.modelsFound", { count }), "ok");
    } else {
      status.textContent = t("settings.failed");
      setToast(data.error ? errorText(data.error) : t("toast.modelListFailed"), "err");
    }
  } catch (e) {
    status.textContent = t("settings.failed");
    setToast(errorText(e.message), "err");
  }
});

// ---------------------------------------------------------------- controls
const ACTION_TOAST = {
  start: "toast.startOk",
  stop: "toast.stopOk",
  pause: "toast.pauseOk",
  resume: "toast.resumeOk",
  save: "toast.saveOk",
  instruct: "toast.instructOk",
};

async function control(action, payload = {}) {
  try {
    const res = await api("/api/control", { method: "POST", body: JSON.stringify({ action, ...payload }) });
    if (res && res.ok === false && res.error) setToast(errorText(res.error), "err");
    else setToast(t(ACTION_TOAST[action] || "toast.actionOk", { action }), "ok");
    await refreshState();
    return res;
  } catch (e) {
    setToast(errorText(e.message), "err");
  }
}

$("#btn-start").addEventListener("click", async () => {
  try { await saveConfig(false); } catch (e) { setToast(errorText(e.message), "err"); return; }
  await control("start");
});
$("#btn-stop").addEventListener("click", () => control("stop"));
$("#btn-pause").addEventListener("click", () => control("pause"));
$("#btn-resume").addEventListener("click", () => control("resume"));
$("#btn-save").addEventListener("click", () => control("save"));
$("#btn-instruct").addEventListener("click", async () => {
  const input = $("#instruct-input");
  const value = input.value.trim();
  if (!value) return;
  await control("instruct", { text: value });
  input.value = "";
});
$("#instruct-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter") { event.preventDefault(); $("#btn-instruct").click(); }
});

// ---------------------------------------------------------------- state
async function refreshState() {
  if (state.busy) return;
  state.busy = true;
  try {
    const data = await api("/api/state");
    renderState(data);
  } catch (e) {
    setTop("err", t("status.webuiError"));
  } finally {
    state.busy = false;
  }
}

function renderState(data) {
  state.lastData = data;
  const bot = data.bot || {};
  const running = !!bot.running;
  const phase = bot.phase || (running ? "running" : "idle");
  const procLabel = running ? t("bot.running")
    : phase === "exited" ? t("bot.exited", { code: bot.exit_code ?? "?" })
    : t("bot.stopped");
  $("#bot-label").textContent = running ? t("status.botRunning", { pid: bot.pid || "?" }) : t("status.botStopped");
  text($("#bot-process"), procLabel);
  text($("#bot-foot"), running && bot.pid ? t("bot.pid", { pid: bot.pid }) : (phase === "exited" ? t("bot.exitedFoot") : ""));
  $("#bot-log").textContent = bot.log_tail || "—";
  $("#btn-start").disabled = running;
  $("#btn-stop").disabled = !running;
  $("#btn-pause").disabled = !data.ok;
  $("#btn-resume").disabled = !data.ok;
  $("#btn-save").disabled = !data.ok;

  if (!data.ok) {
    setTop("err", t("status.offline"));
    return;
  }
  setTop("on", t("status.online"));
  const st = data.state || {};
  const player = st.player || {};
  const ch = st.character || {};
  const pos = ch.position || {};
  text($("#player-name"), player.connected ? player.name : t("player.waiting", { name: st.bot_name || "LLM-Bot" }));
  text($("#player-foot"), player.connected
    ? t("player.foot", {
        index: player.index,
        role: player.admin ? t("player.admin") : t("player.player"),
        controller: player.controller_type,
      })
    : t("player.notConnected"));
  text($("#player-pos"), player.connected ? `${pos.x ?? "—"}, ${pos.y ?? "—"}` : "—");
  text($("#player-surface"), player.physical_surface || "—");
  text($("#player-hp"), ch.alive ? `${Math.round(ch.health)} / ${Math.round(ch.max_health)}` : "—");
  text($("#player-controller"), player.opened_self ? t("player.guiOpened") : "");
  const job = st.job;
  text($("#job-kind"), job ? jobLabel(job.kind) : t("common.idle"));
  text($("#job-detail"), job ? `${job.phase || ""} ${job.detail || ""}` : "");
  text($("#tick"), st.tick !== undefined ? `${st.tick} · x${st.speed ?? 1}` : "—");
  const queue = st.queue || [];
  text($("#queue"), queue.length
    ? t("job.queued", { list: queue.map((item) => `${jobLabel(item.kind)}#${item.id}`).join(", ") })
    : t("job.noQueue"));

  const inventory = ch.inventory || [];
  const invEl = $("#inventory");
  invEl.replaceChildren();
  invEl.classList.toggle("empty", inventory.length === 0);
  if (!inventory.length) invEl.textContent = t("common.empty");
  else for (const item of inventory) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.append(`${item.name} `);
    const count = document.createElement("b");
    count.textContent = `x${item.count}`;
    chip.appendChild(count);
    invEl.appendChild(chip);
  }
  text($("#inv-count"), t("inventory.count", { count: inventory.length }));

  const force = st.force || {};
  text($("#research-current"), force.current_research || t("common.none"));
  text($("#research-progress"), `${Math.round(100 * (force.research_progress || 0) * 10) / 10}%`);
  const researchQueue = force.research_queue || [];
  text($("#research-queue"), researchQueue.length ? researchQueue.join(", ") : t("common.empty"));
  text($("#players-online"), `${force.connected_players ?? 0} / ${force.players ?? 0}`);

  renderList($("#resources"), st.resources || [], (resource) => [
    `${resource.name} @ ${resource.nearest?.x},${resource.nearest?.y}`,
    t("resources.meta", {
      distance: resource.nearest?.distance?.toFixed?.(1) ?? "?",
      tiles: resource.tiles ?? "?",
      total: resource.total_amount ?? "?",
    }),
  ]);
  renderList($("#entities"), st.entities || [], (entity) => [
    `${entity.name}${entity.unit_number ? " #" + entity.unit_number : ""}`,
    `@ ${entity.x},${entity.y} · ${t("entities.meta", { distance: entity.distance?.toFixed?.(1) ?? "?" })}`,
  ]);
  if (data.llm) {
    const model = data.llm.local_model || data.llm.cloud_model || "—";
    $("#model-label").textContent = `${providerLabel(data.llm.provider)} · ${model}`;
  }
}

function renderList(el, items, map) {
  el.replaceChildren();
  el.classList.toggle("empty", items.length === 0);
  if (!items.length) { el.textContent = t("common.none"); return; }
  for (const item of items) {
    const [left, right] = map(item);
    const row = document.createElement("div");
    row.className = "row";
    const a = document.createElement("span"); a.textContent = left;
    const b = document.createElement("span"); b.textContent = right;
    row.append(a, b);
    el.appendChild(row);
  }
}

// ---------------------------------------------------------------- feed
function addFeedItem(feed, event) {
  const type = event.type || "event";
  const item = document.createElement("div");
  item.className = "feed-item " + type;
  const meta = document.createElement("div");
  meta.className = "feed-meta";
  const badge = document.createElement("span");
  badge.className = "badge";
  badge.textContent = eventLabel(type);
  const time = document.createElement("span");
  time.textContent = fmtTime(event.ts);
  meta.append(badge, time);
  if (event.provider) {
    const provider = document.createElement("span");
    provider.textContent = event.provider;
    meta.appendChild(provider);
  }
  if (event.model) {
    const model = document.createElement("span");
    model.textContent = event.model;
    meta.appendChild(model);
  }
  item.appendChild(meta);

  if (type === "assistant") {
    if (event.reasoning && $("#filter-reasoning").checked) {
      const reasoning = document.createElement("div");
      reasoning.className = "feed-text";
      reasoning.textContent = t("feed.reasoning") + "\n" + event.reasoning;
      item.appendChild(reasoning);
    }
    if (event.content) {
      const content = document.createElement("div");
      content.className = "feed-text";
      content.textContent = event.content;
      item.appendChild(content);
    }
    if (!event.content && !event.reasoning) {
      const empty = document.createElement("div");
      empty.className = "feed-text empty";
      empty.textContent = t("feed.emptyAssistant");
      item.appendChild(empty);
    }
  } else if (type === "cycle_start") {
    const goal = document.createElement("div");
    goal.className = "feed-text";
    goal.textContent = t("feed.goalCycle") + "\n" + (event.task || "");
    item.appendChild(goal);
  } else if (type === "tool_call") {
    if (!$("#filter-tools").checked) return;
    const title = document.createElement("div");
    title.className = "feed-text";
    title.textContent = t("feed.toolCallName", { name: event.name || t("feed.tool") });
    item.appendChild(title);
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = t("feed.arguments");
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(event.args || {}, null, 2);
    details.append(summary, pre);
    item.appendChild(details);
  } else if (type === "tool_result") {
    if (!$("#filter-results").checked) return;
    const title = document.createElement("div");
    title.className = "feed-text";
    title.textContent = t("feed.toolResultName", { name: event.name || t("feed.toolResult") });
    item.appendChild(title);
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = t("feed.result");
    const pre = document.createElement("pre");
    pre.textContent = String(event.result || "");
    details.append(summary, pre);
    item.appendChild(details);
  } else if (type === "error" || type === "provider_fallback") {
    const error = document.createElement("div");
    error.className = "feed-text";
    error.textContent = event.error || JSON.stringify(event);
    item.appendChild(error);
  } else if (type === "cycle_end") {
    const end = document.createElement("div");
    end.className = "feed-text";
    const markers = {
      "(model ended with reasoning only)": "feed.reasoningOnly",
      "(empty response)": "feed.emptyResponse",
      "(max turns reached)": "feed.maxTurns",
    };
    const key = markers[event.text];
    end.textContent = key ? t(key) : (event.text || "");
    item.appendChild(end);
  } else {
    const raw = document.createElement("div");
    raw.className = "feed-text";
    raw.textContent = JSON.stringify(event);
    item.appendChild(raw);
  }
  feed.appendChild(item);
}

function renderFeed(events) {
  const feed = $("#feed");
  feed.replaceChildren();
  if (!events || !events.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = t("decisions.empty");
    feed.appendChild(empty);
    return;
  }
  for (const event of events) addFeedItem(feed, event);
}

async function refreshLogs(force = false) {
  try {
    const data = await api("/api/logs?limit=400");
    const events = data.events || [];
    state.lastEvents = events;
    const key = events.length + ":" + (events[events.length - 1]?.ts || 0);
    if (!force && key === state.lastEventsKey) return;
    state.lastEventsKey = key;
    const feed = $("#feed");
    const nearBottom = feed.scrollTop + feed.clientHeight >= feed.scrollHeight - 80;
    renderFeed(events);
    if ($("#autoscroll").checked && (force || nearBottom)) feed.scrollTop = feed.scrollHeight;
  } catch (e) {
    // keep the previous feed
  }
}

// ---------------------------------------------------------------- boot
(async () => {
  applyLanguage();
  try {
    await loadConfig();
    await refreshState();
    await refreshLogs();
  } catch (e) {
    setToast(errorText(e.message), "err");
  }
  setInterval(refreshState, 2000);
  setInterval(refreshLogs, 2000);
})();
