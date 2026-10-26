local s=game.surfaces.nauvis
local t={}
for _,e in pairs(s.find_entities_filtered{area={{293,414},{309,429}},type="pipe"}) do
  local q={}
  local ok,c=pcall(function() return e.get_fluid_contents() end)
  if ok and c then for n,a in pairs(c) do q[#q+1]=n.."="..math.floor(a) end end
  if #q>0 then t[#t+1]=string.format("(%.1f,%.1f)[%s]",e.position.x,e.position.y,table.concat(q,",")) end
end
local r=s.find_entity("oil-refinery",{298.5,423.5})
local q={}
local ok,c=pcall(function() return r.get_fluid_contents() end)
if ok and c then for n,a in pairs(c) do q[#q+1]=n.."="..math.floor(a) end end
t[#t+1]="refinery st="..tostring(r.status).." ["..table.concat(q,",").."]"
return table.concat(t,"\n")
