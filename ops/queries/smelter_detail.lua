local s=game.surfaces.nauvis
local out={}
local function invs(e)
  local p={}
  local maxi=(e.get_max_inventory_index and e.get_max_inventory_index()) or 1
  for i=1,maxi do local ci=e.get_inventory(i) if ci then for _,it in pairs(ci.get_contents()) do p[#p+1]=it.name.."x"..it.count end end end
  return table.concat(p,",")
end
for _,e in pairs(s.find_entities_filtered{area={{-70,57},{-34,67}}}) do
  if e.type=="furnace" then
    out[#out+1]=string.format("F#%s @(%.0f,%.0f) st=%s [%s]",tostring(e.unit_number),e.position.x,e.position.y,tostring(e.status),invs(e))
  elseif e.type=="inserter" and e.position.y>60 then
    out[#out+1]=string.format("I#%s @(%.1f,%.1f) st=%s [%s]",tostring(e.unit_number),e.position.x,e.position.y,tostring(e.status),invs(e))
  elseif e.type=="container" and (e.unit_number==204 or e.unit_number==633) then
    out[#out+1]=string.format("CHEST%s [%s]",tostring(e.unit_number),invs(e))
  end
end
return table.concat(out,"\n")
