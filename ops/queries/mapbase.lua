local s = game.surfaces.nauvis
local x0, y0, x1, y1, step = -80, 0, 80, 120, 2
local lines = {}
for y = y0, y1, step do
  local row = {}
  for x = x0, x1, step do
    local t = s.get_tile(x, y)
    local ch = "."
    if t.name == "water" or t.name == "deepwater" then ch = "~"
    elseif t.name == "cliff" then ch = "#"
    end
    local ents = s.find_entities_filtered{area={{x-1,y-1},{x+1,y+1}}, type="resource"}
    if #ents > 0 then
      local n = ents[1].name
      if n == "iron-ore" then ch="i" elseif n=="copper-ore" then ch="c"
      elseif n=="coal" then ch="k" elseif n=="stone" then ch="s" end
    end
    local tree = s.find_entities_filtered{area={{x-1,y-1},{x+1,y+1}}, type="tree"}
    if #tree > 0 and ch == "." then ch = "T" end
    local cl = s.find_entities_filtered{area={{x-1,y-1},{x+1,y+1}}, type="cliff"}
    if #cl > 0 and ch == "." then ch = "#" end
    row[#row+1] = ch
  end
  lines[#lines+1] = string.format("%4d %s", y, table.concat(row))
end
local header = "     "
for x = x0, x1, step do
  if x % 20 == 0 then header = header..string.sub(string.format("%-10d", x),1,10) end
end
return header.."\n"..table.concat(lines, "\n")
