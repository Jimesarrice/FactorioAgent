local s = game.surfaces.nauvis
local c = game.players["LLM-Bot"].character
local best
for _, r in pairs(s.find_entities_filtered{name="iron-ore", area={{-70,30},{-20,70}}}) do
  local cx, cy = r.position.x, r.position.y
  -- candidate drill centre sits half a tile into the patch; test the 2x2
  -- area as (cx,cy)-(cx+2,cy+2) in tile centres
  local pure, free = true, true
  for dx = 0, 1 do
    for dy = 0, 1 do
      local x, y = cx + dx, cy + dy
      local tiles = s.find_entities_filtered{area={{x-0.5,y-0.5},{x+0.5,y+0.5}}}
      local has_iron = false
      for _, e in pairs(tiles) do
        if e.type == "resource" then
          if e.name ~= "iron-ore" then pure = false end
          if e.name == "iron-ore" then has_iron = true end
        elseif e.name ~= "fish" then
          free = false
        end
      end
      if not has_iron then pure = false end
    end
  end
  if pure and free then
    local d = (cx-c.position.x)^2 + (cy-c.position.y)^2
    if not best or d < best.d then best = {x=cx, y=cy, d=d} end
  end
end
if not best then return "no pure 2x2 iron spot" end
-- find a free output tile to the east and a walkable spot
local out = {x=best.x+2, y=best.y+1}
local walk = s.find_non_colliding_position("character", {x=best.x+3, y=best.y+1}, 4, 0.25)
return string.format("drill_center=(%.1f,%.1f) output=(%.1f,%.1f) walk=(%.1f,%.1f) d=%.1f",
  best.x, best.y, out.x, out.y, walk and walk.x or -1, walk and walk.y or -1, math.sqrt(best.d))
