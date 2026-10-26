local s=game.surfaces.nauvis
local out={}
for _,e in pairs(s.find_entities_filtered{area={{-37,52},{-18,68}},type="transport-belt"}) do
  out[#out+1]=string.format("%.1f,%.1f d=%s",e.position.x,e.position.y,tostring(e.direction))
end
table.sort(out)
return table.concat(out,"\n")
