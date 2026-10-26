local s=game.surfaces.nauvis
local pts={{-38.5,45.5},{-41.5,40.5},{-43.5,35.5},{-42.5,33.5}}
local out={}
for _,p in ipairs(pts) do
  local ok=s.can_place_entity{name="small-electric-pole",position={x=p[1],y=p[2]},force=game.forces.player}
  local es=s.find_entities_filtered{area={{p[1]-0.6,p[2]-0.6},{p[1]+0.6,p[2]+0.6}}}
  local names={}
  for _,e in pairs(es) do names[#names+1]=e.name end
  out[#out+1]=string.format("%.1f,%.1f can=%s near=%s",p[1],p[2],tostring(ok),table.concat(names,","))
end
-- lab power status
for _,e in pairs(s.find_entities_filtered{type="lab",force="player"}) do
  out[#out+1]=string.format("lab#%s @(%.1f,%.1f) enet=%s",tostring(e.unit_number),e.position.x,e.position.y,tostring(e.electric_network_id))
end
return table.concat(out,"\n")
