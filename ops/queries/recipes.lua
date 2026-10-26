local names = {
  "rocket-part", "rocket-silo", "space-platform-starter-pack", "space-science-pack",
  "processing-unit", "advanced-circuit", "electronic-circuit", "low-density-structure",
  "rocket-fuel", "solid-fuel", "plastic-bar", "sulfur", "sulfuric-acid", "battery",
  "utility-science-pack", "production-science-pack", "chemical-science-pack",
  "military-science-pack", "logistic-science-pack", "automation-science-pack",
  "space-platform-foundation", "asteroid-collector", "crusher", "cargo-bay",
}
local f = game.forces.player
local lines = {}

local function describe(recipe)
  local ing = {}
  for _, i in pairs(recipe.ingredients) do
    ing[#ing+1] = string.format("%s x%s", i.name, i.amount)
  end
  local prod = {}
  for _, p in pairs(recipe.products or {}) do
    prod[#prod+1] = string.format("%s x%s", p.name, p.amount)
  end
  return string.format("%s [%s] %.2fs  in: %s  out: %s", recipe.name,
    table.concat(recipe.categories or {}, ","), recipe.energy,
    table.concat(ing, " + "), table.concat(prod, " + "))
end

for _, n in ipairs(names) do
  local r = f.recipes[n]
  if r then
    lines[#lines+1] = describe(r)
  else
    lines[#lines+1] = n.." [recipe not enabled]"
  end
end

lines[#lines+1] = "--- technologies"
local tnames = {"rocket-silo","rocket-fuel","low-density-structure","processing-unit",
  "utility-science-pack","production-science-pack","chemical-science-pack",
  "space-platform","space-science-pack","asteroid-processing","advanced-asteroid-processing",
  "railway","automated-rail-transportation","oil-processing","advanced-oil-processing",
  "coal-liquefaction","electric-engine","automation-3","logistics-3","construction-robotics"}
for _, n in ipairs(tnames) do
  local t = f.technologies[n]
  if t then
    local pre = {}
    for _, p in pairs(t.prerequisites or {}) do pre[#pre+1] = p.name end
    local cost = "?"
    pcall(function() cost = t.research_unit_energy end)
    lines[#lines+1] = string.format("%s researched=%s enabled=%s cost=%s pre=%s",
      n, tostring(t.researched), tostring(t.enabled), tostring(cost), table.concat(pre, ","))
  else
    lines[#lines+1] = n.." [tech missing]"
  end
end
return table.concat(lines, "\n")
