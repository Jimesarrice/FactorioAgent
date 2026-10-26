local out = {}
local f = game.forces.player
for _, name in ipairs({"get_item_production_statistics","get_fluid_production_statistics","get_kill_count_statistics","get_entity_build_count_statistics"}) do
  local ok, v = pcall(function() return f[name] end)
  out[#out+1] = name.." ok="..tostring(ok).." type="..tostring(type(v))
  if ok and type(v) == "function" then
    local ok2, r = pcall(function() return f[name](game.surfaces.nauvis) end)
    out[#out+1] = "  call="..tostring(ok2).." type="..tostring(type(r))
    if ok2 and type(r) == "userdata" then
      local ok3, cnt = pcall(function() return r.get_input_count("iron-plate") end)
      out[#out+1] = "  input="..tostring(ok3)..":"..tostring(cnt)
    end
  end
end
local s = game.surfaces.nauvis
for _, name in ipairs({"get_electric_networks","electric_networks","get_energy_production"}) do
  local ok, v = pcall(function() return s[name] end)
  out[#out+1] = "surface."..name.." ok="..tostring(ok).." type="..tostring(type(v))
end
-- assembling machine recipe check if any exist anywhere
local am
for _, e in pairs(s.find_entities_filtered{type="assembling-machine", force="player"}) do am = e break end
out[#out+1] = "am exists="..tostring(am ~= nil)
if am then
  local ok, r = pcall(function() return am.get_recipe() end)
  out[#out+1] = "am.get_recipe="..tostring(ok).." "..tostring(r)
end
return table.concat(out, "\n")
