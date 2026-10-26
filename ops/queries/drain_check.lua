local s=game.surfaces.nauvis
local t={}
for _,p in ipairs({{-57.5,59.5},{-56.5,47.5},{-55.5,47.5},{-42.5,59.5},{-43.5,59.5}}) do
  local es=s.find_entities_filtered{position={x=p[1],y=p[2]},radius=0.4}
  local n={}
  for _,e in pairs(es) do n[#n+1]=e.name.."#"..tostring(e.unit_number).." st="..tostring(e.status) end
  t[#t+1]=string.format("%.1f,%.1f -> %s",p[1],p[2],table.concat(n,","))
end
for _,e in pairs(s.find_entities_filtered{area={{-60,46},{-40,61}},type={"inserter","transport-belt","electric-pole"}}) do
  if e.position.x<-55 or e.position.x>-45 then
    t[#t+1]=string.format("%s#%s @(%.1f,%.1f) d=%s st=%s net=%s",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),tostring(e.electric_network_id))
  end
end
return table.concat(t,"\n")
