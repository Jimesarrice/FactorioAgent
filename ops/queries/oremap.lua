local s = game.surfaces.nauvis
local lines = {}
local header = "     "
for x = -50, -20 do
  if x % 5 == 0 then header = header .. string.format("%-5d", x) end
end
lines[#lines+1] = header
for y = 36, 52 do
  local row = {}
  for x = -50, -20 do
    local tile = s.get_tile(x, y)
    local ch = "."
    if tile.name == "water" then ch = "~" end
    local es = s.find_entities_filtered{area={{x-0.4,y-0.4},{x+0.4,y+0.4}}}
    for _, e in pairs(es) do
      if e.type == "resource" then
        if e.name == "iron-ore" then ch="i" elseif e.name=="coal" then ch="k"
        elseif e.name=="stone" then ch="s" elseif e.name=="copper-ore" then ch="c" end
      elseif e.type == "tree" then ch="T"
      elseif e.name == "character" then ch="P"
      elseif e.type == "simple-entity" then ch="R"
      elseif e.valid and e.type ~= "resource" and e.type ~= "tree" and e.type ~= "fish" then ch="E"
      end
    end
    row[#row+1] = ch
  end
  lines[#lines+1] = string.format("%4d %s", y, table.concat(row))
end
return table.concat(lines, "\n")
