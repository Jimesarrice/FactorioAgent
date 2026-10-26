local x1, y1, x2, y2 = -60, 20, 30, 80
local out = {}
local function invdef(name)
  local ok, v = pcall(function() return defines.inventory[name] end)
  return ok and v or nil
end
local src_i, res_i = invdef("furnace_source"), invdef("furnace_result")
for _, e in pairs(game.surfaces.nauvis.find_entities_filtered{area={{x1,y1},{x2,y2}}}) do
  if e.type ~= "resource" and e.type ~= "tree" and e.type ~= "cliff" and e.type ~= "simple-entity"
     and e.type ~= "fish" and e.type ~= "character" then
    local line = string.format("%s#%s @(%.1f,%.1f) dir=%s status=%s",
      e.name, tostring(e.unit_number), e.position.x, e.position.y, tostring(e.direction), tostring(e.status))
    if src_i then
      local ok, inv = pcall(function() return e.get_inventory(src_i) end)
      if ok and inv then
        line = line .. string.format(" src(iron-ore=%d coal=%d)", inv.get_item_count("iron-ore"), inv.get_item_count("coal"))
      end
    end
    if res_i then
      local ok, outinv = pcall(function() return e.get_inventory(res_i) end)
      if ok and outinv then
        line = line .. string.format(" result(iron-plate=%d)", outinv.get_item_count("iron-plate"))
      end
    end
    out[#out+1] = line
  end
end
table.sort(out)
local f = game.forces.player
return "research=" .. tostring(f.current_research and f.current_research.name) ..
  " progress=" .. tostring(f.research_progress) ..
  " speed=" .. tostring(game.speed) .. "\n" .. table.concat(out, "\n")
