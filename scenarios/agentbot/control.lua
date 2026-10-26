-- Standard freeplay start: crash site, starting items, charting, victory script.
require('__base__/script/freeplay/control.lua')
local freeplay_module = require('__base__/script/freeplay/freeplay')

-- Factorio's `storage` table is shared by every mod, so namespace our data.
-- Never cache this table in a file-scope local: on save load the engine
-- restores `storage` after the control.lua chunk has run, so a cached table
-- can point at the pre-load (empty) storage.
local function ns()
  local t = storage.agentbridge
  if type(t) ~= "table" then
    t = {}
    storage.agentbridge = t
  end
  if t.migrated ~= true then
    -- Only adopt the pre-namespace layout when it is clearly ours; avoid
    -- stealing generic keys from another mod's storage on a real server.
    local legacy = (storage.version == 2 and storage.queue ~= nil and storage.events ~= nil)
    if legacy then
      if t.char_id == nil then t.char_id = storage.char_id end
      if t.queue == nil then t.queue = storage.queue end
      if t.events == nil then t.events = storage.events end
      if t.event_seq == nil then t.event_seq = storage.event_seq end
      if t.next_job_id == nil then t.next_job_id = storage.next_job_id end
      if t.auto_respawn == nil then t.auto_respawn = storage.auto_respawn end
      if t.spawn_point == nil then t.spawn_point = storage.spawn_point end
    end
    t.migrated = true
  end
  return t
end

local VERSION = 2
local wire_poles_near  -- forward declaration; defined with the info helpers
local MAX_EVENTS = 240
local DEFAULT_SCAN_RADIUS = 18
local SOLID_RESOURCES = {
  ["iron-ore"] = true, ["copper-ore"] = true, ["coal"] = true,
  ["stone"] = true, ["uranium-ore"] = true,
}

local function jenc(t) return helpers.table_to_json(t) end
local function out(s) rcon.print(s) end

local function pos(p) return { x = p.x, y = p.y } end
local function d2(a, b)
  local dx, dy = a.x - b.x, a.y - b.y
  return dx * dx + dy * dy
end

-- Factorio's 8-way direction enum uses even values (0,2,...14).
local function dir_to(from, to)
  local dx, dy = to.x - from.x, to.y - from.y
  if dx == 0 and dy == 0 then return defines.direction.north end
  local angle = math.atan2(dy, dx) -- 0 = east, +pi/2 = south
  local sector = math.floor((angle + math.pi / 8) / (math.pi / 4)) % 8
  local dirs = {
    defines.direction.east,      -- 0
    defines.direction.southeast, -- 1
    defines.direction.south,     -- 2
    defines.direction.southwest, -- 3
    defines.direction.west,      -- 4
    defines.direction.northwest, -- 5
    defines.direction.north,     -- 6
    defines.direction.northeast, -- 7
  }
  return dirs[sector + 1]
end

local function inventory_items(inv)
  local items = {}
  if not inv then return items end
  for _, item in pairs(inv.get_contents()) do
    table.insert(items, { name = item.name, count = item.count, quality = item.quality })
  end
  table.sort(items, function(a, b) return a.name < b.name end)
  return items
end

local function count_item(inv, name)
  if not inv then return 0 end
  return inv.get_item_count(name)
end

-- A real LuaPlayer only exists while a real client is connected.  This is the
-- body of the bot; the scenario controls it from the server.  A bare character
-- is kept only as an explicitly enabled lab fallback.
local function bot_player()
  local name = ns().bot_name or "LLM-Bot"
  local p = game.get_player(name)
  if p and p.valid and p.connected and p.character then return p end
  return nil
end

local function char()
  local p = bot_player()
  if p then
    ns().char_id = p.character.unit_number
    return p.character
  end
  if not ns().allow_bare then return nil end
  if not ns().char_id then return nil end
  local c = game.get_entity_by_unit_number(ns().char_id)
  if c and c.valid then return c end
  ns().char_id = nil
  return nil
end

local function ensure_char()
  local p = bot_player()
  if p then
    ns().char_id = p.character.unit_number
    return p.character
  end
  if not ns().allow_bare then return nil end
  local c = char()
  if c then return c end
  local s = game.surfaces[1]
  if not s then return nil end
  local spawn = ns().spawn_point or { x = 0, y = 0 }
  local p2 = s.find_non_colliding_position("character", spawn, 64, 0.5)
  if not p2 then return nil end
  local e = s.create_entity({ name = "character", position = p2, force = game.forces.player })
  if not e then return nil end
  ns().char_id = e.unit_number
  ns().spawn_point = pos(e.position)
  log("[AGENT] spawned bare character unit=" .. tostring(e.unit_number))
  return e
end

local function emit(kind, data)
  ns().event_seq = (ns().event_seq or 0) + 1
  local ev = { seq = ns().event_seq, tick = game.tick, type = kind }
  for k, v in pairs(data or {}) do ev[k] = v end
  table.insert(ns().events, ev)
  while #ns().events > MAX_EVENTS do table.remove(ns().events, 1) end
  log("[AGENT] event " .. jenc(ev))
  return ev
end

local function inbox_add(kind, text, player_index)
  if not text or text == "" then return end
  ns().inbox_seq = (ns().inbox_seq or 0) + 1
  local ev = { seq = ns().inbox_seq, tick = game.tick, type = "instruction",
    kind = kind, text = text, player_index = player_index }
  table.insert(ns().inbox, ev)
  while #ns().inbox > 200 do table.remove(ns().inbox, 1) end
  emit("instruction", ev)
end

local function init_storage()
  ns().version = VERSION
  ns().next_job_id = ns().next_job_id or 0
  ns().queue = ns().queue or {}
  ns().events = ns().events or {}
  ns().event_seq = ns().event_seq or 0
  ns().bot_name = ns().bot_name or "LLM-Bot"
  ns().allow_bare = ns().allow_bare == true
  ns().auto_respawn = ns().auto_respawn ~= false
  ns().spawn_point = ns().spawn_point or { x = 0, y = 0 }
  ns().inbox = ns().inbox or {}
  ns().inbox_seq = ns().inbox_seq or 0
  ns().auto_commands = ns().auto_commands == true
end

local function stop_motion()
  local c = char()
  if c and c.valid then
    c.walking_state = { walking = false }
    if c.mining_state and c.mining_state.mining then
      c.mining_state = { mining = false }
    end
  end
end

local function finish_job(ok, detail, extra)
  local job = ns().job
  if not job then return end
  stop_motion()
  job.status = ok and "done" or "failed"
  job.detail = detail or ""
  job.finished_tick = game.tick
  local payload = { id = job.id, kind = job.kind, ok = ok, detail = job.detail }
  if extra then for k, v in pairs(extra) do payload[k] = v end end
  emit(ok and "job_done" or "job_failed", payload)
  ns().job = nil
  ns().path_handle = nil
  -- start the next queued job on the next tick to keep the engine stable
  ns().start_next_tick = game.tick + 1
end

local function job_fail(detail)
  finish_job(false, detail)
end

local function set_phase(job, phase, detail)
  job.phase = phase
  job.phase_tick = game.tick
  if detail then job.detail = detail end
  emit("phase", { id = job.id, kind = job.kind, phase = phase, detail = job.detail })
end

local function item_for_resource(name)
  -- resource tiles yield their own item; trees/rocks are handled by callers
  return name
end

local function find_nearest_entity(c, name, radius, etype)
  local filter = { position = c.position, radius = radius, type = etype }
  if name and name ~= "" then filter.name = name end
  local ents = c.surface.find_entities_filtered(filter)
  local best, bestd
  for _, e in pairs(ents) do
    if e.valid then
      local d = d2(c.position, e.position)
      if not bestd or d < bestd then best, bestd = e, d end
    end
  end
  return best
end

local function find_nearest_resource(c, name, radius)
  return find_nearest_entity(c, name, radius, "resource")
end

local function request_path(job, goal)
  local c = char()
  if not c then return job_fail("no character") end
  local start = c.surface.find_non_colliding_position("character", c.position, 6, 0.5) or c.position
  local handle = c.surface.request_path({
    bounding_box = { { -0.4, -0.4 }, { 0.4, 0.4 } },
    collision_mask = {
      layers = { player = true, train = true, water_tile = true, object = true },
      consider_tile_transitions = true,
    },
    start = start,
    goal = goal,
    force = c.force,
    entity_to_ignore = c,
    radius = 1,
    pathfind_flags = { cache = false, no_break = true, prefer_straight_paths = false, allow_paths_through_own_entities = false },
  })
  if not handle or handle == 0 then return job_fail("path request rejected") end
  job.path_handle = handle
  job.path = nil
  job.path_index = 1
  job.path_started = game.tick
  job.last_check = game.tick
  job.last_pos = pos(c.position)
  job.stuck = 0
  set_phase(job, "pathing", "requested path to " .. tostring(goal.x) .. "," .. tostring(goal.y))
  return true
end

local function follow_path(job, arrival_distance, arrival_phase)
  local c = char()
  if not c then return job_fail("character disappeared") end
  local target_d = arrival_distance or 0.8
  local goal = job.data and job.data.goal
  if goal and d2(c.position, goal) <= target_d * target_d then
    c.walking_state = { walking = false }
    if arrival_phase then
      set_phase(job, arrival_phase, "arrived")
    else
      finish_job(true, "arrived")
    end
    return
  end
  local path = job.path
  if not path then return end
  if #path == 0 or job.path_index > #path then
    c.walking_state = { walking = false }
    if arrival_phase then
      set_phase(job, arrival_phase, "path complete")
    else
      finish_job(true, "path complete")
    end
    return
  end
  local wp = path[job.path_index]
  if not wp then
    finish_job(true, "path complete")
    return
  end
  if d2(c.position, wp.position) < 0.36 then
    job.path_index = job.path_index + 1
    return
  end
  c.walking_state = { walking = true, direction = dir_to(c.position, wp.position) }
  -- stuck detection (only while actually walking)
  if game.tick - (job.last_check or 0) >= 90 then
    local moved = d2(c.position, job.last_pos or c.position)
    if moved < 0.09 then
      job.stuck = (job.stuck or 0) + 1
    else
      job.stuck = 0
    end
    job.last_check = game.tick
    job.last_pos = pos(c.position)
    if job.stuck >= 3 then
      job_fail("stuck for " .. tostring(job.stuck * 90) .. " ticks")
    end
  end
end

local function start_mining(job, target)
  local c = char()
  if not c then return job_fail("no character") end
  c.walking_state = { walking = false }
  c.update_selected_entity(target.position)
  c.mining_state = { mining = true, position = target.position }
  job.data.target = target.position
  job.data.target_name = target.name
  set_phase(job, "mining", "target " .. target.name .. " at " .. tostring(target.position.x) .. "," .. tostring(target.position.y))
end

