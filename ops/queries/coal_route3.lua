local s=game.surfaces.nauvis
local out={}
out[#out+1]="--- y 49.5..51.5 x -28..45"
for _,e in pairs(s.find_entities_filtered{area={{-28,49.5},{45,51.5}}}) do
  if e.type~="resource" then out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
end
out[#out+1]="--- x -28.5..-26.5 y 50..54"
for _,e in pairs(s.find_entities_filtered{area={{-28.5,50},{-26.5,54}}}) do out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
out[#out+1]="--- trees/rocks y49..52 x -28..45"
for _,e in pairs(s.find_entities_filtered{area={{-28,49},{45,52}},type={"tree","simple-entity"}}) do out[#out+1]=string.format("%s @(%.1f,%.1f)",e.name,e.position.x,e.position.y) end
return table.concat(out,"\n")
