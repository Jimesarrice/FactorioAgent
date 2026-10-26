local s=game.surfaces.nauvis
local t={}
local function invs(e)
  local p={}
  local maxi=(e.get_max_inventory_index and e.get_max_inventory_index()) or 1
  for i=1,maxi do local inv=e.get_inventory(i) if inv then for _,it in pairs(inv.get_contents()) do p[#p+1]=it.name.."x"..it.count end end end
  return table.concat(p,",")
end
for _,e in pairs(s.find_entities_filtered{area={{-22,44},{24,76}},type={"assembling-machine","lab","container","inserter","transport-belt","splitter"}}) do
  if e.type~="transport-belt" or (e.position.y>58 and e.position.x<12) then
    local r=""
    if e.type=="assembling-machine" then r=" recipe="..tostring(e.get_recipe() and e.get_recipe().name) end
    t[#t+1]=string.format("%s#%s @(%.1f,%.1f) d=%s st=%s%s [%s]",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),r,invs(e))
  end
end
return table.concat(t,"\n")
