local s=game.surfaces.nauvis
local t={}
local function line(e)
  local l1,l2="",""
  for i=1,2 do local ok,tr=pcall(function() return e.get_transport_line(i) end); if ok and tr then local c=tr.get_contents() local q={} for _,it in pairs(c) do q[#q+1]=it.name.."x"..it.count end if i==1 then l1=table.concat(q,",") else l2=table.concat(q,",") end end end
  return l1.."/"..l2
end
for y=47,60 do
  local e=s.find_entity("transport-belt",{-57.5,y-0.5})
  if e then t[#t+1]=string.format("(-57.5,%.1f) d=%s [%s]",y-0.5,tostring(e.direction),line(e)) end
end
local m=s.find_entity("transport-belt",{-57.5,60.5})
if m then t[#t+1]="main(-57.5,60.5) d="..tostring(m.direction).." ["..line(m).."]" end
local b=s.find_entity("transport-belt",{-57.5,59.5})
if b then
  local nb=b.belt_neighbours
  local function q(side) if not nb[side] then return "nil" end return string.format("%s@%.1f,%.1f",nb[side].name,nb[side].position.x,nb[side].position.y) end
  t[#t+1]="drain last neighbours left="..q("left").." right="..q("right")
end
return table.concat(t,"\n")
