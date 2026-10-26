local s=game.surfaces.nauvis
local lines={}
for _,e in pairs(s.find_entities_filtered{type="electric-pole", force="player"}) do
  lines[#lines+1]=string.format("pole#%d @(%.1f,%.1f) enet=%s",e.unit_number,e.position.x,e.position.y,tostring(e.electric_network_id))
end
for _,e in pairs(s.find_entities_filtered{type="generator",force="player"}) do
  lines[#lines+1]=string.format("generator#%d @(%.1f,%.1f) enet=%s energy=%s",e.unit_number,e.position.x,e.position.y,tostring(e.electric_network_id),tostring(e.energy))
end
table.sort(lines)
return table.concat(lines,"\n")