local function run_walk(job)
  local c = char()
  if not c then return job_fail("no character") end
  if job.phase == "init" then
    job.data.goal = { x = job.params.x, y = job.params.y }
    if type(job.data.goal.x) ~= "number" or type(job.data.goal.y) ~= "number" then
      return job_fail("walk needs numeric x,y")
    end
    if d2(c.position, job.data.goal) <= 0.64 then
      return finish_job(true, "already there")
    end
    job.deadline = game.tick + (job.params.timeout_ticks or 60 * 60 * 3)
    return request_path(job, job.data.goal)
  elseif job.phase == "pathing" then
    if game.tick > (job.deadline or 0) then return job_fail("path timeout") end
  elseif job.phase == "following" then
    if game.tick > (job.deadline or 0) then return job_fail("walk timeout") end
    return follow_path(job, 1.2, nil)
  elseif job.phase == "walking_direct" then
    if game.tick > (job.deadline or 0) then return job_fail("direct walk timeout") end
    if d2(c.position, job.data.goal) <= 2.25 then
      return finish_job(true, "walked direct", { position = pos(c.position) })
    end
    local dir = dir_to(c.position, job.data.goal)
    if job.data.stuck_until and game.tick < job.data.stuck_until and job.data.detour_dir then
      dir = job.data.detour_dir
    end
    if not job.data.check_tick or game.tick >= job.data.check_tick then
      if job.last_pos and d2(c.position, job.last_pos) < 0.09 then
        job.data.detour_dir = ((dir + 2) % 16)
        job.data.stuck_until = game.tick + 45
        job.data.stuck = (job.data.stuck or 0) + 1
      else
        job.data.detour_dir = nil
        job.data.stuck = 0
      end
      job.last_pos = pos(c.position)
      job.data.check_tick = game.tick + 30
      if (job.data.stuck or 0) > 12 then return job_fail("direct walk stuck") end
    end
    c.walking_state = { walking = true, direction = dir }
  end
end

local function run_mine(job)
  local c = char()
  if not c then return job_fail("no character") end
  local inv = c.get_inventory(defines.inventory.character_main)
  local is_tree = (job.params.name == "tree" or job.params.name == "wood")
  local item = job.data.item or (is_tree and "wood" or item_for_resource(job.params.name))
  if job.phase == "init" then
    if not is_tree and not SOLID_RESOURCES[job.params.name] then
      return job_fail("unsupported resource '" .. tostring(job.params.name) .. "' (solid resources or tree)")
    end
    job.data.count = math.max(1, math.floor(job.params.count or 1))
    job.data.radius = job.params.radius or 64
    job.data.start_count = count_item(inv, item)
    job.data.target_type = is_tree and "tree" or "resource"
    job.deadline = game.tick + (job.params.timeout_ticks or 60 * 60 * 8)
    local target = is_tree
      and find_nearest_entity(c, nil, job.data.radius, "tree")
      or find_nearest_resource(c, job.params.name, job.data.radius)
    if not target then return job_fail("no " .. tostring(job.params.name) .. " within " .. job.data.radius .. " tiles") end
    job.data.target = target.position
    job.data.target_name = target.name
    set_phase(job, "approach", "found " .. job.params.name)
    local approach = c.surface.find_non_colliding_position("character", target.position, 3, 0.25)
    if not approach then return job_fail("no approach position") end
    job.data.goal = approach
    return request_path(job, approach)
  elseif job.phase == "pathing" then
    if game.tick > (job.deadline or 0) then return job_fail("path timeout") end
  elseif job.phase == "following" then
    if game.tick > (job.deadline or 0) then return job_fail("approach timeout") end
    return follow_path(job, 2.2, "mining")
  elseif job.phase == "mining" then
    if game.tick > (job.deadline or 0) then
      return job_fail("mining timeout, got " .. tostring(count_item(inv, item) - job.data.start_count))
    end
    local gained = count_item(inv, item) - job.data.start_count
    if gained >= job.data.count then
      return finish_job(true, "mined " .. tostring(gained), { item = item, count = gained })
    end
    local target = job.data.target
    local still = target and c.surface.find_entities_filtered({ position = target, radius = 0.6, name = job.data.target_name, type = job.data.target_type or "resource" })
    if not still or #still == 0 then
      -- depleted: look for the next tile
      local next_target = is_tree
        and find_nearest_entity(c, nil, job.data.radius, "tree")
        or find_nearest_resource(c, job.params.name, job.data.radius)
      if not next_target then
        if gained > 0 then return finish_job(true, "resource depleted, mined " .. tostring(gained), { item = item, count = gained }) end
        return job_fail("resource depleted")
      end
      job.data.target = next_target.position
      job.data.target_name = next_target.name
      local approach = c.surface.find_non_colliding_position("character", next_target.position, 3, 0.25)
      job.data.goal = approach
      set_phase(job, "approach", "next tile")
      if approach and d2(c.position, approach) > 4 then
        return request_path(job, approach)
      end
      return start_mining(job, next_target)
    end
    if job.data.target and d2(c.position, job.data.target) > 4.0 then
      -- The approach waypoint can stop a little short; close the last tiles
      -- with the engine's own walking so the mining reach is respected.
      c.walking_state = { walking = true, direction = dir_to(c.position, job.data.target) }
      return
    end
    if not c.mining_state or not c.mining_state.mining then
      local e = still[1]
      if e and e.valid then start_mining(job, e) end
    end
  end
end

local function recipe_ingredients(recipe)
  local out = {}
  for _, ing in pairs(recipe.ingredients) do
    if ing.type == "fluid" then return nil, "fluid ingredients cannot be hand-crafted" end
    table.insert(out, { name = ing.name, amount = ing.amount })
  end
  return out
end

local function run_craft(job)
  local c = char()
  if not c then return job_fail("no character") end
  local force = c.force
  local inv = c.get_inventory(defines.inventory.character_main)
  if job.phase == "init" then
    local recipe = force.recipes[job.params.recipe]
    if not recipe then return job_fail("no such recipe: " .. tostring(job.params.recipe)) end
    if not recipe.enabled then return job_fail("recipe locked: " .. job.params.recipe) end
    job.data.count = math.max(1, math.floor(job.params.count or 1))
    local ingredients, err = recipe_ingredients(recipe)
    if not ingredients then return job_fail(err) end
    for _, ing in pairs(ingredients) do
      if count_item(inv, ing.name) < ing.amount * job.data.count then
        return job_fail("missing " .. ing.name .. " (" .. tostring(count_item(inv, ing.name)) .. "/" .. tostring(ing.amount * job.data.count) .. ")")
      end
    end
    local product = recipe.products and recipe.products[1]
    job.data.item = product and product.name or job.params.recipe
    job.data.start_count = count_item(inv, job.data.item)
    job.deadline = game.tick + (job.params.timeout_ticks or 60 * 60 * 10)
    local p = bot_player()
    local ok, err2 = pcall(function()
      if p then
        p.begin_crafting({ recipe = job.params.recipe, count = job.data.count })
      else
        c.begin_crafting({ recipe = job.params.recipe, count = job.data.count })
      end
    end)
    if not ok then return job_fail("begin_crafting failed: " .. tostring(err2)) end
    set_phase(job, "crafting", "queued " .. job.params.recipe .. " x" .. tostring(job.data.count))
    return
  elseif job.phase == "crafting" then
    if game.tick > (job.deadline or 0) then return job_fail("craft timeout") end
    local produced = count_item(inv, job.data.item) - job.data.start_count
    local queue = c.crafting_queue or {}
    local still_queued = false
    for _, q in pairs(queue) do if q.recipe == job.params.recipe then still_queued = true end end
    if produced >= job.data.count and not still_queued then
      return finish_job(true, "crafted " .. tostring(produced), { item = job.data.item, count = produced })
    end
    if #queue == 0 and produced < job.data.count then
      if produced > 0 then return finish_job(true, "partial craft " .. tostring(produced), { item = job.data.item, count = produced }) end
      return job_fail("crafting stopped with no output (missing ingredients?)")
    end
  end
end

local function run_place(job)
  local c = char()
  if not c then return job_fail("no character") end
  if job.phase ~= "init" then return end
  local inv = c.get_inventory(defines.inventory.character_main)
  local name = job.params.name
  local proto = prototypes.entity[name]
  if not proto then return job_fail("no such entity prototype: " .. tostring(name)) end
  local item = name
  if proto.items_to_place_this and proto.items_to_place_this[1] then
    item = proto.items_to_place_this[1].name
  end
  if count_item(inv, item) < 1 then return job_fail("missing item " .. item) end
  local p
  if type(job.params.x) == "number" and type(job.params.y) == "number" then
    p = { x = job.params.x, y = job.params.y }
  else
    p = c.surface.find_non_colliding_position(name, c.position, job.params.radius or 8, 0.25, true)
    if not p then return job_fail("no placeable position near character") end
  end
  local direction = job.params.direction or defines.direction.north
  local function can_place_at(q)
    return c.surface.can_place_entity({ name = name, position = q, direction = direction, force = c.force })
  end
  if not can_place_at(p) then
    -- If the caller supplied a blocked position, look for a nearby free spot
    -- instead of failing outright.  The actual position is returned in the job
    -- result so the agent can learn where the building went.
    local alt = c.surface.find_non_colliding_position(name, p, job.params.radius or 5, 0.25, true)
    if alt and can_place_at(alt) then
      p = alt
    else
      return job_fail("cannot place " .. name .. " at " .. tostring(p.x) .. "," .. tostring(p.y) .. " (collision)")
    end
  end
  local player = bot_player()
  if player then
    -- Use the real player build path: smart pipette + normal build validation.
    local okp = player.pipette(item, job.params.quality)
    if not okp then
      -- pipette can fail for some items; fall back to a normal cursor stack
      -- taken from the player's inventory.
      local pinv = player.get_main_inventory()
      if not pinv or pinv.get_item_count(item) < 1 then
        return job_fail("no " .. item .. " in the player's inventory")
      end
      pinv.remove({ name = item, count = 1 })
      player.cursor_stack.set_stack({ name = item, count = 1 })
    end
    if not player.can_build_from_cursor({ position = p, direction = direction }) then
      player.clear_cursor()
      return job_fail("player cannot build " .. name .. " at " .. tostring(p.x) .. "," .. tostring(p.y))
    end
    player.build_from_cursor({ position = p, direction = direction })
    player.clear_cursor()
    finish_job(true, "player built " .. name, { position = p, item = item, mode = "real_player" })
    return
  end
  local args = { name = name, position = p, direction = direction, force = c.force, raise_built = true }
  if job.params.recipe then args.recipe = job.params.recipe end
  local ent = c.surface.create_entity(args)
  if not ent then return job_fail("create_entity failed") end
  inv.remove({ name = item, count = 1 })
  finish_job(true, "placed " .. name, { unit_number = ent.unit_number, position = p, item = item, mode = "script" })
end

