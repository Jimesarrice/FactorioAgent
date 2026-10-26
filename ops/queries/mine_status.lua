local s=game.surfaces.nauvis
local t={}
for _,e in pairs(s.find_entities_filtered{area={{-72,45},{-35,62}}}) do
  if e.type=="mining-drill" or e.type=="container" then
    local p={}
    local maxi=(e.get_max_inventory_index and e.get_max_inventory_index()) or 1
    for i=1,maxi do local ci=e.get_inventory(i) if ci then for _,it in pairs(ci.get_contents()) do p[#p+1]=it.name.."x"..it.count end end end
    t[#t+1]=string.format("%s#%s @(%.1f,%.1f) st=%s [%s]",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.status),table.concat(p,","))
  end
end
return table.concat(t,"\n")
