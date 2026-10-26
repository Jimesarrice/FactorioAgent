local s = game.surfaces.nauvis
local poles = s.find_entities_filtered{type="electric-pole", force="player"}
local done, failed = 0, 0
local cid
local okid, id = pcall(function() return defines.wire_connector_id.pole_copper end)
if not okid then return "no pole_copper connector id: "..tostring(id) end
cid = id
local function reach(p)
  local ok, proto = pcall(function() return p.prototype end)
  if ok and proto then
    local ok2, d = pcall(function() return proto.get_wire_max_distance and proto.get_wire_max_distance() or proto.max_wire_distance end)
    if ok2 and d then return d end
  end
  if p.name == "big-electric-pole" then return 30 end
  if p.name == "medium-electric-pole" then return 9 end
  return 7.5
end
for i = 1, #poles do
  for j = i + 1, #poles do
    local a, b = poles[i], poles[j]
    local dx, dy = a.position.x - b.position.x, a.position.y - b.position.y
    local dist = math.sqrt(dx*dx + dy*dy)
    if dist <= math.min(reach(a), reach(b)) + 0.01 then
      local oka, ca = pcall(function() return a.get_wire_connector(cid, true) end)
      local okb, cb = pcall(function() return b.get_wire_connector(cid, true) end)
      if oka and okb and ca and cb then
        local okc, res = pcall(function() return ca.connect_to(cb) end)
        if okc then done = done + 1 else failed = failed + 1 end
      else
        failed = failed + 1
      end
    end
  end
end
return string.format("poles=%d attempts_ok=%d failed=%d", #poles, done, failed)
