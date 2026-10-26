local s=game.surfaces.nauvis
local out={}
out[#out+1]="--- poles x<-10"
for _,e in pairs(s.find_entities_filtered{area={{-80,30},{-10,75}},type="electric-pole",force="player"}) do
  out[#out+1]=string.format("#%s %s @(%.1f,%.1f) net=%s",tostring(e.unit_number),e.name,e.position.x,e.position.y,tostring(e.electric_network_id))
end
table.sort(out)
out[#out+1]="--- generators/engines"
for _,t in ipairs({"generator","steam-engine","boiler","offshore-pump"}) do
  for _,e in pairs(s.find_entities_filtered{type=t,force="player"}) do
    local extra=""
    if t=="boiler" then
      local inv=e.get_inventory(defines.inventory.fuel); local parts={}
      if inv then for _,it in pairs(inv.get_contents()) do parts[#parts+1]=it.name.."x"..it.count end end
      extra=" fuel="..table.concat(parts,",")
    end
    out[#out+1]=string.format("%s#%s @(%.1f,%.1f) st=%s net=%s%s",t,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.status),tostring(e.electric_network_id),extra)
  end
end
out[#out+1]="--- network ids count"
local counts={}
for _,e in pairs(s.find_entities_filtered{type="electric-pole",force="player"}) do
  local id=tostring(e.electric_network_id); counts[id]=(counts[id] or 0)+1
end
for id,c in pairs(counts) do out[#out+1]="net="..id.." poles="..c end
return table.concat(out,"\n")
