local s = game.surfaces.nauvis
local c = game.players["LLM-Bot"].character
local lines = {}
lines[#lines+1] = "character at "..c.position.x..","..c.position.y
for _, e in pairs(s.find_entities_filtered{area={{-20,-10},{90,70}}, force="player"}) do
  if e.type ~= "character" then
    lines[#lines+1] = string.format("%s#%s @(%.1f,%.1f) dir=%s status=%s",
      e.name, tostring(e.unit_number), e.position.x, e.position.y, tostring(e.direction),
      tostring(e.status))
  end
end
table.sort(lines)
return table.concat(lines, "\n")
