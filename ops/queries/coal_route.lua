local s=game.surfaces.nauvis
local out={}
out[#out+1]="--- y 52..55 x -30..48"
for _,e in pairs(s.find_entities_filtered{area={{-30,52},{-21,55}}}) do out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
for _,e in pairs(s.find_entities_filtered{area={{-21,52},{48,55}}}) do out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
out[#out+1]="--- x 43..46 y 40..54"
for _,e in pairs(s.find_entities_filtered{area={{43,40},{46,54}}}) do out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
out[#out+1]="--- x 45..52 y 9..42"
for _,e in pairs(s.find_entities_filtered{area={{45,9},{52,42}}}) do out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
return table.concat(out,"\n")
