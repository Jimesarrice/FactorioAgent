local f = game.forces.player
local lines = {}
local tnames = {"automation","logistics","electric-mining-drill","automation-2","steel-processing",
  "logistics-2","oil-gathering","oil-processing","fluid-handling","engine","solar-energy",
  "military","military-2","stone-wall","fast-inserter","toolbelt","landfill","railway"}
for _,n in ipairs(tnames) do
  local t=f.technologies[n]
  if t then
    local cost="?"; pcall(function() cost=t.research_unit_energy end)
    local pre={}; for _,p in pairs(t.prerequisites or {}) do pre[#pre+1]=p.name end
    local ing={}; local r=f.recipes[n]
    lines[#lines+1]=string.format("%s cost=%s researched=%s enabled=%s pre=%s",n,tostring(cost),tostring(t.researched),tostring(t.enabled),table.concat(pre,","))
  end
end
lines[#lines+1]="--- recipes"
local rnames={"burner-mining-drill","electric-mining-drill","stone-furnace","steel-furnace",
  "transport-belt","inserter","assembling-machine-1","assembling-machine-2","lab",
  "small-electric-pole","medium-electric-pole","big-electric-pole","pipe","pipe-to-ground",
  "offshore-pump","boiler","steam-engine","iron-gear-wheel","copper-cable","electronic-circuit",
  "advanced-circuit","engine-unit","electric-engine-unit","steel-plate","stone-brick","concrete",
  "refinery","chemical-plant","pumpjack","storage-tank","pump","solar-panel","accumulator",
  "roboport","construction-robot","logistic-robot","train-stop","locomotive","cargo-wagon","fluid-wagon",
  "rail","rocket-silo","rocket-part","low-density-structure","rocket-fuel","processing-unit",
  "space-platform-foundation","asteroid-collector","crusher","cargo-bay","space-platform-starter-pack",
  "solar-panel","battery","engine-unit","electric-furnace","productivity-module","speed-module"}
for _,n in ipairs(rnames) do
  local r=f.recipes[n]
  if r then
    local ing={}; for _,i in pairs(r.ingredients) do ing[#ing+1]=i.name.."x"..i.amount end
    local prod={}; for _,p in pairs(r.products or {}) do prod[#prod+1]=p.name.."x"..p.amount end
    lines[#lines+1]=string.format("%s cat=%s %.1fs in=%s out=%s",n,table.concat(r.categories or {},","),r.energy,table.concat(ing,"+"),table.concat(prod,"+"))
  else
    lines[#lines+1]=n.." MISSING"
  end
end
return table.concat(lines,"\n")
