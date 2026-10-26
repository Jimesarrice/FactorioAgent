local s=game.surfaces.nauvis
local out={}
local groups={}
for _,e in pairs(s.find_entities_filtered{area={{-80,30},{-20,70}},type="item-entity"}) do
  local n=e.stack.name
  groups[n]=(groups[n] or 0)+e.stack.count
end
for n,c in pairs(groups) do out[#out+1]=n.."="..c end
table.sort(out)
return table.concat(out,", ")
