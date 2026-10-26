local s = game.surfaces.nauvis
local function tile_ent(x, y)
  local es = s.find_entities_filtered{area={{x-0.45,y-0.45},{x+0.45,y+0.45}}}
  for _, e in pairs(es) do
    if e.type ~= "fish" then return e end
  end
  return nil
end
local function check_res(x, y, want)
  local e = tile_ent(x, y)
  return e and e.type == "resource" and e.name == want
end
local function check_free(x, y)
  local e = tile_ent(x, y)
  return not e
end
local dirs = {
  {name="east", dx=2, dy=0, d=4}, {name="south", dx=0, dy=2, d=8},
  {name="west", dx=-2, dy=0, d=12}, {name="north", dx=0, dy=-2, d=0},
}
local function search(want, cx, cy, radius)
  local found = {}
  for x = cx - radius, cx + radius, 2 do
    for y = cy - radius, cy + radius, 2 do
      local pure = true
      for dx = -1, 1 do
        for dy = -1, 1 do
          if not check_res(x + dx, y + dy, want) then pure = false end
        end
      end
      if pure then
        for _, dir in ipairs(dirs) do
          if check_free(x + dir.dx, y + dir.dy) then
            found[#found+1] = string.format("%s drill=(%.1f,%.1f) out=%s furnace=(%.1f,%.1f)",
              want, x, y, dir.name, x + dir.dx, y + dir.dy)
          end
        end
      end
    end
  end
  return found
end
local lines = {}
for _, r in ipairs({{"iron-ore",-44,47,12},{"copper-ore",18,62,14}}) do
  local found = search(r[1], r[2], r[3], r[4])
  lines[#lines+1] = "--- "..r[1].." sites="..#found
  for i = 1, math.min(#found, 8) do lines[#lines+1] = found[i] end
end
return table.concat(lines, "\n")
