local s=game.surfaces.nauvis
local t={}
local function line(e)
  local out={}
  for i=1,2 do local ok,tr=pcall(function() return e.get_transport_line(i) end); if ok and tr then local c=tr.get_contents() local q={} for _,it in pairs(c) do q[#q+1]=it.name.."x"..it.count end out[#out+1]="L"..i.."["..table.concat(q,",").."]" end end
  return table.concat(out," ")
end
for _,p in ipairs({{-24.5,63.5},{-25.5,63.5},{-27.5,63.5},{-29.5,63.5},{-30.5,63.5},{-31.5,63.5},{-31.5,62.5},{-31.5,61.5},{-31.5,60.5}}) do
  local e=s.find_entity("transport-belt",{p[1],p[2]}) or s.find_entity("inserter",{p[1],p[2]}) or s.find_entity("wooden-chest",{p[1],p[2]})
  if e then t[#t+1]=string.format("%s#%s @(%.1f,%.1f) d=%s st=%s %s",e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),e.type=="transport-belt" and line(e) or "") end
end
return table.concat(t,"\n")
