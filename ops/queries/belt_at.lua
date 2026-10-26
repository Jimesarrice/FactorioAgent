local s=game.surfaces.nauvis
local out={}
for _,e in pairs(s.find_entities_filtered{area={{-63,39},{-60,46}},type="transport-belt"}) do
  local p1={}; local p2={}
  for _,it in pairs(e.get_transport_line(1).get_contents()) do p1[#p1+1]=it.name.."x"..it.count end
  for _,it in pairs(e.get_transport_line(2).get_contents()) do p2[#p2+1]=it.name.."x"..it.count end
  out[#out+1]=string.format("%.1f,%.1f dir=%s L1=%s L2=%s",e.position.x,e.position.y,tostring(e.direction),table.concat(p1,","),table.concat(p2,","))
end
for _,e in pairs(s.find_entities_filtered{area={{-64,39},{-60,46}},type="item-entity"}) do
  out[#out+1]=string.format("item %s @(%.1f,%.1f)",e.stack.name,e.position.x,e.position.y)
end
return table.concat(out,"\n")
