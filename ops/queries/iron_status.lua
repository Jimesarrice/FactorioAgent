local s=game.surfaces.nauvis
local out={}
out[#out+1]="--- drills"
for _,e in pairs(s.find_entities_filtered{type="mining-drill",force="player"}) do
  out[#out+1]=string.format("%s#%s @(%.1f,%.1f) st=%s",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.status))
end
out[#out+1]="--- furnaces x<-20"
for _,e in pairs(s.find_entities_filtered{type="furnace",force="player"}) do
  if e.position.x<-20 then
    local parts={}
    for i=1,4 do
      local ci=e.get_inventory(i)
      if ci then for _,it in pairs(ci.get_contents()) do parts[#parts+1]=it.name.."x"..it.count end end
    end
    out[#out+1]=string.format("#%s @(%.0f,%.0f) st=%s %s",tostring(e.unit_number),e.position.x,e.position.y,tostring(e.status),table.concat(parts,","))
  end
end
out[#out+1]="--- chests"
for _,e in pairs(s.find_entities_filtered{type="container",force="player"}) do
  local parts={}
  for i=1,3 do
    local ci=e.get_inventory(i)
    if ci then for _,it in pairs(ci.get_contents()) do parts[#parts+1]=it.name.."x"..it.count end end
  end
  if #parts>0 then out[#out+1]=string.format("#%s @(%.1f,%.1f) %s",tostring(e.unit_number),e.position.x,e.position.y,table.concat(parts,",")) end
end
return table.concat(out,"\n")
