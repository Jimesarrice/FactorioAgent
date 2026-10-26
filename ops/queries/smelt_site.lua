local s=game.surfaces.nauvis
local out={}
out[#out+1]="--- y 60.5 ore line"
for _,e in pairs(s.find_entities_filtered{area={{-71,59.9},{-35,61.1}}}) do
  if e.type~="resource" and e.type~="tree" then out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
end
out[#out+1]="--- y 61..66 x -66..-35"
for _,e in pairs(s.find_entities_filtered{area={{-66,61},{-35,66}}}) do
  if e.type~="resource" and e.type~="tree" then out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
end
out[#out+1]="--- trees/rocks y 59..66 x -71..-35"
for _,e in pairs(s.find_entities_filtered{area={{-71,59},{-35,66}},type={"tree","simple-entity"}}) do
  out[#out+1]=string.format("%s @(%.1f,%.1f)",e.name,e.position.x,e.position.y)
end
return table.concat(out,"\n")
