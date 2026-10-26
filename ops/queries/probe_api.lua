local out = {}
local f = game.forces.player
local ok, p = pcall(function() return f.item_production_statistics end)
out[#out+1] = "prodstats="..tostring(ok).." type="..tostring(type(p))
if ok and p then
  local m = {}
  for k, v in pairs(getmetatable(p) or {}) do m[#m+1] = k end
  out[#out+1] = "methods="..table.concat(m, ",")
  local ok2, v = pcall(function() return p.get_input_count("iron-plate") end)
  out[#out+1] = "input="..tostring(ok2)..":"..tostring(v)
  local ok3, v3 = pcall(function() return p.get_output_count("iron-plate") end)
  out[#out+1] = "output="..tostring(ok3)..":"..tostring(v3)
end
local lab
for _, e in pairs(game.surfaces.nauvis.find_entities_filtered{type="lab", force="player"}) do lab = e break end
if lab then
  local okf, fl = pcall(function() return lab.get_fluid_contents() end)
  out[#out+1] = "lab fluid ok="..tostring(okf).." "..tostring(type(fl))
end
local ent
for _, e in pairs(game.surfaces.nauvis.find_entities_filtered{type="assembling-machine", force="player"}) do ent = e break end
if ent then
  local okr, r = pcall(function() return ent.get_recipe() end)
  out[#out+1] = "am recipe ok="..tostring(okr).." "..tostring(r)
end
local gen
for _, e in pairs(game.surfaces.nauvis.find_entities_filtered{type="generator", force="player"}) do gen = e break end
if gen then
  local okn, n = pcall(function() return gen.electric_network_id end)
  local oks, st = pcall(function() return gen.electric_network_statistics end)
  out[#out+1] = "gen net="..tostring(okn)..":"..tostring(n).." stats="..tostring(oks)..":"..tostring(type(st))
  if oks and st then
    local m2 = {}
    for k, v in pairs(getmetatable(st) or {}) do m2[#m2+1] = k end
    out[#out+1] = "gen methods="..table.concat(m2, ",")
    local oki, iv = pcall(function() return st.get_input_count("electricity") end)
    out[#out+1] = "gen input="..tostring(oki)..":"..tostring(iv)
  end
end
return table.concat(out, "\n")
