local s=game.surfaces.nauvis
local out={}
for _,e in pairs(s.find_entities_filtered{area={{-39.8,42},{-37.2,61}}}) do
  if e.type~="resource" and e.type~="tree" then out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y) end
end
return table.concat(out,"\n")
