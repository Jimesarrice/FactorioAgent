local e
for _, cand in pairs(game.surfaces.nauvis.find_entities_filtered{area={{-60,20},{30,80}}}) do
  if cand.unit_number == 43 then e = cand break end
end
if not e then return "drill not found" end
local ma = e.mining_area
local counts = {}
for _, r in pairs(game.surfaces.nauvis.find_entities_filtered{area=ma, type="resource"}) do
  counts[r.name] = (counts[r.name] or 0) + r.amount
end
local parts = {}
for n, a in pairs(counts) do parts[#parts+1] = n.."="..a end
table.sort(parts)
return string.format("drill@%.1f,%.1f dir=%s status=%s area=(%.0f,%.0f)-(%.0f,%.0f) %s",
  e.position.x, e.position.y, tostring(e.direction), tostring(e.status),
  ma.left_top.x, ma.left_top.y, ma.right_bottom.x, ma.right_bottom.y, table.concat(parts, ","))
