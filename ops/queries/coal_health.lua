local s=game.surfaces.nauvis
local t={}
for _,e in pairs(s.find_entities_filtered{area={{-33,43},{-26,55}},force="player"}) do
  if e.type=="mining-drill" or e.type=="container" or e.type=="inserter" then
    local p={}
    local maxi=(e.get_max_inventory_index and e.get_max_inventory_index()) or 1
    for i=1,maxi do local inv=e.get_inventory(i) if inv then for _,it in pairs(inv.get_contents()) do p[#p+1]=it.name.."x"..it.count end end end
    t[#t+1]=string.format("%s#%s @(%.1f,%.1f) st=%s [%s]",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.status),table.concat(p,","))
  end
end
for _,e in pairs(s.find_entities_filtered{type="boiler",force="player"}) do
  local inv=e.get_inventory(1); local n=inv and inv.get_item_count("coal") or 0
  t[#t+1]=string.format("boiler#%s st=%s coal=%d",tostring(e.unit_number),tostring(e.status),n)
end
return table.concat(t,"\n")
