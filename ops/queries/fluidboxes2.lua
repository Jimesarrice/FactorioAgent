local s=game.surfaces.nauvis
local t={}
for _,u in ipairs({447,449,445,426}) do
  local e
  for _,x in pairs(s.find_entities_filtered{area={{295,400},{360,440}}}) do if x.unit_number==u then e=x break end end
  if e then
    t[#t+1]="--- "..e.name.."#"..u.." @("..e.position.x..","..e.position.y..")"
    for i=1,6 do
      local ok,fb=pcall(function() return e.get_fluid_box_prototype(i) end)
      if ok and fb then
        local prod="?"
        local okp,p=pcall(function() return fb.production_type end); if okp then prod=tostring(p) end
        local pipes="?"
        local okc,pc=pcall(function() return fb.pipe_connections end)
        if okc and pc then
          local q={}
          for _,c in pairs(pc) do q[#q+1]=tostring(c.position and (c.position.x..","..c.position.y) or "?").." d"..tostring(c.direction) end
          pipes=table.concat(q,";")
        end
        t[#t+1]=string.format("box%d prod=%s pipes=%s",i,prod,pipes)
      end
    end
  end
end
return table.concat(t,"\n")
