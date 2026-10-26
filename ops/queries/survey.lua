local s = game.surfaces.nauvis
local out = {}
for _, r in pairs(s.find_entities_filtered{type="resource"}) do
  local n = r.name
  out[n] = out[n] or {count=0, amount=0, minx=1e9, miny=1e9, maxx=-1e9, maxy=-1e9}
  local o = out[n]
  o.count = o.count + 1
  o.amount = o.amount + r.amount
  o.minx = math.min(o.minx, r.position.x)
  o.maxx = math.max(o.maxx, r.position.x)
  o.miny = math.min(o.miny, r.position.y)
  o.maxy = math.max(o.maxy, r.position.y)
end
local lines = {}
for n, o in pairs(out) do
  lines[#lines+1] = string.format("%s count=%d amount=%d box=(%.1f,%.1f)-(%.1f,%.1f)",
    n, o.count, o.amount, o.minx, o.miny, o.maxx, o.maxy)
end
table.sort(lines)
-- nearest resource per type to the player's character
local c = game.players["LLM-Bot"] and game.players["LLM-Bot"].character
if c then
  lines[#lines+1] = "--- nearest to character at " .. c.position.x .. "," .. c.position.y
  for _, n in ipairs({"iron-ore","copper-ore","coal","stone","crude-oil","uranium-ore"}) do
    local best, bestd
    for _, e in pairs(s.find_entities_filtered{name=n, position=c.position, radius=1000}) do
      local dx, dy = e.position.x-c.position.x, e.position.y-c.position.y
      local d = dx*dx+dy*dy
      if not bestd or d < bestd then best, bestd = e, d end
    end
    if best then
      lines[#lines+1] = string.format("%s nearest=(%.1f,%.1f) d=%.1f", n,
        best.position.x, best.position.y, math.sqrt(bestd))
    end
  end
end
return table.concat(lines, "\n")
