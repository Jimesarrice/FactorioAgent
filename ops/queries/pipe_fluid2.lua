local s=game.surfaces.nauvis
local t={}
for _,p in ipairs({{295.5,411.5},{295.5,421.5},{302.5,421.5},{305.5,421.5},{303.5,410.5},{295.5,410.5}}) do
  local e=s.find_entity("pipe",{p[1],p[2]}) or s.find_entity("pipe-to-ground",{p[1],p[2]})
  if e then
    local ok,c=pcall(function() return e.get_fluid_contents() end)
    local q={}
    if ok and c then for n,a in pairs(c) do q[#q+1]=n.."="..tostring(a) end end
    t[#t+1]=string.format("%s @(%.1f,%.1f) [%s]",e.name,p[1],p[2],table.concat(q,","))
  else t[#t+1]=string.format("no entity @(%.1f,%.1f)",p[1],p[2]) end
end
local r=s.find_entity("oil-refinery",{300.5,413.5})
if r then local ok,c=pcall(function() return r.get_fluid_contents() end) local q={} if ok and c then for n,a in pairs(c) do q[#q+1]=n.."="..tostring(a) end end t[#t+1]="refinery ["..table.concat(q,",").."] st="..tostring(r.status) end
return table.concat(t,"\n")
