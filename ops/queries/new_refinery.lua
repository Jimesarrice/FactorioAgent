local s=game.surfaces.nauvis
local t={}
for _,e in pairs(s.find_entities_filtered{area={{290,415},{310,430}}}) do
  if e.type=="oil-refinery" or e.type=="chemical-plant" or e.type=="electric-pole" or e.type=="pipe" or e.type=="pipe-to-ground" then
    local extra=""
    if e.type=="oil-refinery" or e.type=="chemical-plant" then extra=" recipe="..tostring(e.get_recipe() and e.get_recipe().name) end
    t[#t+1]=string.format("%s#%s @(%.1f,%.1f) d=%s st=%s net=%s%s",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),tostring(e.electric_network_id),extra)
  end
end
return table.concat(t,"\n")
