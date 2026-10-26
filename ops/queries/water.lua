local s = game.surfaces.nauvis
local want = {{0,0},{-20,40},{0,40},{20,40},{40,40},{20,20},{40,20}}
local lines = {}
for _, p in ipairs(want) do
  local best, bestd
  for _, t in pairs(s.find_tiles_filtered{name="water", area={{p[1]-150,p[2]-150},{p[1]+150,p[2]+150}}}) do
    local dx, dy = t.position.x-p[1], t.position.y-p[2]
    local d = dx*dx+dy*dy
    if not bestd or d < bestd then best, bestd = t, d end
  end
  if best then
    lines[#lines+1] = string.format("from(%d,%d) nearest water=(%.1f,%.1f) d=%.1f", p[1],p[2],best.position.x,best.position.y,math.sqrt(bestd))
  end
end
-- water around proposed base (-5,45)
local n = 0
local box = {{-80,0},{60,80}}
for _ in pairs(s.find_tiles_filtered{name="water", area=box}) do n = n + 1 end
lines[#lines+1] = string.format("water tiles in (-80,0)-(60,80): %d", n)
return table.concat(lines, "\n")
