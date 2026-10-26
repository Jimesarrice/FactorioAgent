local s=game.surfaces.nauvis
local out={}
local function st(e) return tostring(e.status) end
out[#out+1]="--- furnaces all"
for _,e in pairs(s.find_entities_filtered{type="furnace",force="player"}) do
  local parts={}
  for i=1,3 do local ci=e.get_inventory(i); if ci then for _,it in pairs(ci.get_contents()) do parts[#parts+1]=it.name.."x"..it.count end end end
  out[#out+1]=string.format("#%s @(%.0f,%.0f) d=%s st=%s %s",tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),st(e),table.concat(parts,","))
end
out[#out+1]="--- inserters area"
for _,e in pairs(s.find_entities_filtered{area={{-75,35},{-15,72}},type="inserter",force="player"}) do
  out[#out+1]=string.format("#%s @(%.1f,%.1f) d=%s st=%s",tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),st(e))
end
out[#out+1]="--- belts x -70..-25 y 45..68"
for _,e in pairs(s.find_entities_filtered{area={{-71,45},{-25,68}},type="transport-belt",force="player"}) do
  out[#out+1]=string.format("(%.1f,%.1f) d=%s",e.position.x,e.position.y,tostring(e.direction))
end
table.sort(out)
return table.concat(out,"\n")
