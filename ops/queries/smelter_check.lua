local s=game.surfaces.nauvis
local out={}
for _,e in pairs(s.find_entities_filtered{area={{-72,57},{-33,67}}}) do
  if e.type~="resource" and e.type~="tree" then
    out[#out+1]=string.format("%s#%s @(%.1f,%.1f) d=%s st=%s",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status))
  end
end
table.sort(out)
return table.concat(out,"\n")
