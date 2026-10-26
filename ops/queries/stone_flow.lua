local s=game.surfaces.nauvis
local out={}
local ground={}
for _,e in pairs(s.find_entities_filtered{area={{-70,38},{-55,50}},type="item-entity"}) do
  ground[e.stack.name]=(ground[e.stack.name] or 0)+e.stack.count
end
for n,c in pairs(ground) do out[#out+1]="ground "..n.."="..c end
for _,bl in pairs(s.find_entities_filtered{area={{-70,38},{-55,50}},type="transport-belt"}) do
  local line=bl.get_transport_line(1)
  local cs=line.get_contents()
  if #cs>0 then
    local parts={}
    for _,it in pairs(cs) do parts[#parts+1]=it.name.."x"..it.count end
    out[#out+1]=string.format("belt %.1f,%.1f dir=%s %s",bl.position.x,bl.position.y,tostring(bl.direction),table.concat(parts,","))
  end
end
return table.concat(out,"\n")
