local s=game.surfaces.nauvis
local out={}
for _,e in pairs(s.find_entities_filtered{area={{-75,33},{-55,62}}}) do
  if e.type~="resource" and e.type~="tree" and e.type~="character" then
    local extra=""
    if e.type=="container" or e.type=="furnace" then
      local parts={}
      for i=1,3 do local ci=e.get_inventory(i); if ci then for _,it in pairs(ci.get_contents()) do parts[#parts+1]=it.name.."x"..it.count end end end
      extra=" ["..table.concat(parts,",").."]"
    elseif e.type=="mining-drill" then
      local ci=e.get_inventory(defines.inventory.fuel); local parts={}
      if ci then for _,it in pairs(ci.get_contents()) do parts[#parts+1]=it.name.."x"..it.count end end
      extra=" fuel["..table.concat(parts,",").."]"
    end
    out[#out+1]=string.format("%s#%s @(%.1f,%.1f) d=%s st=%s%s",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),extra)
  end
end
return table.concat(out,"\n")
