local s=game.surfaces.nauvis
local out={}
for _,t in ipairs({"inserter","transport-belt","splitter","container","furnace"}) do
  out[#out+1]="--- "..t
  for _,e in pairs(s.find_entities_filtered{area={{-24,40},{4,53}},type=t,force="player"}) do
    local parts={}
    if t=="container" then for i=1,2 do local ci=e.get_inventory(i); if ci then for _,it in pairs(ci.get_contents()) do parts[#parts+1]=it.name.."x"..it.count end end end end
    out[#out+1]=string.format("#%s @(%.1f,%.1f) d=%s st=%s %s",tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),table.concat(parts,","))
  end
end
return table.concat(out,"\n")
