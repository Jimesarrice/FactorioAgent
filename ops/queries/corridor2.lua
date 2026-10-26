local s=game.surfaces.nauvis
local out={}
out[#out+1]="--- vertical x -37..-34 y 42..59"
for _,e in pairs(s.find_entities_filtered{area={{-37.9,42},{-33.1,59}}}) do
  if e.type~="resource" and e.type~="tree" then out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
end
out[#out+1]="--- horizontal y 40.5..42.5 x -35..0"
for _,e in pairs(s.find_entities_filtered{area={{-35,40.1},{0,42.9}}}) do
  if e.type~="resource" and e.type~="tree" then out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
end
out[#out+1]="--- resources at corridor top"
for _,e in pairs(s.find_entities_filtered{area={{-36,40},{-2,44}},type="resource"}) do out[#out+1]=e.name.." @("..e.position.x..","..e.position.y..")" end
return table.concat(out,"\n")
