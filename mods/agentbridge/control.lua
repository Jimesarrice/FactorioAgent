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

local function char()
  if not ns().char_id then return nil end
  local c = game.get_entity_by_unit_number(ns().char_id)
  if c and c.valid then return c end
  ns().char_id = nil
  return nil
end

local function ensure_char()
  local c = char()
  if c then return c end
  local s = game.surfaces[1]
  if not s then return nil end
  local spawn = ns().spawn_point or { x = 0, y = 0 }
  local p = s.find_non_colliding_position("character", spawn, 64, 0.5)
  if not p then return nil end
  local e = s.create_entity({ name = "character", position = p, force = game.forces.player })
  if not e then return nil end
  ns().char_id = e.unit_number
  ns().spawn_point = pos(e.position)
  log("[AGENT] spawned character unit=" .. tostring(e.unit_number))
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

local function init_storage()
  ns().version = VERSION
  ns().next_job_id = ns().next_job_id or 0
  ns().queue = ns().queue or {}
  ns().events = ns().events or {}
  ns().event_seq = ns().event_seq or 0
  ns().auto_respawn = ns().auto_respawn ~= false
  ns().spawn_point = ns().spawn_point or { x = 0, y = 0 }
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

local function find_nearest_resource(c, name, radius)
  local ents = c.surface.find_entities_filtered({ position = c.position, radius = radius, name = name, type = "resource" })
  local best, bestd
  for _, e in pairs(ents) do
    if e.valid then
      local d = d2(c.position, e.position)
      if not bestd or d < bestd then best, bestd = e, d end
    end
  end
  return best
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
  end
end

local function run_mine(job)
  local c = char()
  if not c then return job_fail("no character") end
  local inv = c.get_inventory(defines.inventory.character_main)
  local item = job.data.item or item_for_resource(job.params.name)
  if job.phase == "init" then
    if not SOLID_RESOURCES[job.params.name] then
      return job_fail("unsupported resource '" .. tostring(job.params.name) .. "' (solid resources only)")
    end
    job.data.count = math.max(1, math.floor(job.params.count or 1))
    job.data.radius = job.params.radius or 64
    job.data.start_count = count_item(inv, item)
    job.deadline = game.tick + (job.params.timeout_ticks or 60 * 60 * 8)
    local target = find_nearest_resource(c, job.params.name, job.data.radius)
    if not target then return job_fail("no " .. job.params.name .. " within " .. job.data.radius .. " tiles") end
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
    local still = target and c.surface.find_entities_filtered({ position = target, radius = 0.6, name = job.data.target_name, type = "resource" })
    if not still or #still == 0 then
      -- depleted: look for the next tile
      local next_target = find_nearest_resource(c, job.params.name, job.data.radius)
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
    local ok, err2 = pcall(function() c.begin_crafting({ recipe = job.params.recipe, count = job.data.count }) end)
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
  local args = { name = name, position = p, direction = direction, force = c.force, raise_built = true }
  if job.params.recipe then args.recipe = job.params.recipe end
  local ent = c.surface.create_entity(args)
  if not ent then return job_fail("create_entity failed") end
  inv.remove({ name = item, count = 1 })
  finish_job(true, "placed " .. name, { unit_number = ent.unit_number, position = p, item = item })
end

local function find_target_entity(c, job)
  if job.params.target then
    local e = game.get_entity_by_unit_number(job.params.target)
    if e and e.valid then return e end
    -- Most buildings are not exposed by get_entity_by_unit_number (that API
    -- only covers prototypes with the get-by-unit-number flag), so match the
    -- unit number from a local scan instead.
    local ents = c.surface.find_entities_filtered({ position = c.position, radius = job.params.radius or 48 })
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
  local tech = c.force.technologies[job.params.tech]
  if not tech then return job_fail("no such technology: " .. tostring(job.params.tech)) end
  if tech.researched then return finish_job(true, "already researched") end
  if not tech.enabled then return job_fail("technology locked") end
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

local function run_job(job)
  if job.kind == "walk" then return run_walk(job)
  elseif job.kind == "mine" then return run_mine(job)
  elseif job.kind == "craft" then return run_craft(job)
  elseif job.kind == "place" then return run_place(job)
  elseif job.kind == "insert" then return run_insert(job)
  elseif job.kind == "take" then return run_take(job)
  elseif job.kind == "research" then return run_research(job)
  elseif job.kind == "wait" then return run_wait(job)
  elseif job.kind == "say" then return run_say(job)
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

remote.add_interface("agentbridge", {
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
        out(jenc({ ok = true, canceled = q.id }))
        return true
      end
    end
    out(jenc({ ok = false, error = "no such job" }))
    return false
  end,

  cancel_all = function()
    if ns().job then
      stop_motion()
      ns().job = nil
    end
    ns().queue = {}
    ns().path_handle = nil
    out(jenc({ ok = true }))
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
    for _, p in pairs(recipe.products) do
      table.insert(products, { type = p.type, name = p.name, amount = p.amount, probability = p.probability })
    end
    out(jenc({ ok = true, name = recipe.name, enabled = recipe.enabled,
      category = recipe.category, energy = recipe.energy,
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
        for _, p in pairs(tech.prerequisites or {}) do
          table.insert(pre, p.name)
          if not p.researched then table.insert(unmet, p.name) end
        end
        table.insert(list, { name = name, researched = false, cost = cost,
          prerequisites = pre, unmet_prerequisites = unmet, available = (#unmet == 0) })
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
  ensure_char()
  emit("mod_init", { version = VERSION })
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
end)

script.on_event(defines.events.on_tick, function()
  if not ns().version then init_storage() end

  if ns().start_next_tick and game.tick >= ns().start_next_tick then
    ns().start_next_tick = nil
    start_next_job()
  end

  if ns().auto_respawn and game.tick % 120 == 0 and not char() then
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
