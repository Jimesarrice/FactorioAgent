local s=game.surfaces.nauvis
local t={}
for _,p in ipairs({{-42.5,60.5},{-41.5,60.5},{-40.5,60.5},{-57.5,60.5},{-56.5,60.5},{-63.5,57.5},{-63.5,58.5},{-64.5,58.5}}) do
  local e=s.find_entity("transport-belt",{p[1],p[2]})
  if e then
    local l1,l2="",""
    for i=1,2 do
      local ok,tr=pcall(function() return e.get_transport_line(i) end)
      if ok and tr then local c=tr.get_contents() local q={} for _,it in pairs(c) do q[#q+1]=it.name.."x"..it.count end if i==1 then l1=table.concat(q,",") else l2=table.concat(q,",") end end
    end
    t[#t+1]=string.format("%.1f,%.1f d=%s L1[%s] L2[%s]",p[1],p[2],tostring(e.direction),l1,l2)
  else
    t[#t+1]=string.format("%.1f,%.1f no-belt",p[1],p[2])
  end
end
return table.concat(t,"\n")
