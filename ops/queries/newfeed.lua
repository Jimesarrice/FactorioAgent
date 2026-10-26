local s=game.surfaces.nauvis
local t={}
for _,e in pairs(s.find_entities_filtered{area={{-33,61},{-23,65}},type={"inserter","transport-belt","container","electric-pole"},force="player"}) do
  local extra=""
  if e.type=="container" then local p={} local maxi=e.get_max_inventory_index() for i=1,maxi do local inv=e.get_inventory(i) if inv then for _,it in pairs(inv.get_contents()) do p[#p+1]=it.name.."x"..it.count end end end extra="["..table.concat(p,",").."]" end
  if e.type=="transport-belt" then local ok,tr=pcall(function() return e.get_transport_line(1) end) if ok and tr then local c=tr.get_contents() local q={} for _,it in pairs(c) do q[#q+1]=it.name.."x"..it.count end extra="["..table.concat(q,",").."]" end end
  t[#t+1]=string.format("%s#%s @(%.1f,%.1f) d=%s st=%s %s",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),extra)
end
return table.concat(t,"\n")
