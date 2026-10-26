local s=game.surfaces.nauvis
local t={}
for _,e in pairs(s.find_entities_filtered{area={{290,415},{312,432}}}) do
  if e.name=="oil-refinery" or e.name=="chemical-plant" then
    t[#t+1]=string.format("%s#%s @(%.1f,%.1f) st=%s net=%s recipe=%s",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.status),tostring(e.electric_network_id),tostring(e.get_recipe() and e.get_recipe().name))
  end
end
return table.concat(t,"\n")
