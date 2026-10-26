local f=game.forces.player
local lines={}
for _,n in ipairs({"automation","electric-mining-drill","steel-processing","chemical-science-pack","rocket-silo","space-science-pack"}) do
  local t=f.technologies[n]
  if t then
    local function g(k) local ok,v=pcall(function() return t[k] end); return ok and tostring(v) or "?" end
    local ings={}
    local ok,list=pcall(function() return t.research_unit_ingredients end)
    if ok and list then for _,i in pairs(list) do ings[#ings+1]=i.name.."x"..i.amount end end
    lines[#lines+1]=string.format("%s energy=%s count=%s ings=%s researched=%s",n,g("research_unit_energy"),g("research_unit_count"),table.concat(ings,","),g("researched"))
  end
end
for _,n in ipairs({"automation-science-pack","logistic-science-pack","chemical-science-pack","space-science-pack"}) do
  local it=prototypes.item[n]
  lines[#lines+1]=n.." stack="..tostring(it and it.stack_size)
end
return table.concat(lines,"\n")
