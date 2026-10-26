local s=game.surfaces.nauvis
local lines={}
local status_names={}
for k,v in pairs(defines.entity_status) do status_names[v]=k end
for _,e in pairs(s.find_entities_filtered{area={{-50,45},{-10,60}}, force="player"}) do
  lines[#lines+1]=string.format("IRON %s#%s @(%.1f,%.1f) dir=%s status=%s enet=%s",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(status_names[e.status]),tostring(e.electric_network_id))
end
for _,e in pairs(s.find_entities_filtered{area={{-5,55},{30,75}}, force="player"}) do
  lines[#lines+1]=string.format("COPPER %s#%s @(%.1f,%.1f) dir=%s status=%s enet=%s",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(status_names[e.status]),tostring(e.electric_network_id))
end
-- also any ghosts left
for _,g in pairs(s.find_entities_filtered{area={{-50,45},{30,75}}, force="player", type="entity-ghost"}) do
  lines[#lines+1]=string.format("GHOST %s @(%.1f,%.1f)",g.ghost_name,g.position.x,g.position.y)
end
table.sort(lines)
return table.concat(lines,"\n")
