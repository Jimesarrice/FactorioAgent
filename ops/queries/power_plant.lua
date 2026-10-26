local s=game.surfaces.nauvis
local out={}
for _,t in ipairs({"inserter","container","transport-belt","splitter","underground-belt","small-electric-pole","medium-electric-pole"}) do
  out[#out+1]="--- "..t
  for _,e in pairs(s.find_entities_filtered{area={{44,3},{64,44}},type=t,force="player"}) do
    local parts={}
    if t=="container" then
      for i=1,2 do local ci=e.get_inventory(i); if ci then for _,it in pairs(ci.get_contents()) do parts[#parts+1]=it.name.."x"..it.count end end end
    elseif t=="inserter" then
      local ci=e.get_inventory(defines.inventory.inserter_hand); if ci then for _,it in pairs(ci.get_contents()) do parts[#parts+1]=it.name.."x"..it.count end end
    end
    if t=="transport-belt" or t=="inserter" or t=="container" then
      out[#out+1]=string.format("#%s @(%.1f,%.1f) d=%s st=%s %s",tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),table.concat(parts,","))
    end
  end
end
return table.concat(out,"\n")
