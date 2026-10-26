local s=game.surfaces.nauvis
local out={}
for _,e in pairs(s.find_entities_filtered{area={{-72,59},{-18,62}}}) do
  if e.type~="resource" and e.type~="tree" and e.type~="character" then
    out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y)
  end
end
out[#out+1]="--- trees/rocks in corridor"
for _,e in pairs(s.find_entities_filtered{area={{-72,59},{-18,62}},type={"tree","simple-entity"}}) do
  out[#out+1]=string.format("%s @(%.1f,%.1f)",e.name,e.position.x,e.position.y)
end
return table.concat(out,"\n")
