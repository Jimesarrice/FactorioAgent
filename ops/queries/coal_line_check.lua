local s=game.surfaces.nauvis
local t={}
local function invs(e)
  local p={}
  local maxi=(e.get_max_inventory_index and e.get_max_inventory_index()) or 1
  for i=1,maxi do local ci=e.get_inventory(i) if ci then for _,it in pairs(ci.get_contents()) do p[#p+1]=it.name.."x"..it.count end end end
  return table.concat(p,",")
end
for _,e in pairs(s.find_entities_filtered{area={{-31,52},{-26,55}},force="player"}) do t[#t+1]=string.format("%s#%s @(%.1f,%.1f) st=%s [%s]",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.status),invs(e)) end
for _,e in pairs(s.find_entities_filtered{area={{47,40},{50,43}},force="player"}) do t[#t+1]=string.format("%s#%s @(%.1f,%.1f) st=%s [%s]",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.status),invs(e)) end
for _,e in pairs(s.find_entities_filtered{area={{-30,49},{45,50}},type="transport-belt"}) do
  if e.position.x==-27.5 or e.position.x==44.5 or e.position.x==-26.5 or e.position.x==45.5 then
    local l1=""
    local ok,tr=pcall(function() return e.get_transport_line(1) end)
    if ok and tr then local c=tr.get_contents() local q={} for _,it in pairs(c) do q[#q+1]=it.name.."x"..it.count end l1=table.concat(q,",") end
    t[#t+1]=string.format("belt @(%.1f,%.1f) d=%s [%s]",e.position.x,e.position.y,tostring(e.direction),l1)
  end
end
for _,e in pairs(s.find_entities_filtered{type="boiler",force="player"}) do t[#t+1]=string.format("boiler#%s st=%s [%s]",tostring(e.unit_number),tostring(e.status),invs(e)) end
return table.concat(t,"\n")
