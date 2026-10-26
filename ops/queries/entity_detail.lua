local ids = {43, 44, 15, 16}
local lines = {}
-- Map status enum back to names.
local status_names = {}
for k, v in pairs(defines.entity_status) do status_names[v] = k end
-- Map inventory enum back to names.
local inv_names = {}
for k, v in pairs(defines.inventory) do inv_names[v] = k end
for _, id in ipairs(ids) do
  local e
  for _, cand in pairs(game.surfaces.nauvis.find_entities_filtered{area={{-60,20},{30,80}}}) do
    if cand.unit_number == id then e = cand break end
  end
  if not e then
    lines[#lines+1] = "#"..id.." not found"
  else
    lines[#lines+1] = string.format("#%d %s @(%.1f,%.1f) status=%s(%s) dir=%s",
      id, e.name, e.position.x, e.position.y, tostring(e.status), tostring(status_names[e.status]), tostring(e.direction))
    local maxi = (e.get_max_inventory_index and e.get_max_inventory_index()) or 10
    for i = 1, maxi do
      local ok, inv = pcall(function() return e.get_inventory(i) end)
      if ok and inv then
        local contents = inv.get_contents()
        if contents and #contents > 0 then
          local parts = {}
          for _, c in pairs(contents) do parts[#parts+1] = c.name.."x"..c.count end
          lines[#lines+1] = string.format("  inv[%d %s] %s", i, tostring(inv_names[i]), table.concat(parts, ", "))
        end
      end
    end
    if e.type == "mining-drill" then
      local ok, ma = pcall(function() return e.mining_area end)
      if ok and ma then
        lines[#lines+1] = string.format("  mining_area=(%.1f,%.1f)-(%.1f,%.1f)", ma.left_top.x, ma.left_top.y, ma.right_bottom.x, ma.right_bottom.y)
      end
    end
  end
end
return table.concat(lines, "\n")