local function find_target_entity(c, job)
  if job.params.target then
    local e = game.get_entity_by_unit_number(job.params.target)
    if e and e.valid then return e end
    -- Most buildings are not exposed by get_entity_by_unit_number (that API
    -- only covers prototypes with the get-by-unit-number flag), so match the
    -- unit number from a local scan instead.
    local ents = c.surface.find_entities_filtered({ position = c.position, radius = job.params.radius or 256 })
    for _, e2 in pairs(ents) do
      if e2.valid and e2.unit_number == job.params.target then return e2 end
    end
    return nil
  end
  if not job.params.entity_name then return nil end
  local ents = c.surface.find_entities_filtered({
    position = c.position, radius = job.params.radius or 12,
    name = job.params.entity_name, force = c.force,
  })
  local best
  for _, e in pairs(ents) do
    if e.valid and e.type ~= "character" then
      if not best or d2(c.position, e.position) < d2(c.position, best.position) then best = e end
    end
  end
  return best
end

local function run_rotate(job)
  local p = bot_player(); if not p then return job_fail("no real player connected") end
  local c = p.character; if not c then return job_fail("no character") end
  if job.phase ~= "init" then return end
  local ent = find_target_entity(c, job)
  if not ent then return job_fail("no target entity within 256 tiles; walk closer (within 10 tiles)") end
  if not ent.valid then return job_fail("target is invalid") end
  if d2(c.position, ent.position) > 100 then
    return job_fail("target too far; walk closer (within 10 tiles)")
  end
  local before = ent.direction
  local ok = ent.rotate({ by_player = p, reverse = job.params.reverse == true })
  if not ok then return job_fail("cannot rotate " .. tostring(ent.name)) end
  finish_job(true, "rotated " .. tostring(ent.name), {
    unit_number = ent.unit_number, name = ent.name,
    direction_before = before, direction_after = ent.direction,
  })
end

local function run_dismantle(job)
  local p = bot_player(); if not p then return job_fail("no real player connected") end
  local c = p.character; if not c then return job_fail("no character") end
  if job.phase ~= "init" then return end
  local ent = find_target_entity(c, job)
  if not ent then return job_fail("no target entity within 256 tiles; walk closer (within 10 tiles)") end
  if not ent.valid then return job_fail("target is invalid") end
  if not ent.minable then return job_fail("entity is not minable") end
  if d2(c.position, ent.position) > 100 then
    return job_fail("target too far; walk closer (within 10 tiles)")
  end
  local name, posv, unit = ent.name, pos(ent.position), ent.unit_number
  local ok = p.mine_entity(ent, false)
  if not ok then return job_fail("could not dismantle " .. tostring(name) .. " (reach or inventory full)") end
  if ent.valid then return job_fail("entity still valid after mine: " .. tostring(name)) end
  finish_job(true, "dismantled " .. tostring(name), {
    unit_number = unit, name = name, position = posv,
  })
end

local function run_insert(job)
  local c = char(); if not c then return job_fail("no character") end
  if job.phase ~= "init" then return end
  local inv = c.get_inventory(defines.inventory.character_main)
  local item = job.params.item
  local count = math.max(1, math.floor(job.params.count or 1))
  if count_item(inv, item) < count then return job_fail("missing " .. tostring(item)) end
  local ent = find_target_entity(c, job)
  if not ent then return job_fail("no target entity") end
  local inserted = ent.insert({ name = item, count = count })
  if inserted <= 0 then return job_fail("target refused " .. item) end
  inv.remove({ name = item, count = inserted })
  finish_job(true, "inserted " .. tostring(inserted), { unit_number = ent.unit_number, item = item, count = inserted })
end

local function run_take(job)
  local c = char(); if not c then return job_fail("no character") end
  if job.phase ~= "init" then return end
  local ent = find_target_entity(c, job)
  if not ent then return job_fail("no target entity") end
  local item = job.params.item
  local want = math.max(1, math.floor(job.params.count or 1))
  local moved = 0
  local max_index = (ent.get_max_inventory_index and ent.get_max_inventory_index()) or 1
  for i = 1, max_index do
    if moved >= want then break end
    local e_inv = ent.get_inventory(i)
    if e_inv then
      local avail = e_inv.get_item_count(item)
      if avail > 0 then
        local take = math.min(avail, want - moved)
        local removed = e_inv.remove({ name = item, count = take })
        if removed > 0 then
          local ins = c.insert({ name = item, count = removed })
          if ins < removed then e_inv.insert({ name = item, count = removed - ins }) end
          moved = moved + ins
        end
      end
    end
  end
  if moved <= 0 then return job_fail("nothing taken") end
  finish_job(true, "took " .. tostring(moved), { unit_number = ent.unit_number, item = item, count = moved })
end

local function run_research(job)
  local c = char(); if not c then return job_fail("no character") end
  if job.phase ~= "init" then return end
  local tech_name = job.params.tech or job.params.technology
  local tech = c.force.technologies[tech_name]
  if not tech then return job_fail("no such technology: " .. tostring(tech_name)) end
  if tech.researched then return finish_job(true, "already researched") end
  if not tech.enabled then return job_fail("technology locked") end
  local oktrg, trg = pcall(function() return tech.prototype.research_trigger end)
  if oktrg and trg then
    return job_fail("technology is unlocked by a trigger, not by research; trigger=" ..
      tostring(trg.type) .. " " .. tostring(trg.item or trg.technology or ""))
  end
  local unmet = {}
  for _, p in pairs(tech.prerequisites or {}) do
    if not p.researched then table.insert(unmet, p.name) end
  end
  if #unmet > 0 then
    return job_fail("missing prerequisites: " .. table.concat(unmet, ", "))
  end
  local added = c.force.add_research(tech)
  if not added then return job_fail("could not queue research") end
  finish_job(true, "research queued", { tech = job.params.tech })
end

local function run_wait(job)
  if job.phase ~= "init" then return end
  job.data.remaining = math.max(0, math.floor(job.params.ticks or 60))
  set_phase(job, "waiting", "ticks=" .. tostring(job.data.remaining))
end

local function run_say(job)
  if job.phase ~= "init" then return end
  local msg = tostring(job.params.message or "")
  game.print("[AGENT] " .. msg)
  finish_job(true, "said")
end

-- Blueprint helpers ---------------------------------------------------------
-- A blueprint item (LuaItemStack) and a blueprint-library record (LuaRecord)
-- expose the same blueprint API.  `build_blueprint` only creates construction
-- ghosts; `revive` turns them into real entities.  mode=ghost keeps the plan,
-- mode=cost consumes the player's items, mode=force builds without materials.

local function cursor_blueprint(p)
  p.clear_cursor()
  local st = p.cursor_stack
  if not st then return nil end
  local ok = st.set_stack({ name = "blueprint", count = 1 })
  if not ok then return nil end
  return st
end

