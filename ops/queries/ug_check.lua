local s=game.surfaces.nauvis
local t={}
for _,p in ipairs({{-49.5,60.5},{-48.5,60.5},{-43.5,60.5},{-42.5,60.5},{-41.5,60.5},{-40.5,60.5}}) do
  local e=s.find_entity("transport-belt",{p[1],p[2]}) or s.find_entity("underground-belt",{p[1],p[2]})
  local line=""
  if e then
    local ok,tr=pcall(function() return e.get_transport_line(1) end)
    if ok and tr then local c=tr.get_contents() local q={} for _,it in pairs(c) do q[#q+1]=it.name.."x"..it.count end line=table.concat(q,",") end
  end
  t[#t+1]=string.format("%.1f,%.1f: %s#%s d=%s [%s]",p[1],p[2],e and e.name or "nil",e and tostring(e.unit_number) or "-",e and tostring(e.direction) or "-",line)
end
return table.concat(t,"\n")
