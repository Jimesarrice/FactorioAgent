local out={}
for _,s in pairs(game.surfaces) do
  for _,g in pairs(s.find_entities_filtered{type={"generator","boiler"},force="player"}) do
    out[#out+1]=string.format("%s#%s @(%.1f,%.1f) surf=%s st=%s net=%s",g.name,tostring(g.unit_number),g.position.x,g.position.y,s.name,tostring(g.status),tostring(g.electric_network_id))
  end
end
local s=game.surfaces.nauvis
out[#out+1]="--- nauvis area 40..65,5..45 all non-tree"
local n=0
for _,e in pairs(s.find_entities_filtered{area={{40,5},{65,45}}}) do
  if e.type~="tree" and e.type~="simple-entity" and e.type~="resource" then
    n=n+1
    if n<200 then out[#out+1]=string.format("%s#%s(%s) @(%.1f,%.1f) d=%s st=%s",e.type,e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status)) end
  end
end
out[#out+1]="count="..n
return table.concat(out,"\n")
