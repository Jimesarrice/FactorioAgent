local s=game.surfaces.nauvis
local t={}
for _,p in ipairs({{295.5,411.5},{295.5,421.5},{302.5,421.5},{305.5,421.5},{303.5,410.5},{295.5,410.5}}) do
  local e=s.find_entity("pipe",{p[1],p[2]}) or s.find_entity("pipe-to-ground",{p[1],p[2]})
  if e then
    local ok,fb=pcall(function() return e.fluidbox end)
    local info="err"
    if ok and fb then
      local ok2,n=pcall(function() return #fb end)
      local ok3,f=pcall(function() return fb[1] end)
      info="len="..tostring(ok2 and n or "?").." name="..tostring(ok3 and f and f.name or "nil").." amount="..tostring(ok3 and f and f.amount or "nil")
    end
    t[#t+1]=string.format("%s @(%.1f,%.1f) %s",e.name,p[1],p[2],info)
  else t[#t+1]=string.format("no entity @(%.1f,%.1f)",p[1],p[2]) end
end
return table.concat(t,"\n")