local function blueprint_counts(st)
  local count, tiles = nil, 0
  pcall(function() count = st.get_blueprint_entity_count() end)
  pcall(function() tiles = #(st.get_blueprint_tiles() or {}) end)
  return count, tiles
end

local function blueprint_requirements(st)
  local need = {}
  local function add_item(name, count)
    if name then need[name] = (need[name] or 0) + (count or 1) end
  end
  local ok, ents = pcall(function() return st.get_blueprint_entities() end)
  for _, e in pairs(ok and ents or {}) do
    local proto = prototypes.entity[e.name]
    local its = proto and proto.items_to_place_this
    if its and its[1] then add_item(its[1].name, its[1].count) end
  end
  local ok2, tiles = pcall(function() return st.get_blueprint_tiles() end)
  for _, t in pairs(ok2 and tiles or {}) do
    local proto = prototypes.tile and prototypes.tile[t.name]
    local its = proto and proto.items_to_place_this
    if its and its[1] then add_item(its[1].name, its[1].count) end
  end
  local list = {}
  for name, count in pairs(need) do table.insert(list, { name = name, count = count }) end
  table.sort(list, function(a, b) return a.name < b.name end)
  return need, list
end

local function check_requirements(inv, need)
  local missing = {}
  for name, count in pairs(need) do
    local have = inv and inv.get_item_count(name) or 0
    if have < count then table.insert(missing, { name = name, need = count, have = have }) end
  end
  table.sort(missing, function(a, b) return a.name < b.name end)
  return #missing == 0, missing
end

local function ghost_item(g)
  local name = g.ghost_name or g.name
  local proto = prototypes.entity[name] or (prototypes.tile and prototypes.tile[name])
  local its = proto and proto.items_to_place_this
  local first = its and its[1]
  if not first then return nil end
  return first.name, first.count or 1
end

local function revive_ghosts(p, ghosts, charge)
  local inv = p.get_main_inventory()
  local revived, failed, spent = 0, {}, {}
  for _, g in pairs(ghosts) do
    if g.valid then
      local item, count = ghost_item(g)
      local can_try = true
      if charge and item then
        if not inv or inv.get_item_count(item) < count then
          table.insert(failed, { name = g.ghost_name or g.name, reason = "missing " .. item })
          can_try = false
        else
          inv.remove({ name = item, count = count })
          spent[item] = (spent[item] or 0) + count
        end
      end
      if can_try then
        local ok = pcall(function() return g.revive({ raise_revive = true }) end)
        if ok and not g.valid then
          revived = revived + 1
        else
          table.insert(failed, { name = g.ghost_name or g.name, reason = "blocked" })
          if charge and item and inv then inv.insert({ name = item, count = count }) end
        end
      end
    end
  end
  return revived, failed, spent
end

local function build_from_blueprint(p, st, posv, direction, mode)
  mode = mode or "cost"
  if mode == "normal" then mode = "ghost" end
  if mode ~= "ghost" and mode ~= "cost" and mode ~= "force" then
    return nil, "unknown blueprint mode: " .. tostring(mode)
  end
  local count, tile_count = blueprint_counts(st)
  local need, req_list
  if mode == "cost" then
    need, req_list = blueprint_requirements(st)
    local enough, missing = check_requirements(p.get_main_inventory(), need)
    if not enough then
      return nil, "not enough items for blueprint", { missing = missing, requirements = req_list }
    end
  end
  local ghosts = {}
  local ok, err = pcall(function()
    -- force/cost clear trees and rocks; ghost mode leaves a plain plan.
    local res = st.build_blueprint({
      surface = p.surface, position = posv, force = p.force, direction = direction,
      build_mode = (mode == "ghost") and defines.build_mode.normal or defines.build_mode.forced,
      by_player = p, skip_fog_of_war = false,
    })
    for _, g in pairs(type(res) == "table" and res or {}) do
      if g.valid then table.insert(ghosts, g) end
    end
  end)
  if not ok then return nil, "build_blueprint failed: " .. tostring(err) end
  if #ghosts == 0 then
    return nil, "nothing could be placed at this position (blocked terrain, existing entity, or fog of war)", {
      position = posv, mode = mode, entity_count = count, tile_count = tile_count,
    }
  end
  -- build_blueprint returns entity AND tile ghosts; use that list directly.
  local result = {
    position = posv, mode = mode,
    entity_count = count, tile_count = tile_count,
    ghosts = #ghosts, revived = 0,
  }
  if mode ~= "ghost" then
    local revived, failed, spent = revive_ghosts(p, ghosts, mode == "cost")
    local left = 0
    for _, g in pairs(ghosts) do if g.valid then left = left + 1 end end
    result.revived = revived
    result.remaining_ghosts = left
    if #failed > 0 then result.failed = failed end
    if next(spent) ~= nil then result.items_used = spent end
    if mode == "cost" then result.requirements = req_list end
    -- Revived ghosts do not always auto-connect their copper wires.  Repair
    -- the local pole network so blueprint-built power plants actually work.
    if wire_poles_near then
      local wired = wire_poles_near(p.surface, p.force, posv, 256)
      result.wiring = wired
    end
  end
  return result
end

local function run_blueprint(job)
  local p = bot_player(); if not p then return job_fail("no real player connected") end
  if job.phase ~= "init" then return end
  local idx = job.params.index or 1
  local rec = p.blueprints[idx]
  if not rec then return job_fail("no blueprint record at index " .. tostring(idx)) end
  local posv = job.params.position
  if type(posv) ~= "table" or type(posv.x) ~= "number" then
    return job_fail("blueprint needs position {x,y}")
  end
  local mode = job.params.mode or (job.params.forced and "force" or "ghost")
  local res, err, extra = build_from_blueprint(p, rec, posv, job.params.direction, mode)
  if not res then return finish_job(false, err, extra) end
  res.index = idx
  finish_job(true, "blueprint " .. tostring(mode) .. ": revived " .. tostring(res.revived) ..
    "/" .. tostring(res.ghosts), res)
end

local function find_platform(p, name)
  if not p then return nil end
  for _, pf in pairs(p.force.platforms) do
    if pf.name == name then return pf end
  end
  return nil
end

local function schedule_view(pf)
  local ok, sch = pcall(function() return pf.get_schedule() end)
  if not ok or not sch then return {} end
  local ok2, recs = pcall(function() return sch.get_records() end)
  local out = {}
  if ok2 and recs then
    for i, r in pairs(recs) do
      table.insert(out, { index = i, station = r.station, temporary = r.temporary, wait_conditions = #(r.wait_conditions or {}) })
    end
  end
  return out
end

local function hub_view(pf)
  if not pf or not pf.hub or not pf.hub.valid then return nil end
  return { unit_number = pf.hub.unit_number, name = pf.hub.name,
           position = pos(pf.hub.position), surface = pf.hub.surface.name }
end

local function on_planet(p)
  local s = p.physical_surface
  if s and not s.platform and s.planet then return true, s end
  return false, s
end

-- If the engine refuses to land (platform not at a station), move the real
-- character to the planet below and restore the character controller.  The
-- body and inventory stay intact; the result reports method="teleport".
local function teleport_to_planet(p)
  local surf = p.physical_surface
  local pf = surf and surf.platform
  local loc = pf and pf.space_location
  local planet = loc and loc.name or "nauvis"
  local s = game.surfaces[planet]
  if not s and game.planets[planet] then
    s = game.planets[planet].create_surface() or game.surfaces[planet]
  end
  if not s then return false, "no planet surface " .. tostring(planet) end
  local ch = p.character
  if not ch then return false, "no character" end
  local origin = p.force.get_spawn_position(s)
  local target = s.find_non_colliding_position("character", origin, 512, 0.5)
  if not target then return false, "no landing position on " .. s.name end
  local moved = ch.teleport(target, s)
  if not moved then return false, "character teleport failed" end
  p.set_controller({ type = defines.controllers.character, character = ch })
  return true, "teleport"
end

local function finish_landing(p, method)
  local s = p.physical_surface
  finish_job(true, "landed on planet", {
    method = method,
    surface = s and s.name or nil,
    position = p.physical_position and pos(p.physical_position) or nil,
  })
end

-- The engine landing is asynchronous: it returns true, then the character
-- arrives on the planet a few seconds later.  Poll in the "landing" phase.
local function run_land(p, job)
  if job.phase == "init" then
    local ok = p.land_on_planet()
    local arrived, s = on_planet(p)
    if arrived then return finish_landing(p, "engine") end
    if ok then
      job.data.land_deadline = game.tick + 60 * 60
      return set_phase(job, "landing", "descending to " .. tostring(s and s.name))
    end
    local moved, method = teleport_to_planet(p)
    if not moved then return job_fail("could not land: " .. tostring(method)) end
    return finish_landing(p, method)
  elseif job.phase == "landing" then
    local arrived = on_planet(p)
    if arrived then return finish_landing(p, "engine") end
    if game.tick >= (job.data.land_deadline or 0) then
      local moved, method = teleport_to_planet(p)
      if not moved then return job_fail("landing timed out: " .. tostring(method)) end
      return finish_landing(p, method)
    end
  end
end

local function run_space(job)
  local p = bot_player(); if not p then return job_fail("no real player connected") end
  local action = job.params.action
  if action == "land" then return run_land(p, job) end
  if job.phase ~= "init" then return end
  if action == "enter" then
    local target = nil
    for _, pf in pairs(p.force.platforms) do
      if pf.name == job.params.platform then target = pf end
    end
    if not target then return job_fail("no such platform: " .. tostring(job.params.platform)) end
    if not target.hub then return job_fail("platform has no hub; apply_starter_pack first") end
    local ok = p.enter_space_platform(target)
    if not ok then return job_fail("could not enter platform") end
    finish_job(true, "entered platform", { platform = target.name, surface = p.physical_surface and p.physical_surface.name })
  elseif action == "leave" then
    p.leave_space_platform()
    finish_job(true, "left platform", {
      surface = p.physical_surface and p.physical_surface.name,
      controller = p.controller_type,
    })
  elseif action == "create" then
    if not job.params.planet then return job_fail("create needs planet") end
    if not job.params.starter_pack then return job_fail("create needs starter_pack item") end
    local pf, err = p.force.create_space_platform({
      name = job.params.name,
      planet = job.params.planet,
      starter_pack = { name = job.params.starter_pack, quality = job.params.quality or "normal" },
    })
    if not pf then return job_fail("create_space_platform failed: " .. tostring(err)) end
    local applied = false
    if job.params.apply ~= false then
      local ok, hub = pcall(function() return pf.apply_starter_pack(true) end)
      applied = ok and hub ~= nil
    end
    finish_job(true, "space platform created", {
      name = pf.name, space_location = pf.space_location and pf.space_location.name,
      starter_pack_applied = applied, hub = hub_view(pf),
    })
  elseif action == "apply_starter_pack" then
    local pf = find_platform(p, job.params.platform)
    if not pf then return job_fail("no such platform") end
    if pf.hub then
      finish_job(true, "starter pack already applied", { platform = pf.name, hub = hub_view(pf) })
    else
      local ok, hub = pcall(function() return pf.apply_starter_pack(true) end)
      if not ok or not hub then return job_fail("apply_starter_pack failed: " .. tostring(hub)) end
      finish_job(true, "starter pack applied", { platform = pf.name, hub = hub_view(pf) })
    end
  elseif action == "pause" or action == "resume" then
    local pf = find_platform(p, job.params.platform)
    if not pf then return job_fail("no such platform") end
    pf.paused = (action == "pause")
    finish_job(true, "platform " .. action, { platform = pf.name })
  elseif action == "schedule" then
    local pf = find_platform(p, job.params.platform)
    if not pf then return job_fail("no such platform") end
    finish_job(true, "platform schedule", { platform = pf.name, schedule = schedule_view(pf) })
  elseif action == "go" then
    local pf = find_platform(p, job.params.platform)
    if not pf then return job_fail("no such platform") end
    local dest = job.params.station or job.params.planet
    if not dest then return job_fail("go needs station/planet") end
    local sch = pf.get_schedule()
    local idx = sch.add_record({ station = dest, temporary = true })
    if not idx then return job_fail("could not add destination") end
    sch.go_to_station(idx)
    finish_job(true, "platform going to " .. dest, { platform = pf.name, destination = dest, index = idx })
  elseif action == "add_stop" then
    local pf = find_platform(p, job.params.platform)
    if not pf then return job_fail("no such platform") end
    local dest = job.params.station or job.params.planet
    if not dest then return job_fail("add_stop needs station/planet") end
    local sch = pf.get_schedule()
    local rec = { station = dest, temporary = job.params.temporary == true }
    if job.params.wait_conditions then rec.wait_conditions = job.params.wait_conditions end
    local ok, idx = pcall(function() return sch.add_record(rec) end)
    if not ok then return job_fail("add_stop failed: " .. tostring(idx)) end
    finish_job(true, "stop added", { platform = pf.name, destination = dest, index = idx })
  elseif action == "clear_schedule" then
    local pf = find_platform(p, job.params.platform)
    if not pf then return job_fail("no such platform") end
    pf.get_schedule():clear_records()
    finish_job(true, "schedule cleared", { platform = pf.name })
  elseif action == "hub" then
    local pf = find_platform(p, job.params.platform)
    if not pf then return job_fail("no such platform") end
    finish_job(true, "platform hub", {
      platform = pf.name,
      hub = hub_view(pf),
      schedule = schedule_view(pf),
    })
  else
    return job_fail("unknown space action: " .. tostring(action))
  end
end

local function run_job(job)
  if job.kind == "walk" then return run_walk(job)
  elseif job.kind == "mine" then return run_mine(job)
  elseif job.kind == "craft" then return run_craft(job)
  elseif job.kind == "place" then return run_place(job)
  elseif job.kind == "insert" then return run_insert(job)
  elseif job.kind == "rotate" then return run_rotate(job)
  elseif job.kind == "dismantle" then return run_dismantle(job)
  elseif job.kind == "take" then return run_take(job)
  elseif job.kind == "research" then return run_research(job)
  elseif job.kind == "wait" then return run_wait(job)
  elseif job.kind == "say" then return run_say(job)
  elseif job.kind == "build_blueprint" then return run_blueprint(job)
  elseif job.kind == "space" then return run_space(job)
  else return job_fail("unknown action: " .. tostring(job.kind)) end
end

local function start_next_job()
  if ns().job then return end
  local job = table.remove(ns().queue, 1)
  if not job then return end
  ns().job = job
  job.status = "running"
  job.started_tick = game.tick
  job.phase = "init"
  job.data = {}
  job.detail = ""
  emit("job_started", { id = job.id, kind = job.kind })
end

local function is_water_tile(surface, x, y)
  local ok, t = pcall(function() return surface.get_tile(x, y) end)
  return ok and t and (t.name == "water" or t.name == "deepwater")
end

local function find_water_opts(radius)
  local p = bot_player(); if not p then return nil, "no real player connected" end
  local c = p.character; if not c then return nil, "no character" end
  local r = math.max(8, math.min(512, tonumber(radius) or 120))
  local area = { left_top = { x = c.position.x - r, y = c.position.y - r },
                 right_bottom = { x = c.position.x + r, y = c.position.y + r } }
  local tiles = c.surface.find_tiles_filtered({ area = area, name = "water" })
  if not tiles or #tiles == 0 then
    tiles = c.surface.find_tiles_filtered({ area = area, name = "deepwater" })
  end
  if not tiles or #tiles == 0 then return nil, "no water within " .. r .. " tiles" end
  -- Find the nearest shore tile to the character, then test pump placements
  -- around it.  can_place_entity alone is not enough for offshore pumps: it
  -- can accept a land-locked centre, so also require water under the 2x2
  -- pump footprint and a free pipe-side tile.
  local best, bestd
  for _, t in pairs(tiles) do
    local cx, cy = t.position.x + 0.5, t.position.y + 0.5
    local d = (cx - c.position.x) ^ 2 + (cy - c.position.y) ^ 2
    if not bestd or d < bestd then best = t; bestd = d end
  end
  local center = { x = best.position.x + 0.5, y = best.position.y + 0.5 }
  local dirs = { defines.direction.north, defines.direction.east, defines.direction.south, defines.direction.west }
  local pump, pump_dir, water_count
  for _, dir in pairs(dirs) do
    for dx = -2, 2 do
      for dy = -2, 2 do
        local pp = { x = center.x + dx, y = center.y + dy }
        if c.surface.can_place_entity({ name = "offshore-pump", position = pp, direction = dir, force = c.force }) then
          local wc = 0
          for ox = -0.5, 0.5, 1 do
            for oy = -0.5, 0.5, 1 do
              if is_water_tile(c.surface, pp.x + ox, pp.y + oy) then wc = wc + 1 end
            end
          end
          if wc >= 2 then
            pump, pump_dir, water_count = pp, dir, wc
            break
          end
        end
      end
      if pump then break end
    end
    if pump then break end
  end
  if not pump then
    return nil, "found water but no valid 2x2 offshore-pump site (needs >=2 water tiles under the pump)"
  end
  local shore = c.surface.find_non_colliding_position("character", pump, 24, 0.25, true)
  return {
    ok = true,
    water_tile = { x = best.position.x, y = best.position.y },
    water_center = center,
    water_tiles = #tiles,
    distance = math.sqrt(bestd),
    pump_position = pump,
    pump_direction = pump_dir,
    pump_water_tiles = water_count,
    shore_position = shore,
  }
end

local function scan_resources(c, radius, limit)
  -- Group resource tiles by name, keeping the nearest tile.  A raw list of
  -- tiles would be dominated by a single ore patch and hide other resources.
  local groups = {}
  local ents = c.surface.find_entities_filtered({ position = c.position, radius = radius, type = "resource" })
  for _, e in pairs(ents) do
    if e.valid then
      local g = groups[e.name]
      if not g then
        g = { name = e.name, tiles = 0, total_amount = 0, nearest = nil }
        groups[e.name] = g
      end
      g.tiles = g.tiles + 1
      g.total_amount = g.total_amount + (e.amount or 0)
      local d = math.sqrt(d2(c.position, e.position))
      if not g.nearest or d < g.nearest.distance then
        g.nearest = { x = e.position.x, y = e.position.y, distance = d, amount = e.amount }
      end
    end
  end
  local list = {}
  for _, g in pairs(groups) do table.insert(list, g) end
  table.sort(list, function(a, b) return a.nearest.distance < b.nearest.distance end)
  while #list > limit do table.remove(list) end
  return list
end

local function scan_entities(c, radius, limit)
  local list = {}
  local ents = c.surface.find_entities_filtered({ position = c.position, radius = radius })
  for _, e in pairs(ents) do
    if e.valid and e.type ~= "character" and e.type ~= "resource" and e.type ~= "particle" then
      table.insert(list, {
        name = e.name, type = e.type, x = e.position.x, y = e.position.y,
        unit_number = e.unit_number, distance = math.sqrt(d2(c.position, e.position)),
        direction = e.direction, status = e.status, minable = e.minable,
      })
    end
  end
  table.sort(list, function(a, b) return a.distance < b.distance end)
  while #list > limit do table.remove(list) end
  return list
end

local function char_state(c)
  if not c or not c.valid then return { alive = false } end
  local inv = c.get_inventory(defines.inventory.character_main)
  local queue = {}
  for _, q in pairs(c.crafting_queue or {}) do
    table.insert(queue, { recipe = q.recipe, count = q.count })
  end
  local walking = c.walking_state
  local mining = c.mining_state
  return {
    alive = true,
    unit_number = c.unit_number,
    name = c.name,
    position = pos(c.position),
    surface = c.surface.name,
    health = c.health,
    max_health = c.max_health,
    walking = walking and { walking = walking.walking, direction = walking.direction } or nil,
    mining = mining and { mining = mining.mining, position = mining.position } or nil,
    crafting_queue = queue,
    inventory = inventory_items(inv),
  }
end

local function player_state()
  local p = bot_player()
  if not p then return { connected = false } end
  local c = p.character
  local queue = {}
  for _, q in pairs((c and c.crafting_queue) or {}) do
    table.insert(queue, { recipe = q.recipe, count = q.count })
  end
  return {
    connected = true,
    name = p.name,
    index = p.index,
    admin = p.admin,
    controller_type = p.controller_type,
    physical_surface = p.physical_surface and p.physical_surface.name or nil,
    physical_position = pos(p.physical_position),
    character_unit = c and c.unit_number or nil,
    health = c and c.health or nil,
    opened_self = p.opened_self,
    vehicle = p.vehicle and p.vehicle.name or nil,
    crafting_queue = queue,
  }
end

local function blueprint_list()
  local p = bot_player()
  local list = {}
  if not p then return list end
  for i, r in pairs(p.blueprints) do
    local ok, label = pcall(function() return r.label end)
    local ok2, ptype = pcall(function() return r.type end)
    table.insert(list, { index = i, label = ok and label or nil, type = ok2 and ptype or nil })
  end
  return list
end

local function platform_list()
  local p = bot_player()
  local list = {}
  if not p then return list, {} end
  for idx, pf in pairs(p.force.platforms) do
    table.insert(list, {
      index = idx, name = pf.name, state = pf.state,
      space_location = pf.space_location and pf.space_location.name or nil,
      distance = pf.distance, paused = pf.paused,
      hub = pf.hub and pf.hub.position or nil,
      hub_unit = pf.hub and pf.hub.unit_number or nil,
      schedule = schedule_view(pf),
    })
  end
  local planets = {}
  for name, _ in pairs(game.planets) do table.insert(planets, name) end
  table.sort(planets)
  return list, planets
end

local function state(scan_radius)
  local c = char()
  local radius = scan_radius or DEFAULT_SCAN_RADIUS
  local force = c and c.force or game.forces.player
  local job = ns().job
  local job_view
  if job then
    job_view = {
      id = job.id, kind = job.kind, status = job.status, phase = job.phase,
      detail = job.detail, started_tick = job.started_tick,
      goal = job.data and job.data.goal or nil,
      target = job.data and job.data.target or nil,
      path_len = job.path and #job.path or nil,
      path_index = job.path_index,
      stuck = job.stuck,
    }
  end
  local queue_view = {}
  for _, q in pairs(ns().queue) do
    table.insert(queue_view, { id = q.id, kind = q.kind, status = q.status })
  end
  local result = {
    agentbridge_version = VERSION,
    tick = game.tick,
    speed = game.speed,
    paused = game.tick_paused,
    character = char_state(c),
    player = player_state(),
    bot_name = ns().bot_name or "LLM-Bot",
    allow_bare = ns().allow_bare == true,
    blueprints = blueprint_list(),
    platforms = (function() local ps, _ = platform_list(); return ps end)(),
    planets = (function() local _, pl = platform_list(); return pl end)(),
    inbox_seq = ns().inbox_seq or 0,
    job = job_view,
    queue = queue_view,
    last_event_seq = ns().event_seq or 0,
    force = {
      current_research = force.current_research and force.current_research.name or nil,
      research_progress = force.research_progress,
      research_queue = (function()
        local q = {}
        for _, t in pairs(force.research_queue or {}) do table.insert(q, t.name) end
        return q
      end)(),
      evolution_factor = (function() local ok, v = pcall(function() return force.get_evolution_factor() end); return ok and v or 0 end)(),
      players = #game.players,
      connected_players = #game.connected_players,
    },
    resources = c and scan_resources(c, radius, 16) or {},
    entities = c and scan_entities(c, radius, 60) or {},
  }
  return result
end

local function create_blueprint_opts(opts)
  local p = bot_player(); if not p then return nil, "no real player connected" end
  local area = opts.area
  if not area then
    local x1, y1, x2, y2 = opts.x1, opts.y1, opts.x2, opts.y2
    if type(x1) ~= "number" or type(x2) ~= "number" then return nil, "area or x1/y1/x2/y2 required" end
    area = { left_top = { x = math.min(x1, x2), y = math.min(y1, y2) },
             right_bottom = { x = math.max(x1, x2), y = math.max(y1, y2) } }
  end
  local st = cursor_blueprint(p)
  if not st then return nil, "could not create blueprint cursor" end
  local ok, err = pcall(function()
    st.create_blueprint({
      area = area, surface = p.surface, force = p.force,
      always_include_tiles = opts.always_include_tiles == true,
      include_entities = opts.include_entities ~= false,
      include_modules = opts.include_modules ~= false,
      include_fuel = opts.include_fuel ~= false,
      include_station_names = opts.include_station_names == true,
      include_trains = opts.include_trains == true,
    })
  end)
  if not ok then p.clear_cursor(); return nil, "create_blueprint failed: " .. tostring(err) end
  local count, tiles = blueprint_counts(st)
  local encoded = st.export_stack()
  st.clear(); p.clear_cursor()
  return { blueprint = encoded, entity_count = count, tile_count = tiles, area = area }
end

local function build_blueprint_opts(opts)
  local p = bot_player(); if not p then return nil, "no real player connected" end
  local x, y = opts.x, opts.y
  if type(x) ~= "number" or type(y) ~= "number" then return nil, "x/y required" end
  local posv = { x = x, y = y }
  local direction = opts.direction or defines.direction.north
  local mode = opts.mode or "cost"
  if opts.forced == true and opts.mode == nil then mode = "force" end
  local st = cursor_blueprint(p)
  if not st then return nil, "could not create blueprint cursor" end
  if opts.string then
    local code = st.import_stack(opts.string)
    if code == 1 then st.clear(); p.clear_cursor(); return nil, "import_stack failed" end
  else
    st.clear(); p.clear_cursor(); return nil, "blueprint string required"
  end
  local res, err, extra = build_from_blueprint(p, st, posv, direction, mode)
  st.clear(); p.clear_cursor()
  if not res then return nil, err, extra end
  return res
end

-- ---------------------------------------------------------------------------
-- Detailed information and construction helpers.  These are read-only except
-- build_entities/set_recipe/wire, which consume real player items or change
-- normal entity settings.  No items are created without an inventory cost.
-- ---------------------------------------------------------------------------
local ENTITY_STATUS_NAMES = {}
for k, v in pairs(defines.entity_status) do ENTITY_STATUS_NAMES[v] = k end

local INVENTORY_NAMES = {}
for k, v in pairs(defines.inventory) do INVENTORY_NAMES[v] = k end

local function safe_pos(p)
  if type(p) ~= "table" or type(p.x) ~= "number" or type(p.y) ~= "number" then return nil end
  return { x = p.x, y = p.y }
end

local function recipe_view(recipe)
  if not recipe then return nil end
  local ing, prod = {}, {}
  for _, i in pairs(recipe.ingredients or {}) do
    ing[#ing+1] = { type = i.type, name = i.name, amount = i.amount }
  end
  for _, p in pairs(recipe.products or {}) do
    prod[#prod+1] = { type = p.type, name = p.name, amount = p.amount, probability = p.probability }
  end
  local cats = {}
  pcall(function() for _, c in pairs(recipe.categories or {}) do cats[#cats+1] = c end end)
  return { name = recipe.name, enabled = recipe.enabled, energy = recipe.energy,
           categories = cats, ingredients = ing, products = prod }
end

local function entity_inventories(ent)
  local res = {}
  local maxi = 0
  pcall(function() maxi = ent.get_max_inventory_index() or 0 end)
  for i = 1, maxi do
    local ok, inv = pcall(function() return ent.get_inventory(i) end)
    if ok and inv then
      local items = {}
      for _, it in pairs(inv.get_contents()) do
        items[#items+1] = { name = it.name, count = it.count, quality = it.quality }
      end
      if #items > 0 then
        table.sort(items, function(a, b) return a.name < b.name end)
        res[#res+1] = { index = i, name = INVENTORY_NAMES[i] or tostring(i), items = items }
      end
    end
  end
  return res
end

local function entity_fluids(ent)
  local ok, fl = pcall(function() return ent.get_fluid_contents() end)
  if not ok or type(fl) ~= "table" then return nil end
  local res = {}
  for name, amount in pairs(fl) do
    if type(amount) == "number" and amount > 0 then res[#res+1] = { name = name, amount = amount } end
  end
  table.sort(res, function(a, b) return a.name < b.name end)
  return res
end

local function entity_detail(ent)
  if not ent or not ent.valid then return nil end
  local d = {
    unit_number = ent.unit_number, name = ent.name, type = ent.type,
    position = pos(ent.position), direction = ent.direction,
    status = ent.status, status_name = ENTITY_STATUS_NAMES[ent.status],
    health = ent.health, minable = ent.minable,
  }
  pcall(function() d.recipe = recipe_view(ent.get_recipe()) end)
  d.inventories = entity_inventories(ent)
  d.fluids = entity_fluids(ent)
  pcall(function() d.electric_network_id = ent.electric_network_id end)
  pcall(function() d.drop_position = safe_pos(ent.drop_position) end)
  pcall(function()
    d.mining_area = { left_top = safe_pos(ent.mining_area.left_top),
                      right_bottom = safe_pos(ent.mining_area.right_bottom) }
  end)
  pcall(function()
    if ent.type == "inserter" then
      d.inserter_filter = ent.inserter_filter and ent.inserter_filter.name or nil
      d.inserter_filters = ent.inserter_filters
    end
  end)
  pcall(function()
    if ent.type == "transport-belt" then
      local line = ent.get_transport_line(1)
      local items = {}
      for _, it in pairs(line.get_contents()) do
        items[#items+1] = { name = it.name, count = it.count }
      end
      d.belt_contents = items
    end
  end)
  pcall(function() d.parameters = ent.parameters end)
  return d
end

local function find_entity_any(surface, unit)
  if not surface or not unit then return nil end
  local ok, e = pcall(function() return game.get_entity_by_unit_number(unit) end)
  if ok and e and e.valid then return e end
  -- Unit numbers are not exposed for every prototype through the global getter.
  -- Scan around the real character; 512 tiles covers a normal factory.
  local p = bot_player()
  local c = p and p.character
  if c then
    local ents = surface.find_entities_filtered({ position = c.position, radius = 512 })
    for _, cand in pairs(ents) do
      if cand.valid and cand.unit_number == unit then return cand end
    end
  end
  return nil
end

wire_poles_near = function(surface, force, center, radius)
  local okid, cid = pcall(function() return defines.wire_connector_id.pole_copper end)
  if not okid then return { ok = false, error = "no pole_copper connector id" } end
  local poles = surface.find_entities_filtered({ type = "electric-pole", force = force,
    position = center, radius = radius or 256 })
  local function reach(p)
    local ok, proto = pcall(function() return p.prototype end)
    if ok and proto then
      local ok2, d = pcall(function() return proto.get_wire_max_distance() end)
      if ok2 and d then return d end
      local ok3, d3 = pcall(function() return proto.max_wire_distance end)
      if ok3 and d3 then return d3 end
    end
    if p.name == "big-electric-pole" then return 30 end
    if p.name == "medium-electric-pole" then return 9 end
    return 7.5
  end
  local linked = 0
  for i = 1, #poles do
    for j = i + 1, #poles do
      local a, b = poles[i], poles[j]
      local dx, dy = a.position.x - b.position.x, a.position.y - b.position.y
      if math.sqrt(dx*dx + dy*dy) <= math.min(reach(a), reach(b)) + 0.01 then
        local oka, ca = pcall(function() return a.get_wire_connector(cid, true) end)
        local okb, cb = pcall(function() return b.get_wire_connector(cid, true) end)
        if oka and okb and ca and cb then
          local okc = pcall(function() return ca.connect_to(cb) end)
          if okc then linked = linked + 1 end
        end
      end
    end
  end
  return { ok = true, poles = #poles, linked = linked }
end

local function set_entity_recipe(ent, recipe_name)
  if not ent or not ent.valid then return false, "invalid entity" end
  if recipe_name == nil or recipe_name == "" then
    local ok = pcall(function() ent.set_recipe(nil) end)
    return ok
  end
  local name = tostring(recipe_name)
  local ok1 = pcall(function() ent.set_recipe(name) end)
  if ok1 then return true end
  local force = ent.force
  local recipe = force and force.recipes[name]
  if recipe then
    local ok2 = pcall(function() ent.set_recipe(recipe) end)
    if ok2 then return true end
  end
  return false, "entity cannot use recipe " .. name
end

local function build_entities_opts(opts)
  local p = bot_player(); if not p then return nil, "no real player connected" end
  local c = p.character; if not c then return nil, "no character" end
  local inv = p.get_main_inventory()
  local surface = opts.surface and game.surfaces[opts.surface] or p.surface
  if not surface then return nil, "no such surface" end
  local consume = opts.consume ~= false
  local placed, failed, used = {}, {}, {}
  for _, spec in ipairs(opts.entities or {}) do
    local name = tostring(spec.name or "")
    local proto = prototypes.entity[name]
    local x, y = tonumber(spec.x or spec.position and spec.position.x), tonumber(spec.y or spec.position and spec.position.y)
    if not proto then
      failed[#failed+1] = { name = name, x = x, y = y, reason = "no such entity prototype" }
    elseif not x or not y then
      failed[#failed+1] = { name = name, reason = "x/y required" }
    else
      local posv = { x = x, y = y }
      local dir = spec.direction or defines.direction.north
      local item = proto.items_to_place_this and proto.items_to_place_this[1]
      local item_name = item and item.name or name
      local item_count = item and (item.count or 1) or 1
      if consume and (not inv or inv.get_item_count(item_name) < item_count) then
        failed[#failed+1] = { name = name, x = x, y = y, reason = "missing " .. item_name }
      elseif not surface.can_place_entity({ name = name, position = posv, direction = dir, force = c.force }) then
        failed[#failed+1] = { name = name, x = x, y = y, reason = "blocked or wrong grid position" }
      else
        if consume then inv.remove({ name = item_name, count = item_count }) end
        local args = { name = name, position = posv, direction = dir, force = c.force, raise_built = true }
        if spec.recipe then args.recipe = spec.recipe end
        local ok, ent = pcall(function() return surface.create_entity(args) end)
        if not ok or not ent then
          if consume then inv.insert({ name = item_name, count = item_count }) end
          failed[#failed+1] = { name = name, x = x, y = y, reason = "create_entity failed: " .. tostring(ent) }
        else
          if spec.recipe then pcall(function() set_entity_recipe(ent, spec.recipe) end) end
          if spec.filter then pcall(function() ent.inserter_filter = spec.filter end) end
          if spec.parameters then pcall(function() ent.parameters = spec.parameters end) end
          placed[#placed+1] = { unit_number = ent.unit_number, name = name, position = posv, item = item_name }
          used[item_name] = (used[item_name] or 0) + item_count
        end
      end
    end
  end
  local wired = nil
  if opts.wire ~= false then
    wired = wire_poles_near(surface, c.force, opts.wire_center or c.position, opts.wire_radius or 256)
  end
  return { ok = true, placed = #placed, failed = #failed, items_used = used,
           entities = placed, failures = failed, wiring = wired }
end

local function resource_patches_opts(opts)
  local p = bot_player(); if not p then return nil, "no real player connected" end
  local c = p.character; if not c then return nil, "no character" end
  local radius = math.max(16, math.min(2000, tonumber(opts.radius) or 256))
  local surface = c.surface
  local seen, patches, nodes = {}, {}, {}
  local res = surface.find_entities_filtered({ position = c.position, radius = radius, type = "resource" })
  local byname = {}
  for _, e in pairs(res) do
    byname[e.name] = byname[e.name] or {}
    table.insert(byname[e.name], e)
  end
  for name, list in pairs(byname) do
    local grid = {}
    for i, e in ipairs(list) do
      local key = math.floor(e.position.x) .. ":" .. math.floor(e.position.y)
      grid[key] = grid[key] or {}
      table.insert(grid[key], e)
    end
    for _, e in ipairs(list) do
      local nkey = e.position.x .. ":" .. e.position.y
      if not seen[nkey] then
        local q, head = { e }, 1
        seen[nkey] = true
        local sum, tiles, minx, miny, maxx, maxy = 0, 0, 1e9, 1e9, -1e9, -1e9
        while head <= #q do
          local cur = q[head]; head = head + 1
          sum = sum + (cur.amount or 0); tiles = tiles + 1
          minx = math.min(minx, cur.position.x); maxx = math.max(maxx, cur.position.x)
          miny = math.min(miny, cur.position.y); maxy = math.max(maxy, cur.position.y)
          local cx, cy = math.floor(cur.position.x), math.floor(cur.position.y)
          for ox = -1, 1 do
            for oy = -1, 1 do
              local bucket = grid[(cx+ox)..":"..(cy+oy)]
              if bucket then
                for _, nb in ipairs(bucket) do
                  local k2 = nb.position.x .. ":" .. nb.position.y
                  if not seen[k2] then seen[k2] = true; q[#q+1] = nb end
                end
              end
            end
          end
        end
        patches[#patches+1] = { name = name, amount = sum, tiles = tiles,
          center = { x = (minx+maxx)/2, y = (miny+maxy)/2 },
          left_top = { x = minx, y = miny }, right_bottom = { x = maxx, y = maxy } }
      end
    end
  end
  table.sort(patches, function(a, b) return a.amount > b.amount end)
  local limit = math.max(1, math.min(200, tonumber(opts.limit) or 40))
  while #patches > limit do table.remove(patches) end
  return { ok = true, radius = radius, count = #patches, patches = patches }
end

remote.add_interface("agentbridge", {
  ping = function()
    out("PONG scenario tick=" .. tostring(game.tick))
    return true
  end,

  detail = function(json)
    local ok, opts = pcall(helpers.json_to_table, json)
    if not ok or type(opts) ~= "table" then out(jenc({ ok = false, error = "invalid options" })) return false end
    local c = char(); if not c then out(jenc({ ok = false, error = "no character" })) return false end
    local limit = math.max(1, math.min(200, tonumber(opts.limit) or 50))
    local list = {}
    if opts.unit_number then
      local e = find_entity_any(c.surface, tonumber(opts.unit_number))
      if not e then out(jenc({ ok = false, error = "no such entity within 512 tiles" })) return false end
      local d = entity_detail(e)
      if d then list[1] = d end
    else
      local center = opts.position and { x = opts.position.x, y = opts.position.y } or c.position
      local filter = { position = center, radius = tonumber(opts.radius) or 16, force = c.force }
      if opts.name then filter.name = opts.name end
      if opts.type then filter.type = opts.type end
      for _, e in pairs(c.surface.find_entities_filtered(filter)) do
        if e.valid and e.type ~= "character" then
          local d = entity_detail(e)
          if d then list[#list+1] = d end
        end
        if #list >= limit then break end
      end
    end
    table.sort(list, function(a, b)
      if a.distance == nil or b.distance == nil then return (a.unit_number or 0) < (b.unit_number or 0) end
      return a.distance < b.distance
    end)
    out(jenc({ ok = true, count = #list, entities = list }))
    return true
  end,

  recipes = function(json)
    local ok, opts = pcall(helpers.json_to_table, json)
    if not ok or type(opts) ~= "table" then opts = {} end
    local f = game.forces.player
    local list = {}
    local enabled_only = opts.enabled_only == true
    local filter = opts.filter and tostring(opts.filter) or nil
    if opts.names then
      for _, n in ipairs(opts.names) do
        local r = f.recipes[n]
        if r then list[#list+1] = recipe_view(r) end
      end
    else
      for name, r in pairs(f.recipes) do
        if (not enabled_only or r.enabled) and (not filter or string.find(name, filter, 1, true)) then
          list[#list+1] = recipe_view(r)
        end
      end
    end
    table.sort(list, function(a, b) return a.name < b.name end)
    local limit = math.max(1, math.min(1000, tonumber(opts.limit) or 300))
    while #list > limit do table.remove(list) end
    out(jenc({ ok = true, count = #list, recipes = list }))
    return true
  end,

  tech_tree = function(json)
    local ok, opts = pcall(helpers.json_to_table, json)
    if not ok or type(opts) ~= "table" then opts = {} end
    local f = game.forces.player
    local list = {}
    for name, t in pairs(f.technologies) do
      local include = true
      if opts.name and name ~= tostring(opts.name) then include = false end
      if opts.researched ~= nil and t.researched ~= opts.researched then include = false end
      if opts.enabled ~= nil and t.enabled ~= opts.enabled then include = false end
      if opts.available_only and not (t.enabled and not t.researched) then include = false end
      if include then
        local pre, unmet, ings = {}, {}, {}
        for _, p in pairs(t.prerequisites or {}) do
          pre[#pre+1] = p.name
          if not p.researched then unmet[#unmet+1] = p.name end
        end
        local cost, count = 0, 0
        pcall(function() cost = t.research_unit_energy end)
        pcall(function() count = t.research_unit_count end)
        pcall(function()
          for _, i in pairs(t.research_unit_ingredients or {}) do
            ings[#ings+1] = { name = i.name, amount = i.amount }
          end
        end)
        local trg = nil
        pcall(function() trg = t.prototype.research_trigger end)
        list[#list+1] = { name = name, researched = t.researched, enabled = t.enabled,
          cost = cost, count = count, ingredients = ings,
          prerequisites = pre, unmet_prerequisites = unmet,
          available = t.enabled and not t.researched and #unmet == 0,
          trigger = trg and trg.type or nil,
          trigger_item = trg and (trg.item or trg.technology) or nil }
      end
    end
    table.sort(list, function(a, b) return a.name < b.name end)
    local limit = math.max(1, math.min(1000, tonumber(opts.limit) or 500))
    while #list > limit do table.remove(list) end
    out(jenc({ ok = true, count = #list, technologies = list }))
    return true
  end,

  stats = function(json)
    local ok, opts = pcall(helpers.json_to_table, json)
    if not ok or type(opts) ~= "table" then opts = {} end
    local items = opts.items or {
      "iron-plate","copper-plate","steel-plate","stone-brick","coal","iron-ore","copper-ore",
      "electronic-circuit","advanced-circuit","processing-unit","iron-gear-wheel","copper-cable",
      "plastic-bar","sulfur","engine-unit","electric-engine-unit",
      "automation-science-pack","logistic-science-pack","chemical-science-pack",
      "low-density-structure","rocket-fuel","rocket-part","space-science-pack",
    }
    local prod = game.forces.player.get_item_production_statistics(game.surfaces.nauvis)
    local list = {}
    for _, name in ipairs(items) do
      -- Item production statistics reject fluids; keep one bad name from
      -- killing the whole query and report it explicitly instead.
      local ok_in, p1 = pcall(function() return prod.get_input_count(name) end)
      local ok_out, p2 = pcall(function() return prod.get_output_count(name) end)
      if ok_in and ok_out then
        list[#list+1] = { name = name, produced = p1, consumed = p2 }
      else
        list[#list+1] = { name = name, error = "not an item (fluids are not valid here)" }
      end
    end
    out(jenc({ ok = true, surface = "nauvis", items = list }))
    return true
  end,

  alerts = function(json)
    local ok, opts = pcall(helpers.json_to_table, json)
    if not ok or type(opts) ~= "table" then opts = {} end
    local s = game.surfaces[opts.surface or "nauvis"]
    if not s then out(jenc({ ok = false, error = "no such surface" })) return false end
    local bad = {
      no_power = true, low_power = true, no_fuel = true, no_recipe = true,
      no_ingredients = true, full_output = true, item_ingredient_shortage = true,
      fluid_ingredient_shortage = true, waiting_for_space_in_destination = true,
      no_resources = true, no_minable_resources = true, not_connected = true,
      disabled_by_script = true, marked_for_deconstruction = true,
    }
    local counts, list = {}, {}
    local limit = math.max(1, math.min(300, tonumber(opts.limit) or 100))
    for _, e in pairs(s.find_entities_filtered({ force = "player" })) do
      local sn = ENTITY_STATUS_NAMES[e.status]
      if sn and bad[sn] and e.type ~= "electric-pole" then
        counts[sn] = (counts[sn] or 0) + 1
        if #list < limit then
          list[#list+1] = { unit_number = e.unit_number, name = e.name, type = e.type,
            position = pos(e.position), status = sn }
        end
      end
    end
    table.sort(list, function(a, b) return a.name < b.name end)
    out(jenc({ ok = true, counts = counts, count = #list, alerts = list }))
    return true
  end,

  wire = function()
    local p = bot_player(); if not p then out(jenc({ ok = false, error = "no real player" })) return false end
    local c = p.character; if not c then out(jenc({ ok = false, error = "no character" })) return false end
    local res = wire_poles_near(p.surface, p.force, c.position, 512)
    res.ok = true
    out(jenc(res))
    return true
  end,

  set_recipe = function(json)
    local ok, opts = pcall(helpers.json_to_table, json)
    if not ok or type(opts) ~= "table" then out(jenc({ ok = false, error = "invalid options" })) return false end
    local c = char(); if not c then out(jenc({ ok = false, error = "no character" })) return false end
    local unit = tonumber(opts.unit_number or opts.target)
    local e = unit and find_entity_any(c.surface, unit) or nil
    if not e then out(jenc({ ok = false, error = "no such entity" })) return false end
    if e.type ~= "assembling-machine" then
      out(jenc({ ok = false, error = e.name .. " has a fixed recipe; set_recipe applies to assembling machines (including refinery/chemical plant)" }))
      return false
    end
    local ok2, err = set_entity_recipe(e, opts.recipe)
    if not ok2 then out(jenc({ ok = false, error = err or "set_recipe failed" })) return false end
    out(jenc({ ok = true, unit_number = e.unit_number, name = e.name,
      recipe = recipe_view(e.get_recipe()) }))
    return true
  end,

  build_entities = function(json)
    local ok, opts = pcall(helpers.json_to_table, json)
    if not ok or type(opts) ~= "table" then out(jenc({ ok = false, error = "invalid options" })) return false end
    local res, err = build_entities_opts(opts)
    if not res then out(jenc({ ok = false, error = err })) return false end
    out(jenc(res))
    return true
  end,

  resource_patches = function(json)
    local ok, opts = pcall(helpers.json_to_table, json)
    if not ok or type(opts) ~= "table" then opts = {} end
    local res, err = resource_patches_opts(opts)
    if not res then out(jenc({ ok = false, error = err })) return false end
    out(jenc(res))
    return true
  end,

  instruct = function(text, player_index)
    inbox_add("console", tostring(text or ""), player_index)
    out(jenc({ ok = true, seq = ns().inbox_seq or 0 }))
    return true
  end,

  -- Warm-up: the first Lua console command after loading a save is swallowed
  -- by the "disable achievements" confirmation.  The bridge sends this twice.
  warmup = function()
    out("READY tick=" .. tostring(game.tick))
    return true
  end,

  state = function(radius)
    out(jenc(state(radius)))
    return true
  end,

  submit = function(json)
    local ok, action = pcall(helpers.json_to_table, json)
    if not ok or type(action) ~= "table" then
      out(jenc({ ok = false, error = "invalid json action" }))
      return false
    end
    ns().next_job_id = (ns().next_job_id or 0) + 1
    local job = {
      id = ns().next_job_id,
      kind = tostring(action.kind or ""),
      params = action,
      status = "queued",
      phase = "queued",
      created_tick = game.tick,
    }
    table.insert(ns().queue, job)
    emit("job_submitted", { id = job.id, kind = job.kind })
    start_next_job()
    out(jenc({ ok = true, id = job.id, queue = #ns().queue, running = ns().job and ns().job.id or nil }))
    return true
  end,

  cancel = function(id)
    if ns().job and (not id or ns().job.id == id) then
      local current = ns().job
      stop_motion()
      current.status = "canceled"
      current.detail = "canceled by agent"
      current.finished_tick = game.tick
      emit("job_canceled", { id = current.id, kind = current.kind })
      ns().job = nil
      ns().path_handle = nil
      ns().start_next_tick = game.tick + 1
      out(jenc({ ok = true, canceled = current.id }))
      return true
    end
    for i, q in pairs(ns().queue) do
      if not id or q.id == id then
        table.remove(ns().queue, i)
        emit("job_canceled", { id = q.id, kind = q.kind, reason = "cancel_job" })
        out(jenc({ ok = true, canceled = q.id }))
        return true
      end
    end
    out(jenc({ ok = false, error = "no such job" }))
    return false
  end,

  cancel_all = function()
    local canceled = 0
    if ns().job then
      emit("job_canceled", { id = ns().job.id, kind = ns().job.kind, reason = "cancel_all" })
      canceled = canceled + 1
      stop_motion()
      ns().job = nil
    end
    for _, q in ipairs(ns().queue) do
      emit("job_canceled", { id = q.id, kind = q.kind, reason = "cancel_all" })
      canceled = canceled + 1
    end
    ns().queue = {}
    ns().path_handle = nil
    out(jenc({ ok = true, canceled = canceled }))
    return true
  end,

  events = function(since)
    local list = {}
    for _, ev in pairs(ns().events) do
      if ev.seq > (since or 0) then table.insert(list, ev) end
    end
    out(jenc({ events = list, last_seq = ns().event_seq or 0 }))
    return true
  end,

  scan = function(radius)
    local c = char()
    if not c then out(jenc({ ok = false, error = "no character" })) return false end
    out(jenc({ ok = true, character = char_state(c),
      resources = scan_resources(c, radius or DEFAULT_SCAN_RADIUS, 24),
      entities = scan_entities(c, radius or DEFAULT_SCAN_RADIUS, 100) }))
    return true
  end,

  recipe = function(name)
    local c = char()
    local force = c and c.force or game.forces.player
    local recipe = force.recipes[name]
    if not recipe then out(jenc({ ok = false, error = "no such recipe" })) return false end
    local ingredients = {}
    for _, ing in pairs(recipe.ingredients) do
      table.insert(ingredients, { type = ing.type, name = ing.name, amount = ing.amount })
    end
    local products = {}
    for _, p in pairs(recipe.products or {}) do
      table.insert(products, { type = p.type, name = p.name, amount = p.amount, probability = p.probability })
    end
    local categories = {}
    pcall(function()
      for _, cat in pairs(recipe.categories or {}) do table.insert(categories, cat) end
    end)
    out(jenc({ ok = true, name = recipe.name, enabled = recipe.enabled,
      categories = categories, energy = recipe.energy,
      ingredients = ingredients, products = products }))
    return true
  end,

  techs = function(limit)
    local c = char()
    local force = c and c.force or game.forces.player
    local list = {}
    for name, tech in pairs(force.technologies) do
      if tech.enabled and not tech.researched then
        local cost = nil
        local okc, cval = pcall(function() return tech.research_unit_energy end)
        if okc then cost = cval end
        local pre = {}
        local unmet = {}
        local oktrg, trg = pcall(function() return tech.prototype.research_trigger end)
        if not oktrg then trg = nil end
        for _, p in pairs(tech.prerequisites or {}) do
          table.insert(pre, p.name)
          if not p.researched then table.insert(unmet, p.name) end
        end
        table.insert(list, { name = name, researched = false, cost = cost,
          prerequisites = pre, unmet_prerequisites = unmet, available = (#unmet == 0),
          trigger = trg and trg.type or nil,
          trigger_item = trg and (trg.item or trg.technology) or nil,
          trigger_count = trg and trg.count or nil })
      end
      if #list >= (limit or 40) then break end
    end
    table.sort(list, function(a, b) return a.name < b.name end)
    out(jenc({ ok = true, technologies = list }))
    return true
  end,

  ensure = function()
    local c = ensure_char()
    out(c and jenc({ ok = true, unit_number = c.unit_number, position = c.position }) or jenc({ ok = false, error = "spawn failed" }))
    return c ~= nil
  end,

  inbox = function(since)
    local list = {}
    for _, ev in pairs(ns().inbox) do
      if ev.seq > (since or 0) then table.insert(list, ev) end
    end
    out(jenc({ ok = true, events = list, last_seq = ns().inbox_seq or 0 }))
    return true
  end,

  clear_inbox = function()
    ns().inbox = {}
    out(jenc({ ok = true, last_seq = ns().inbox_seq or 0 }))
    return true
  end,

  set_eval = function(flag)
    ns().allow_eval = flag and true or false
    out(jenc({ ok = true, allow_eval = ns().allow_eval }))
    return true
  end,

  eval = function(code)
    if not ns().allow_eval then
      out(jenc({ ok = false, error = "eval is disabled; call set_eval(true) explicitly" }))
      return false
    end
    local f, err = load(code)
    if not f then out(jenc({ ok = false, error = tostring(err) })) return false end
    local ok, res = pcall(f)
    if not ok then out(jenc({ ok = false, error = tostring(res) })) return false end
    out(jenc({ ok = true, result = tostring(res) }))
    return true
  end,

  set_bot_name = function(name)
    ns().bot_name = tostring(name or "LLM-Bot")
    ns().char_id = nil
    ensure_char()
    out(jenc({ ok = true, bot_name = ns().bot_name }))
    return true
  end,

  set_bare = function(flag)
    ns().allow_bare = flag and true or false
    if ns().allow_bare then ensure_char() end
    out(jenc({ ok = true, allow_bare = ns().allow_bare }))
    return true
  end,

  blueprints = function()
    out(jenc({ ok = true, blueprints = blueprint_list() }))
    return true
  end,

  platforms = function()
    local ps, planets = platform_list()
    out(jenc({ ok = true, platforms = ps, planets = planets }))
    return true
  end,

  find_water = function(radius)
    local res, err = find_water_opts(radius)
    if not res then out(jenc({ ok = false, error = err })) return false end
    res.ok = true
    out(jenc(res))
    return true
  end,

  blueprint_create = function(json)
    local ok, opts = pcall(helpers.json_to_table, json)
    if not ok or type(opts) ~= "table" then out(jenc({ ok = false, error = "invalid options" })) return false end
    local res, err = create_blueprint_opts(opts)
    if not res then out(jenc({ ok = false, error = err })) return false end
    res.ok = true
    out(jenc(res))
    return true
  end,

  blueprint_build = function(json)
    local ok, opts = pcall(helpers.json_to_table, json)
    if not ok or type(opts) ~= "table" then out(jenc({ ok = false, error = "invalid options" })) return false end
    local res, err, extra = build_blueprint_opts(opts)
    if not res then
      local payload = { ok = false, error = err }
      for k, v in pairs(extra or {}) do payload[k] = v end
      out(jenc(payload))
      return false
    end
    res.ok = true
    out(jenc(res))
    return true
  end,

  save = function()
    local ok, err = pcall(function() game.server_save() end)
    out(ok and jenc({ ok = true }) or jenc({ ok = false, error = tostring(err) }))
    return ok
  end,

  pause = function(flag)
    game.tick_paused = flag and true or false
    out(jenc({ ok = true, paused = game.tick_paused }))
    return true
  end,

  speed = function(value)
    local v = tonumber(value) or 1
    if v < 0.01 then v = 0.01 end
    if v > 100 then v = 100 end
    game.speed = v
    out(jenc({ ok = true, speed = game.speed }))
    return true
  end,

  respawn = function(x, y)
    if not ns().allow_bare then
      out(jenc({ ok = false, error = "respawn is disabled for a real connected player" }))
      return false
    end
    stop_motion()
    if ns().char_id then
      local old = char()
      if old and old.valid then old.destroy() end
    end
    ns().char_id = nil
    if type(x) == "number" and type(y) == "number" then ns().spawn_point = { x = x, y = y } end
    local c = ensure_char()
    out(c and jenc({ ok = true, unit_number = c.unit_number, position = c.position }) or jenc({ ok = false, error = "spawn failed" }))
    return c ~= nil
  end,
})

-- lifecycle -----------------------------------------------------------------

script.on_init(function()
  init_storage()
  if not storage.crashed_ship_items then
    local ok, err = pcall(freeplay_module.on_init)
    if not ok then log("[AGENT] freeplay init failed: " .. tostring(err)) end
  end
  ns().bot_name = ns().bot_name or "LLM-Bot"
  ns().allow_bare = ns().allow_bare == true
  ensure_char()
  emit("scenario_init", { version = VERSION, bot_name = ns().bot_name })
end)

script.on_configuration_changed(function()
  init_storage()
  if not char() then ensure_char() end
  emit("mod_configured", { version = VERSION })
end)

script.on_event(defines.events.on_script_path_request_finished, function(event)
  local job = ns().job
  if not job or job.path_handle ~= event.id then return end
  if event.try_again_later then
    job.retry_at = game.tick + 30
    return
  end
  if not event.path or #event.path == 0 then
    if job.kind == "walk" and job.data and job.data.goal then
      set_phase(job, "walking_direct", "no path; direct fallback")
      return
    end
    job_fail("no path found")
    return
  end
  job.path = event.path
  job.path_index = 1
  job.last_check = game.tick
  local c = char()
  job.last_pos = c and pos(c.position) or nil
  job.stuck = 0
  set_phase(job, "following", "path length " .. tostring(#event.path))
end)

script.on_event(defines.events.on_entity_died, function(event)
  if ns().char_id and event.entity and event.entity.unit_number == ns().char_id then
    emit("character_died", { cause = event.cause and event.cause.name or nil, tick = event.tick })
    ns().char_id = nil
    if ns().job then
      stop_motion()
      local job = ns().job
      job.status = "failed"
      job.detail = "character died"
      emit("job_failed", { id = job.id, kind = job.kind, ok = false, detail = job.detail })
      ns().job = nil
    end
  end
end)

script.on_event(defines.events.on_console_chat, function(event)
  if event.player_index then
    emit("chat", { player_index = event.player_index, message = event.message })
  end
  local msg = event.message or ""
  local text = msg:match("^%s*@bot%s+(.+)$") or msg:match("^%s*bot:%s*(.+)$") or msg:match("^%s*!bot%s+(.+)$")
  if text then
    inbox_add("chat", text, event.player_index)
  end
end)

commands.add_command("bot", "Send an instruction to the LLM bot: /bot <text>", function(event)
  inbox_add("command", event.parameter or "", event.player_index)
end)

script.on_event(defines.events.on_tick, function()
  if not ns().version then init_storage() end
  if not storage.crashed_ship_items then
    local ok, err = pcall(freeplay_module.on_init)
    if not ok then log("[AGENT] freeplay lazy init failed: " .. tostring(err)) end
  end

  -- The freeplay crash-site cutscene would freeze the bot's controller.
  local bp = game.get_player(ns().bot_name or "LLM-Bot")
  if bp and bp.valid and bp.connected and bp.controller_type == defines.controllers.cutscene then
    pcall(function() bp.exit_cutscene() end)
  end

  if ns().start_next_tick and game.tick >= ns().start_next_tick then
    ns().start_next_tick = nil
    start_next_job()
  end

  if ns().allow_bare and ns().auto_respawn and game.tick % 120 == 0 and not char() then
    ensure_char()
  end

  local job = ns().job
  if job then
    if job.phase == "waiting" then
      job.data.remaining = (job.data.remaining or 0) - 1
      if job.data.remaining <= 0 then
        finish_job(true, "waited")
      end
    elseif job.phase == "pathing" and job.retry_at and game.tick >= job.retry_at then
      job.retry_at = nil
      if job.kind == "walk" then
        request_path(job, job.data.goal)
      elseif job.kind == "mine" then
        request_path(job, job.data.goal)
      end
    else
      local ok, err = pcall(run_job, job)
      if not ok then
        log("[AGENT] job error: " .. tostring(err))
        job_fail("lua error: " .. tostring(err))
      end
    end
  end
end)

log("[AGENT] agentbridge v" .. VERSION .. " loaded")
