local s=game.surfaces.nauvis
local out={}
local function invs(e)
  local parts={}
  local maxi=(e.get_max_inventory_index and e.get_max_inventory_index()) or 1
  for i=1,maxi do
    local ci=e.get_inventory(i)
    if ci then for _,it in pairs(ci.get_contents()) do parts[#parts+1]=it.name.."x"..it.count end end
  end
  return table.concat(parts,",")
end
for _,e in pairs(s.find_entities_filtered{area={{-36,52},{-18,67}},type={"container","assembling-machine","inserter","splitter","transport-belt"},force="player"}) do
  local extra=""
  if e.type=="container" then extra=" ["..invs(e).."]"
  elseif e.type=="assembling-machine" then extra=" recipe="..tostring(e.get_recipe() and e.get_recipe().name).." ["..invs(e).."]"
  end
  out[#out+1]=string.format("%s#%s @(%.1f,%.1f) d=%s st=%s%s",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),extra)
end
table.sort(out)
return table.concat(out,"\n")
