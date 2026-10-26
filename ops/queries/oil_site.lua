local s=game.surfaces.nauvis
local t={}
for _,e in pairs(s.find_entities_filtered{area={{285,400},{370,460}}}) do
  if e.type~="tree" and e.type~="resource" and e.type~="fish" and e.type~="simple-entity" then
    local p={}
    local maxi=(e.get_max_inventory_index and e.get_max_inventory_index()) or 1
    for i=1,maxi do local inv=e.get_inventory(i) if inv then for _,it in pairs(inv.get_contents()) do p[#p+1]=it.name.."x"..it.count end end end
    t[#t+1]=string.format("%s#%s @(%.1f,%.1f) d=%s st=%s net=%s [%s]",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),tostring(e.electric_network_id),table.concat(p,","))
  end
end
return table.concat(t,"\n")
