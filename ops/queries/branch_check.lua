local s=game.surfaces.nauvis
local t={}
local function invs(e)
  local p={}
  local maxi=(e.get_max_inventory_index and e.get_max_inventory_index()) or 1
  for i=1,maxi do local ci=e.get_inventory(i) if ci then for _,it in pairs(ci.get_contents()) do p[#p+1]=it.name.."x"..it.count end end end
  return table.concat(p,",")
end
for _,e in pairs(s.find_entities_filtered{area={{-36,59},{-20,64}},type={"container","inserter","splitter","transport-belt"}}) do
  if e.type~="transport-belt" or (e.position.x<-30 and e.position.y>60) then
    t[#t+1]=string.format("%s#%s @(%.1f,%.1f) d=%s st=%s [%s]",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),invs(e))
  end
end
return table.concat(t,"\n")
