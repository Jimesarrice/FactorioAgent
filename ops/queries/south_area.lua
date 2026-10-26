local s=game.surfaces.nauvis
local out={}
for _,e in pairs(s.find_entities_filtered{area={{-42,66},{-4,78}}}) do
  if e.type~="resource" then
    out[#out+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y)
  end
end
return table.concat(out,"\n")
