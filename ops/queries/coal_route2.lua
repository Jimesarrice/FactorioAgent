local s=game.surfaces.nauvis
local out={}
out[#out+1]="--- y 54.5..56.5 x -15..45"
for _,e in pairs(s.find_entities_filtered{area={{-15,54.5},{45,56.5}}}) do
  if e.type~="resource" then out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
end
out[#out+1]="--- trees/rocks same"
for _,e in pairs(s.find_entities_filtered{area={{-15,54.5},{45,56.5}},type={"tree","simple-entity"}}) do out[#out+1]=string.format("%s @(%.1f,%.1f)",e.name,e.position.x,e.position.y) end
out[#out+1]="--- x 43.5..45.5 y 42..55"
for _,e in pairs(s.find_entities_filtered{area={{43.5,42},{45.5,55}}}) do out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
return table.concat(out,"\n")
